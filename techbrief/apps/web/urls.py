from __future__ import annotations

from django.urls import path

from techbrief.apps.web import views

urlpatterns = [
    path("", views.home_view, name="public-home"),
    path("articles", views.articles_view, name="public-articles"),
    path("archive", views.archive_view, name="public-archive"),
    path("articles/<slug:slug>", views.article_detail_view, name="public-article-detail"),
    path("videos/<slug:slug>", views.video_detail_view, name="public-video-detail"),
    path("about", views.static_page_view, {"page_code": "about"}, name="public-about"),
    path("privacy", views.static_page_view, {"page_code": "privacy"}, name="public-privacy"),
    path("terms", views.static_page_view, {"page_code": "terms"}, name="public-terms"),
    path("unsubscribe/<str:token>", views.unsubscribe_page_view, name="public-unsubscribe"),
    path("api/public/content-items", views.public_content_items_api, name="public-api-content-items"),
    path(
        "api/public/content-items/<slug:slug>",
        views.public_content_item_detail_api,
        name="public-api-content-item-detail",
    ),
    path("api/public/subscriptions", views.create_subscription_api, name="public-api-subscriptions"),
    path(
        "api/public/subscriptions/unsubscribe",
        views.unsubscribe_subscription_api,
        name="public-api-subscriptions-unsubscribe",
    ),
    path("api/public/tracking-pixel", views.tracking_pixel_view, name="public-tracking-pixel"),
]
