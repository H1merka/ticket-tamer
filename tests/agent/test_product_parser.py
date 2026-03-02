"""Tests for agent/product_parser.py — eriskip.com parser helpers."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from agent.product_parser import (
    classify_file,
    _is_catalog_page,
    _extract_name,
    _extract_description,
    _extract_specifications,
    _extract_files,
    _find_next_page,
)


# ---------------------------------------------------------------------------
# classify_file
# ---------------------------------------------------------------------------


class TestClassifyFile:
    def test_manual(self):
        assert classify_file("https://eriskip.com/docs/manual_dgs.pdf") == "manual"

    def test_manual_russian(self):
        assert classify_file("https://eriskip.com/docs/руководство_эксплуатации.pdf") == "manual"

    def test_certificate(self):
        assert classify_file("https://eriskip.com/docs/certificate_atex.pdf") == "certificate"

    def test_scheme(self):
        assert classify_file("https://eriskip.com/docs/схема_подключения.pdf") == "scheme"

    def test_firmware(self):
        assert classify_file("https://eriskip.com/docs/firmware_v2.zip") == "firmware"

    def test_software(self):
        assert classify_file("https://eriskip.com/docs/software_dgs_ble.exe") == "software"

    def test_datasheet(self):
        assert classify_file("https://eriskip.com/docs/datasheet_sensor.pdf") == "datasheet"

    def test_archive(self):
        assert classify_file("https://eriskip.com/docs/package.zip") == "archive"

    def test_cad_drawing(self):
        assert classify_file("https://eriskip.com/docs/sensor.dwg") == "cad_drawing"

    def test_unknown_defaults_to_other(self):
        assert classify_file("https://eriskip.com/docs/readme.txt") == "other"


# ---------------------------------------------------------------------------
# _is_catalog_page
# ---------------------------------------------------------------------------


class TestIsCatalogPage:
    def test_products_page(self):
        assert _is_catalog_page("https://eriskip.com/ru/products") is True

    def test_products_with_pagination(self):
        assert _is_catalog_page("https://eriskip.com/ru/products?page=2") is True

    def test_catalog_page(self):
        assert _is_catalog_page("https://eriskip.com/ru/catalog") is True

    def test_product_detail_page(self):
        assert _is_catalog_page("https://eriskip.com/ru/product/dgs-210") is False

    def test_category_page(self):
        assert _is_catalog_page("https://eriskip.com/ru/category/sensors") is True


# ---------------------------------------------------------------------------
# _extract_name
# ---------------------------------------------------------------------------


class TestExtractName:
    def test_h1_tag(self):
        soup = BeautifulSoup("<html><h1>СЕНСОН-СВ-5023</h1></html>", "html.parser")
        assert _extract_name(soup) == "СЕНСОН-СВ-5023"

    def test_h2_fallback(self):
        soup = BeautifulSoup("<html><h2>ДГС ЭРИС-210</h2></html>", "html.parser")
        assert _extract_name(soup) == "ДГС ЭРИС-210"

    def test_title_fallback(self):
        soup = BeautifulSoup("<html><title>Sensor Page</title></html>", "html.parser")
        assert _extract_name(soup) == "Sensor Page"

    def test_no_heading(self):
        soup = BeautifulSoup("<html><p>text</p></html>", "html.parser")
        assert _extract_name(soup) == ""


# ---------------------------------------------------------------------------
# _extract_description
# ---------------------------------------------------------------------------


class TestExtractDescription:
    def test_description_div(self):
        html = '<div class="product-desc">Газоанализатор</div>'
        soup = BeautifulSoup(html, "html.parser")
        assert _extract_description(soup) == "Газоанализатор"

    def test_p_fallback(self):
        soup = BeautifulSoup("<html><p>Описание прибора</p></html>", "html.parser")
        assert _extract_description(soup) == "Описание прибора"

    def test_no_description(self):
        soup = BeautifulSoup("<html><div></div></html>", "html.parser")
        assert _extract_description(soup) == ""


# ---------------------------------------------------------------------------
# _extract_specifications
# ---------------------------------------------------------------------------


class TestExtractSpecifications:
    def test_table_specs(self):
        html = """
        <table>
            <tr><td>Масса</td><td>1.5 кг</td></tr>
            <tr><td>Каналы</td><td>4</td></tr>
        </table>
        """
        soup = BeautifulSoup(html, "html.parser")
        specs = _extract_specifications(soup)
        assert specs["Масса"] == "1.5 кг"
        assert specs["Каналы"] == "4"

    def test_ul_specs(self):
        html = '<ul class="spec-list"><li>Масса: 1.5 кг</li></ul>'
        soup = BeautifulSoup(html, "html.parser")
        specs = _extract_specifications(soup)
        assert specs["Масса"] == "1.5 кг"

    def test_empty_specs(self):
        soup = BeautifulSoup("<html><p>No specs</p></html>", "html.parser")
        specs = _extract_specifications(soup)
        assert specs == {}


# ---------------------------------------------------------------------------
# _extract_files
# ---------------------------------------------------------------------------


class TestExtractFiles:
    def test_pdf_link(self):
        html = '<a href="/docs/manual.pdf">Руководство</a>'
        soup = BeautifulSoup(html, "html.parser")
        files = _extract_files(soup, "https://eriskip.com/ru/product/x")
        assert len(files) == 1
        assert files[0]["name"] == "Руководство"
        assert files[0]["url"].endswith("/docs/manual.pdf")

    def test_dedup_urls(self):
        html = """
        <a href="/docs/manual.pdf">Link 1</a>
        <a href="/docs/manual.pdf">Link 2</a>
        """
        soup = BeautifulSoup(html, "html.parser")
        files = _extract_files(soup, "https://eriskip.com/ru/product/x")
        assert len(files) == 1

    def test_no_file_links(self):
        soup = BeautifulSoup("<a href='/page'>text</a>", "html.parser")
        files = _extract_files(soup, "https://eriskip.com/ru/product/x")
        assert files == []


# ---------------------------------------------------------------------------
# _find_next_page
# ---------------------------------------------------------------------------


class TestFindNextPage:
    def test_text_link_next(self):
        html = '<a href="/ru/products?page=2">Следующая</a>'
        soup = BeautifulSoup(html, "html.parser")
        nxt = _find_next_page(soup, "https://eriskip.com/ru/products")
        assert nxt is not None
        assert "page=2" in nxt

    def test_no_next_page(self):
        soup = BeautifulSoup("<html><p>end</p></html>", "html.parser")
        nxt = _find_next_page(soup, "https://eriskip.com/ru/products")
        assert nxt is None

    def test_query_string_pagination(self):
        html = '<a href="/ru/products?page=3">3</a>'
        soup = BeautifulSoup(html, "html.parser")
        nxt = _find_next_page(soup, "https://eriskip.com/ru/products?page=2")
        assert nxt is not None
        assert "page=3" in nxt
