from __future__ import annotations

from django.urls import include, path, reverse_lazy
from wagtail import hooks
from wagtail.admin.menu import MenuItem


@hooks.register("register_admin_urls")
def register_admin_urls():
    return [
        path(
            "techbrief/",
            include(("techbrief.apps.admin_console.urls", "admin_console"), namespace="admin_console"),
        )
    ]


@hooks.register("register_admin_menu_item")
def register_admin_menu_item():
    return MenuItem("TechBrief", reverse_lazy("admin_console:dashboard"), icon_name="home", order=200)
