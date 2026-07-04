"""
Tests for the strategy templates HTML gallery generator.
"""

from __future__ import annotations

from polymind.web.gallery import generate_gallery_html


class TestGalleryGenerator:
    def test_generate_returns_html(self):
        html = generate_gallery_html()
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html

    def test_contains_template_names(self):
        html = generate_gallery_html()
        assert "amm_concentrated" in html
        assert "bands_multi" in html
        assert "classic_mm_simple" in html
        assert "maker_rebate_pair" in html

    def test_contains_css(self):
        html = generate_gallery_html()
        assert ".card" in html
        assert ".modal" in html
        assert "grid" in html

    def test_contains_javascript(self):
        html = generate_gallery_html()
        assert "function showDetails" in html
        assert "function hideDetails" in html

    def test_contains_all_templates(self):
        from polymind.templates import TemplateLibrary

        lib = TemplateLibrary()
        html = generate_gallery_html()
        for t in lib.list_templates():
            assert t.name in html, f"Missing template: {t.name}"

    def test_modal_has_deploy_button(self):
        html = generate_gallery_html()
        assert "Copy deploy command" in html
        assert "clipboard" in html
