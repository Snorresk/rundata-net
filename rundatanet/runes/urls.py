from django.conf import settings
from django.contrib.sitemaps.views import sitemap
from django.urls import path, register_converter
from django.views.generic import TemplateView

from . import views
from .sitemaps import AboutPageSitemap, InscriptionSitemap, MainPageSitemap, StaticViewSitemap


class SignatureConverter:
    """URL converter that accepts any characters except forward slash.

    This allows both normalized slugs (ol-1) and raw Unicode signatures
    (Öl 1, URL-encoded as %C3%96l%201) to match the same route.
    """

    regex = r"[^/]+"

    def to_python(self, value: str) -> str:
        return value

    def to_url(self, value: str) -> str:
        return value


register_converter(SignatureConverter, "sig")

sitemaps = {
    "static": StaticViewSitemap,
    "main": MainPageSitemap,
    "about": AboutPageSitemap,
    "inscriptions": InscriptionSitemap,
}

app_name = "runes"
urlpatterns = [
    path("", TemplateView.as_view(template_name="runes/index.html"), name="index"),
    path("ai-tester/", TemplateView.as_view(template_name="runes/ai_tester.html"), name="ai_tester"),
    path("v1", TemplateView.as_view(template_name="runes/index_old.html"), name="index_v1"),
    # path('master', views.master),
    path("about/", TemplateView.as_view(template_name="runes/about.html"), name="about"),
    path("references/", TemplateView.as_view(template_name="runes/references.html"), name="references"),
    path("eda/", TemplateView.as_view(template_name="runes/eda.html"), name="eda"),
    path("inscription/<sig:slug>/", views.inscription_detail, name="inscription_detail"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
        name="robots_txt",
    ),
]

if settings.DEBUG:
    urlpatterns.append(
        path(
            "mobile-db/",
            TemplateView.as_view(template_name="runes/index.html"),
            name="mobile_db",
        )
    )
