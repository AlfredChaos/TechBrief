from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone as dt_timezone

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import DateTimeField, Q, QuerySet, Value
from django.db.models.functions import Coalesce
from django.http import Http404
from django.utils import timezone

from techbrief.apps.content_pipeline.models import ContentItem
from techbrief.apps.publishers.models import (
    ContentPageSnapshot,
)
from techbrief.apps.publishers.services import subscribe_email, unsubscribe_by_token
from techbrief.apps.web.models import (
    HomePage,
    ListingDefaultSort,
    ListingPage,
    ListingPageCode,
    StaticPage,
    StaticPageCode,
)
from techbrief.apps.web.theme import THEME_TOKENS, build_theme_css_variables, build_dark_mode_css_variables

LOCALE_COOKIE_NAME = "tb_locale"
DEFAULT_LOCALE = "en-US"
SUPPORTED_LOCALES = {"zh-CN", "en-US"}
SUPPORTED_VIEW_MODES = {"zh", "bilingual"}


@dataclass(frozen=True)
class SiteLocale:
    code: str
    is_chinese: bool


def normalize_locale(locale: str | None) -> str:
    if not locale:
        return DEFAULT_LOCALE

    value = locale.strip()
    lowered = value.lower()
    if lowered.startswith("zh"):
        return "zh-CN"
    if lowered.startswith("en"):
        return "en-US"
    if value in SUPPORTED_LOCALES:
        return value
    return DEFAULT_LOCALE


def resolve_locale(request, *, use_query: bool = True, use_cookie: bool = True) -> SiteLocale:
    candidate = None
    if use_query:
        candidate = request.GET.get("locale")
    if not candidate and use_cookie:
        candidate = request.COOKIES.get(LOCALE_COOKIE_NAME)
    if not candidate:
        accept_language = request.headers.get("Accept-Language", "")
        candidate = accept_language.split(",")[0] if accept_language else None
    code = normalize_locale(candidate)
    return SiteLocale(code=code, is_chinese=code == "zh-CN")


def get_localized_value(locale: SiteLocale, zh_value: str | None, en_value: str | None) -> str:
    if locale.is_chinese:
        return zh_value or en_value or ""
    return en_value or zh_value or ""


def get_home_page() -> HomePage:
    page = HomePage.objects.live().public().filter(is_published=True).first()
    if page is None:
        raise Http404("home page not found")
    return page


def get_listing_page(page_code: str) -> ListingPage:
    page = ListingPage.objects.live().public().filter(page_code=page_code, is_published=True).first()
    if page is None:
        raise Http404("listing page not found")
    return page


def get_static_page(page_code: str) -> StaticPage:
    page = StaticPage.objects.live().public().filter(page_code=page_code, is_published=True).first()
    if page is None:
        raise Http404("static page not found")
    return page


def get_detail_snapshot(slug: str, content_type: str | None = None) -> ContentPageSnapshot:
    queryset = _base_snapshot_queryset().filter(slug=slug)
    if content_type:
        queryset = queryset.filter(page_kind=content_type)
    snapshot = queryset.first()
    if snapshot is None:
        raise Http404("content page snapshot not found")
    return snapshot


def _base_snapshot_queryset() -> QuerySet[ContentPageSnapshot]:
    return (
        ContentPageSnapshot.objects.filter(is_published=True)
        .select_related("content_item__source", "cover_artifact")
        .annotate(
            effective_published_at=Coalesce(
                "published_at",
                "published_at_source_snapshot",
                "content_item__published_at_web",
                "content_item__published_at_source",
                Value(timezone.now(), output_field=DateTimeField()),
            )
        )
    )


