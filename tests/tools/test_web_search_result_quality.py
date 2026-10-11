"""Blank search records must never appear as usable source citations."""

import sys
from unittest.mock import MagicMock

from openjarvis.tools.web_search import WebSearchTool


def test_duckduckgo_skips_blank_and_invalid_sources_and_supports_url_key(monkeypatch):
    module = MagicMock()
    module.DDGS.return_value.text.return_value = [
        {"title": "", "href": "", "body": ""},
        None,
        {"title": "unsafe", "href": "javascript:alert(1)"},
        {"title": "invalid host", "href": "https://[broken"},
        {
            "title": "Ollama FAQ",
            "url": "https://docs.ollama.com/faq",
            "description": "Local model memory settings",
        },
    ]
    monkeypatch.setitem(sys.modules, "ddgs", module)
    result = WebSearchTool(engine="duckduckgo").execute(query="public test query")
    assert result.success
    assert result.content.count("Source:") == 1
    assert "Source: https://docs.ollama.com/faq" in result.content
    assert "Local model memory settings" in result.content
    assert "unsafe" not in result.content


def test_blank_results_are_reported_as_no_results(monkeypatch):
    module = MagicMock()
    module.DDGS.return_value.text.return_value = [{"title": "", "href": "", "body": ""}]
    monkeypatch.setitem(sys.modules, "ddgs", module)
    result = WebSearchTool(engine="duckduckgo").execute(query="public test query")
    assert result.content == "No results found."
