import sys
from unittest.mock import MagicMock

# Mock missing dependencies before importing the module under test
# This is necessary because the environment lacks the actual packages.
mock_httpx = MagicMock()
sys.modules["httpx"] = mock_httpx

mock_rapidfuzz = MagicMock()
sys.modules["rapidfuzz"] = mock_rapidfuzz
sys.modules["rapidfuzz.fuzz"] = MagicMock()

mock_bs4 = MagicMock()
sys.modules["bs4"] = mock_bs4

mock_curl_cffi = MagicMock()
sys.modules["curl_cffi"] = mock_curl_cffi
sys.modules["curl_cffi.requests"] = MagicMock()

import pytest
# Absolute import for better reliability across different test runners
from services.pipeline import format_best_result

def test_format_best_result_pdf_happy_path():
    best = {
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "pdf_url": "http://example.com/gatsby.pdf",
        "epub_url": "http://example.com/gatsby.epub",
        "source": "Anna's Archive"
    }
    result = format_best_result(best, "pdf")
    assert result["status"] == "success"
    assert result["book_name"] == "The Great Gatsby by F. Scott Fitzgerald"
    assert result["file_url"] == "http://example.com/gatsby.pdf"
    assert result["extension"] == "pdf"
    assert result["source"] == "Anna's Archive"

def test_format_best_result_epub_happy_path():
    best = {
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "pdf_url": "http://example.com/gatsby.pdf",
        "epub_url": "http://example.com/gatsby.epub",
        "source": "Anna's Archive"
    }
    result = format_best_result(best, "epub")
    assert result["file_url"] == "http://example.com/gatsby.epub"
    assert result["extension"] == "epub"

def test_format_best_result_any_prefers_epub():
    best = {
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "pdf_url": "http://example.com/gatsby.pdf",
        "epub_url": "http://example.com/gatsby.epub",
        "source": "Anna's Archive"
    }
    result = format_best_result(best, "any")
    assert result["file_url"] == "http://example.com/gatsby.epub"
    assert result["extension"] == "epub"

def test_format_best_result_any_falls_back_to_pdf():
    best = {
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "pdf_url": "http://example.com/gatsby.pdf",
        "source": "Anna's Archive"
    }
    result = format_best_result(best, "any")
    assert result["file_url"] == "http://example.com/gatsby.pdf"
    assert result["extension"] == "pdf"

def test_format_best_result_requested_pdf_but_only_epub_available():
    best = {
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "epub_url": "http://example.com/gatsby.epub",
        "source": "Anna's Archive"
    }
    result = format_best_result(best, "pdf")
    assert result["file_url"] == "http://example.com/gatsby.epub"
    assert result["extension"] == "epub"

def test_format_best_result_requested_epub_but_only_pdf_available():
    best = {
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "pdf_url": "http://example.com/gatsby.pdf",
        "source": "Anna's Archive"
    }
    result = format_best_result(best, "epub")
    assert result["file_url"] == "http://example.com/gatsby.pdf"
    assert result["extension"] == "pdf"

def test_format_best_result_missing_author():
    best = {
        "title": "The Great Gatsby",
        "pdf_url": "http://example.com/gatsby.pdf",
        "source": "Anna's Archive"
    }
    result = format_best_result(best, "pdf")
    assert result["book_name"] == "The Great Gatsby"

def test_format_best_result_missing_title():
    best = {
        "author": "F. Scott Fitzgerald",
        "pdf_url": "http://example.com/gatsby.pdf",
        "source": "Anna's Archive"
    }
    result = format_best_result(best, "pdf")
    assert result["book_name"] == "Unknown Book by F. Scott Fitzgerald"

def test_format_best_result_no_urls_available():
    best = {
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "source": "Anna's Archive"
    }
    result = format_best_result(best, "pdf")
    assert result["file_url"] is None
    assert result["extension"] == "pdf"