def query_public_snapshots(
    *,
    source: str | None = None,
    content_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    sort: str = ListingDefaultSort.PUBLISHED_DESC,
) -> QuerySet[ContentPageSnapshot]:
    queryset = _base_snapshot_queryset()
    if source:
        queryset = queryset.filter(content_item__source__source_code=source)
    if content_type in {"article", "video"}:
        queryset = queryset.filter(page_kind=content_type)
    if date_from:
        queryset = queryset.filter(effective_published_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(effective_published_at__date__lte=date_to)
    if q:
        queryset = queryset.filter(
            Q(title_zh_snapshot__icontains=q)
            | Q(title_original_snapshot__icontains=q)
            | Q(summary_zh_snapshot__icontains=q)
        )

    if sort == ListingDefaultSort.PUBLISHED_ASC:
        return queryset.order_by("effective_published_at", "slug")
    if sort == ListingDefaultSort.UPDATED_DESC:
        return queryset.order_by("-last_synced_at", "-effective_published_at", "slug")
    return queryset.order_by("-effective_published_at", "slug")


def paginate_queryset(queryset, *, page: int, page_size: int) -> dict:
    paginator = Paginator(queryset, page_size)
    current_page = paginator.get_page(page)
    return {
        "items": list(current_page.object_list),
        "pagination": {
            "page": current_page.number,
            "page_size": page_size,
            "total": paginator.count,
            "total_pages": paginator.num_pages,
        },
    }


def parse_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def build_public_navigation(locale: SiteLocale, current_path: str) -> list[dict]:
    return [
        {
            "label": get_localized_value(locale, "最新内容", "Articles"),
            "url": "/articles",
            "is_active": current_path.startswith("/articles"),
        },
        {
            "label": get_localized_value(locale, "关于", "About"),
            "url": "/about",
            "is_active": current_path.startswith("/about"),
        },
        {
            "label": get_localized_value(locale, "归档", "Archive"),
            "url": "/archive",
            "is_active": current_path.startswith("/archive"),
        },
    ]


def build_footer_links(locale: SiteLocale) -> list[dict]:
    return [
        {"label": get_localized_value(locale, "隐私", "Privacy"), "url": "/privacy"},
        {"label": get_localized_value(locale, "条款", "Terms"), "url": "/terms"},
        {"label": "API", "url": "/api/public/content-items"},
    ]


def build_base_context(request, *, locale: SiteLocale | None = None) -> dict:
    locale = locale or resolve_locale(request)
    return {
        "site_locale": locale,
        "theme_tokens": THEME_TOKENS,
        "theme_css_variables": build_theme_css_variables(),
        "dark_mode_css_variables": build_dark_mode_css_variables(),
        "ga4_measurement_id": getattr(settings, "GA4_MEASUREMENT_ID", ""),
        "brand_name": "TechBrief",
        "nav_items": build_public_navigation(locale, request.path),
        "footer_links": build_footer_links(locale),
        "subscribe_labels": {
            "button": get_localized_value(locale, "立即订阅", "Subscribe"),
            "modal_title": get_localized_value(locale, "订阅每日 AI 内容汇总", "Subscribe To Daily AI Briefings"),
            "modal_body": get_localized_value(
                locale,
                "获取当天新增的 AI 翻译文章与深度内容摘要，每日汇总发送到您的邮箱。",
                "Receive newly published AI translations and daily editorial summaries in your inbox.",
            ),
            "modal_placeholder": get_localized_value(locale, "输入您的邮箱地址", "Enter your email"),
            "modal_submit": get_localized_value(locale, "立即订阅", "Subscribe Now"),
            "privacy": get_localized_value(locale, "我们尊重您的隐私，随时可以取消订阅。", "We respect your privacy and you can unsubscribe anytime."),
            "success_title": get_localized_value(locale, "感谢订阅！", "Subscription Confirmed"),
            "success_body": get_localized_value(
                locale,
                "您的邮箱已成功加入订阅名单，感谢关注！",
                "Your email has been added to our list. Thanks for subscribing!",
            ),
            "success_back": get_localized_value(locale, "返回浏览", "Back To Reading"),
            "error_invalid": get_localized_value(locale, "请输入有效邮箱地址。", "Please enter a valid email address."),
            "error_failed": get_localized_value(locale, "订阅失败，请稍后重试。", "Subscription failed. Please try again later."),
            "submitting": get_localized_value(locale, "提交中...", "Submitting..."),
        },
        "current_path": request.path,
        "locale_switch_url_zh": build_locale_switch_url(request, "zh-CN"),
        "locale_switch_url_en": build_locale_switch_url(request, "en-US"),
        "unsubscribe_api_url": "/api/public/subscriptions/unsubscribe",
        "subscription_api_url": "/api/public/subscriptions",
        "seo_description": "",
        "canonical_url": f"{getattr(settings, 'PUBLIC_BASE_URL', '')}{request.path}",
        "og_image_url": "",
    }


def build_locale_switch_url(request, locale_code: str) -> str:
    params = request.GET.copy()
    params["locale"] = locale_code
    encoded = params.urlencode()
    return f"{request.path}?{encoded}" if encoded else request.path


def serialize_list_item(snapshot: ContentPageSnapshot, locale: SiteLocale) -> dict:
    content_item = snapshot.content_item
    return {
        "id": str(content_item.id),
        "slug": snapshot.slug,
        "content_type": snapshot.page_kind,
        "source_name": snapshot.source_name_snapshot,
        "source_code": getattr(content_item.source, "source_code", None),
        "title": get_localized_value(locale, snapshot.title_zh_snapshot, snapshot.title_original_snapshot),
        "title_zh": snapshot.title_zh_snapshot,
        "title_original": snapshot.title_original_snapshot,
        "summary": get_localized_value(locale, snapshot.summary_zh_snapshot, content_item.summary_original),
        "summary_zh": snapshot.summary_zh_snapshot,
        "summary_original": content_item.summary_original,
        "cover_url": build_artifact_url(snapshot.cover_artifact),
        "published_at": serialize_datetime(snapshot.effective_published_at),
        "published_label": format_display_date(snapshot.effective_published_at, locale),
        "reading_mode_flags": {
            "supports_zh": bool(snapshot.body_zh_md_snapshot),
            "supports_bilingual": snapshot.supports_bilingual,
        },
        "url": f"/{'videos' if snapshot.page_kind == 'video' else 'articles'}/{snapshot.slug}",
    }


def serialize_detail(snapshot: ContentPageSnapshot, locale: SiteLocale, view_mode: str) -> dict:
    content_item = snapshot.content_item
    content_blocks_zh = markdown_to_blocks(snapshot.body_zh_md_snapshot)
    content_blocks_original = markdown_to_blocks(snapshot.body_original_md_snapshot)
    actual_view_mode = view_mode
    if actual_view_mode == "bilingual" and not snapshot.supports_bilingual:
        actual_view_mode = "zh"

    return {
        "id": str(content_item.id),
        "slug": snapshot.slug,
        "content_type": snapshot.page_kind,
        "source_name": snapshot.source_name_snapshot,
        "title_zh": snapshot.title_zh_snapshot,
        "title_original": snapshot.title_original_snapshot,
        "author_or_speaker": snapshot.author_or_speaker_snapshot,
        "published_at_source": serialize_datetime(snapshot.published_at_source_snapshot),
        "published_label": format_display_date(snapshot.published_at_source_snapshot, locale),
        "source_url": snapshot.source_url_snapshot,
        "canonical_url": snapshot.canonical_url_snapshot,
        "cover_url": build_artifact_url(snapshot.cover_artifact),
        "view_mode": actual_view_mode,
        "content_blocks_zh": content_blocks_zh,
        "content_blocks_original": content_blocks_original,
        "body_zh_md": snapshot.body_zh_md_snapshot,
        "body_original_md": snapshot.body_original_md_snapshot,
        "research_report_md": content_item.research_report_md,
        "disclaimer": snapshot.disclaimer_md_snapshot,
        "supports_bilingual": snapshot.supports_bilingual,
        "is_video": snapshot.page_kind == "video",
    }


def resolve_view_mode(request, snapshot: ContentPageSnapshot | None = None) -> str:
    value = request.GET.get("view", "zh")
    if value not in SUPPORTED_VIEW_MODES:
        value = "zh"
    if snapshot is not None and value == "bilingual" and not snapshot.supports_bilingual:
        return "zh"
    return value


def serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value if timezone.is_aware(value) else timezone.make_aware(value, dt_timezone.utc)
    return normalized.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")


def format_display_date(value: datetime | None, locale: SiteLocale) -> str:
    if value is None:
        return ""
    fmt = "%Y-%m-%d" if locale.is_chinese else "%b %d, %Y"
    return timezone.localtime(value).strftime(fmt)


def build_artifact_url(artifact) -> str | None:
    if artifact is None:
        return None
    storage_key = artifact.storage_key
    if storage_key.startswith("http://") or storage_key.startswith("https://"):
        return storage_key
    domain = settings.COS_CONFIG.get("domain", "")
    if domain:
        return f"https://{domain.strip('/')}/{storage_key.lstrip('/')}"
    return f"/media/{storage_key.lstrip('/')}"


def markdown_to_blocks(text: str | None) -> list[dict]:
    if not text:
        return []

    lines = text.splitlines()
    blocks: list[dict] = []
    paragraph_buffer: list[str] = []
    list_buffer: list[str] = []
    code_buffer: list[str] = []
    code_language = ""
    in_code = False

    def flush_paragraph():
        if paragraph_buffer:
            blocks.append({"type": "paragraph", "text": " ".join(paragraph_buffer).strip()})
            paragraph_buffer.clear()

    def flush_list():
        if list_buffer:
            blocks.append({"type": "list", "items": list(list_buffer)})
            list_buffer.clear()

    def flush_code():
        nonlocal code_language
        if code_buffer:
            blocks.append({"type": "code", "language": code_language, "text": "\n".join(code_buffer).rstrip()})
            code_buffer.clear()
            code_language = ""

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            flush_list()
            if in_code:
                flush_code()
                in_code = False
            else:
                code_language = stripped[3:].strip()
                in_code = True
            continue

        if in_code:
            code_buffer.append(line)
            continue

        if not stripped:
            flush_paragraph()
            flush_list()
            continue

        if re.fullmatch(r"-{3,}", stripped):
            flush_paragraph()
            flush_list()
            blocks.append({"type": "divider"})
            continue

        heading_match = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading_match:
            flush_paragraph()
            flush_list()
            blocks.append(
                {
                    "type": "heading",
                    "level": len(heading_match.group(1)),
                    "text": heading_match.group(2).strip(),
                }
            )
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            flush_list()
            blocks.append({"type": "quote", "text": stripped[1:].strip()})
            continue

        list_match = re.match(r"^[-*]\s+(.*)$", stripped)
        if list_match:
            flush_paragraph()
            list_buffer.append(list_match.group(1).strip())
            continue

        paragraph_buffer.append(stripped)

    flush_paragraph()
    flush_list()
    flush_code()
    return blocks


def build_archive_periods(queryset: QuerySet[ContentPageSnapshot], locale: SiteLocale) -> list[dict]:
    periods: dict[tuple[int, int], dict] = {}
    for snapshot in queryset[:120]:
        published_at = snapshot.effective_published_at
        key = (published_at.year, published_at.month)
        periods.setdefault(
            key,
            {
                "year": published_at.year,
                "month": published_at.month,
                "label": f"{published_at.year}-{published_at.month:02d}"
                if locale.is_chinese
                else published_at.strftime("%b %Y"),
            },
        )
    return list(periods.values())


def get_content_index_context(request, page: ListingPage, *, archive_mode: bool = False) -> dict:
    locale = resolve_locale(request)
    source = request.GET.get("source") or None
    content_type = request.GET.get("content_type") or None
    sort = request.GET.get("sort") or page.default_sort
    page_number = parse_int(request.GET.get("page"), default=1, minimum=1, maximum=9999)
    page_size = parse_int(request.GET.get("page_size"), default=page.page_size, minimum=1, maximum=100)
    date_from = parse_iso_date(request.GET.get("date_from"))
    date_to = parse_iso_date(request.GET.get("date_to"))
    q = request.GET.get("q") or None

    if archive_mode:
        year = request.GET.get("year")
        month = request.GET.get("month")
        if year and month:
            try:
                start = date(int(year), int(month), 1)
                if int(month) == 12:
                    end = date(int(year) + 1, 1, 1)
                else:
                    end = date(int(year), int(month) + 1, 1)
                date_from = start
                date_to = end.fromordinal(end.toordinal() - 1)
            except ValueError:
                pass

    queryset = query_public_snapshots(
        source=source,
        content_type=content_type,
        date_from=date_from,
        date_to=date_to,
        q=q,
        sort=sort,
    )
    paginated = paginate_queryset(queryset, page=page_number, page_size=page_size)

    return {
        **build_base_context(request, locale=locale),
        "page": page,
        "page_title": get_localized_value(locale, page.title_zh, page.title_en),
        "page_subtitle": get_localized_value(locale, page.subtitle_zh, page.subtitle_en),
        "items": [serialize_list_item(item, locale) for item in paginated["items"]],
        "pagination": paginated["pagination"],
        "filters": {
            "source": source or "",
            "content_type": content_type or "",
            "date_from": date_from.isoformat() if date_from else "",
            "date_to": date_to.isoformat() if date_to else "",
            "q": q or "",
            "sort": sort,
        },
        "empty_state_title": get_localized_value(locale, "暂时没有匹配内容", "No Matching Briefings Yet"),
        "empty_state_body": get_localized_value(
            locale,
            "可以尝试放宽筛选条件，或稍后再查看新发布内容。",
            "Try broadening the filters or come back later for newly published items.",
        ),
        "content_type_label": get_localized_value(locale, "内容类型", "Content Type"),
        "source_label": get_localized_value(locale, "来源", "Source"),
        "search_label": get_localized_value(locale, "搜索", "Search"),
        "archive_periods": build_archive_periods(queryset, locale) if archive_mode else [],
        "is_archive": archive_mode,
    }


def build_home_context(request) -> dict:
    locale = resolve_locale(request)
    page = get_home_page()
    items = query_public_snapshots(sort=ListingDefaultSort.PUBLISHED_DESC)[:6]
    return {
        **build_base_context(request, locale=locale),
        "page": page,
        "hero_title": get_localized_value(locale, page.hero_title_zh, page.hero_title_en),
        "hero_subtitle": get_localized_value(locale, page.hero_subtitle_zh, page.hero_subtitle_en),
        "page_title": get_localized_value(locale, page.title_zh, page.title_en),
        "featured_items": [serialize_list_item(item, locale) for item in items],
        "sections": {
            "latest": get_localized_value(locale, "最新发布", "Latest Briefings"),
            "empty": get_localized_value(locale, "内容正在准备中。", "Published content is on the way."),
            "articles": get_localized_value(locale, "文章", "Articles"),
            "videos": get_localized_value(locale, "视频", "Videos"),
            "view_all": get_localized_value(locale, "查看全部", "View All"),
        },
        "home_cta_placeholder": get_localized_value(
            locale,
            page.subscribe_placeholder_zh,
            page.subscribe_placeholder_en,
        ),
        "home_cta_button": get_localized_value(locale, page.primary_cta_text_zh, page.primary_cta_text_en),
        "seo_description": get_localized_value(
            locale,
            "TechBrief — 每日 AI 技术内容双语聚合平台，发现、翻译、发布精选技术文章与视频。",
            "TechBrief — Daily bilingual AI tech content aggregation. Curated articles and videos, translated and published.",
        ),
    }


def build_static_context(request, page: StaticPage) -> dict:
    locale = resolve_locale(request)
    return {
        **build_base_context(request, locale=locale),
        "page": page,
        "page_title": get_localized_value(locale, page.title_zh, page.title_en),
        "page_body_html": get_localized_value(locale, page.body_html_zh, page.body_html_en),
        "page_description": get_localized_value(locale, page.seo_description_zh, page.seo_description_en),
        "seo_description": get_localized_value(locale, page.seo_description_zh, page.seo_description_en),
    }


def build_detail_context(request, snapshot: ContentPageSnapshot) -> dict:
    locale = resolve_locale(request)
    view_mode = resolve_view_mode(request, snapshot)
    detail = serialize_detail(snapshot, locale, view_mode)
    return {
        **build_base_context(request, locale=locale),
        "page_title": get_localized_value(locale, detail["title_zh"], detail["title_original"]),
        "detail": detail,
        "view_mode": detail["view_mode"],
        "view_switch_urls": {
            "zh": build_mode_switch_url(request, "zh"),
            "bilingual": build_mode_switch_url(request, "bilingual"),
        },
        "labels": {
            "source": get_localized_value(locale, "来源", "Source"),
            "research": get_localized_value(locale, "研究补充", "Research Notes"),
            "disclaimer": get_localized_value(locale, "说明", "Disclaimer"),
            "subscribe": get_localized_value(locale, "获取更新", "Get Updates"),
            "mode_zh": get_localized_value(locale, "中文", "Chinese"),
            "mode_bilingual": get_localized_value(locale, "双语", "Bilingual"),
            "copy_zh": get_localized_value(locale, "复制", "Copy"),
            "copy_original": get_localized_value(locale, "复制原文", "Copy Original"),
        },
        "seo_description": get_localized_value(
            locale,
            detail.get("summary_zh", "") or detail.get("summary_original", ""),
            detail.get("summary_original", "") or detail.get("summary_zh", ""),
        )[:200],
        "og_image_url": detail.get("cover_url", ""),
    }


def build_mode_switch_url(request, mode: str) -> str:
    params = request.GET.copy()
    params["view"] = mode
    encoded = params.urlencode()
    return f"{request.path}?{encoded}" if encoded else request.path


def serialize_listing_payload(request) -> dict:
    locale = resolve_locale(request, use_query=False, use_cookie=False)
    page = parse_int(request.GET.get("page"), default=1, minimum=1, maximum=9999)
    page_size = parse_int(request.GET.get("page_size"), default=20, minimum=1, maximum=100)
    sort = request.GET.get("sort") or ListingDefaultSort.PUBLISHED_DESC
    queryset = query_public_snapshots(
        source=request.GET.get("source") or None,
        content_type=request.GET.get("content_type") or None,
        date_from=parse_iso_date(request.GET.get("date_from")),
        date_to=parse_iso_date(request.GET.get("date_to")),
        q=request.GET.get("q") or None,
        sort=sort,
    )
    paginated = paginate_queryset(queryset, page=page, page_size=page_size)
    return {
        "items": [serialize_list_item(item, locale) for item in paginated["items"]],
        "pagination": paginated["pagination"],
    }


def serialize_detail_payload(request, slug: str) -> dict:
    locale = resolve_locale(request, use_query=False, use_cookie=False)
    snapshot = get_detail_snapshot(slug)
    return serialize_detail(snapshot, locale, resolve_view_mode(request, snapshot))


def create_subscription(*, request, payload: dict) -> tuple[dict, int]:
    normalized_payload = dict(payload)
    normalized_payload["locale"] = normalize_locale(
        payload.get("locale") or resolve_locale(request, use_query=False).code
    )
    return subscribe_email(request=request, payload=normalized_payload)


def unsubscribe_subscription(*, request, token: str) -> tuple[dict, int]:
    return unsubscribe_by_token(request=request, token=token)


def build_unsubscribe_context(request, token: str) -> dict:
    locale = resolve_locale(request)
    payload, _ = unsubscribe_subscription(request=request, token=token)
    return {
        **build_base_context(request, locale=locale),
        "page_title": get_localized_value(locale, "已取消订阅", "Unsubscribed"),
        "unsubscribe_state": {
            "title": get_localized_value(locale, "退订已生效", "Unsubscribe Confirmed"),
            "body": get_localized_value(
                locale,
                "该邮箱将不再接收每日内容汇总。如需恢复，可在站内重新订阅。",
                "This email will no longer receive daily briefings. You can subscribe again anytime.",
            ),
            "status": payload["data"]["status"],
        },
    }
