from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.models import Page


class ListingPageCode(models.TextChoices):
    ARTICLES = "articles", "Articles"
    ARCHIVE = "archive", "Archive"


class ListingDefaultSort(models.TextChoices):
    PUBLISHED_DESC = "published_desc", "Published Desc"
    PUBLISHED_ASC = "published_asc", "Published Asc"
    UPDATED_DESC = "updated_desc", "Updated Desc"


class StaticPageCode(models.TextChoices):
    ABOUT = "about", "About"
    PRIVACY = "privacy", "Privacy"
    TERMS = "terms", "Terms"


class TechBriefBasePage(Page):
    title_zh = models.CharField(max_length=255)
    title_en = models.CharField(max_length=255)
    is_published = models.BooleanField(default=True)

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("title_zh"),
                FieldPanel("title_en"),
            ],
            heading="Bilingual Titles",
        ),
        FieldPanel("is_published"),
    ]

    class Meta:
        abstract = True


class HomePage(TechBriefBasePage):
    hero_title_zh = models.CharField(max_length=255)
    hero_title_en = models.CharField(max_length=255)
    hero_subtitle_zh = models.TextField()
    hero_subtitle_en = models.TextField()
    subscribe_placeholder_zh = models.CharField(max_length=128, default="输入邮箱地址")
    subscribe_placeholder_en = models.CharField(max_length=128, default="Enter your email")
    primary_cta_text_zh = models.CharField(max_length=64, default="立即订阅")
    primary_cta_text_en = models.CharField(max_length=64, default="Subscribe")

    parent_page_types = ["wagtailcore.Page"]
    subpage_types = ["web.ListingPage", "web.StaticPage"]
    max_count = 1
    template = "web/home_page.html"

    content_panels = TechBriefBasePage.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("hero_title_zh"),
                FieldPanel("hero_title_en"),
                FieldPanel("hero_subtitle_zh"),
                FieldPanel("hero_subtitle_en"),
            ],
            heading="Hero Copy",
        ),
        MultiFieldPanel(
            [
                FieldPanel("subscribe_placeholder_zh"),
                FieldPanel("subscribe_placeholder_en"),
                FieldPanel("primary_cta_text_zh"),
                FieldPanel("primary_cta_text_en"),
            ],
            heading="Subscription CTA",
        ),
    ]

    class Meta:
        db_table = "tb_home_page"
        verbose_name = "Home Page"
        verbose_name_plural = "Home Pages"
        indexes = [
            models.Index(fields=["is_published"], name="idx_tb_home_page_is_published"),
        ]


class ListingPage(TechBriefBasePage):
    page_code = models.CharField(max_length=32, choices=ListingPageCode.choices, unique=True)
    subtitle_zh = models.TextField(blank=True)
    subtitle_en = models.TextField(blank=True)
    default_sort = models.CharField(
        max_length=32,
        choices=ListingDefaultSort.choices,
        default=ListingDefaultSort.PUBLISHED_DESC,
    )
    default_filters_json = models.JSONField(null=True, blank=True)
    enable_date_filter = models.BooleanField(default=True)
    page_size = models.PositiveSmallIntegerField(
        default=20,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )

    parent_page_types = ["web.HomePage"]
    subpage_types: list[str] = []
    template = "web/listing_page.html"

    content_panels = TechBriefBasePage.content_panels + [
        FieldPanel("page_code"),
        FieldPanel("subtitle_zh"),
        FieldPanel("subtitle_en"),
        FieldPanel("default_sort"),
        FieldPanel("default_filters_json"),
        FieldPanel("enable_date_filter"),
        FieldPanel("page_size"),
    ]

    class Meta:
        db_table = "tb_listing_page"
        verbose_name = "Listing Page"
        verbose_name_plural = "Listing Pages"


class StaticPage(TechBriefBasePage):
    page_code = models.CharField(max_length=32, choices=StaticPageCode.choices, unique=True)
    body_md_zh = models.TextField()
    body_md_en = models.TextField()
    body_html_zh = models.TextField(blank=True)
    body_html_en = models.TextField(blank=True)
    seo_title_zh = models.CharField(max_length=255, blank=True)
    seo_title_en = models.CharField(max_length=255, blank=True)
    seo_description_zh = models.CharField(max_length=512, blank=True)
    seo_description_en = models.CharField(max_length=512, blank=True)

    parent_page_types = ["web.HomePage"]
    subpage_types: list[str] = []
    template = "web/static_page.html"

    content_panels = TechBriefBasePage.content_panels + [
        FieldPanel("page_code"),
        FieldPanel("body_md_zh"),
        FieldPanel("body_md_en"),
        FieldPanel("body_html_zh"),
        FieldPanel("body_html_en"),
        MultiFieldPanel(
            [
                FieldPanel("seo_title_zh"),
                FieldPanel("seo_title_en"),
                FieldPanel("seo_description_zh"),
                FieldPanel("seo_description_en"),
            ],
            heading="Localized SEO",
        ),
    ]

    class Meta:
        db_table = "tb_static_page"
        verbose_name = "Static Page"
        verbose_name_plural = "Static Pages"
