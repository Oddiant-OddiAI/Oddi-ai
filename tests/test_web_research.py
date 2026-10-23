import xml.etree.ElementTree as ET
import json

import pytest
import requests

from app import web_research


def test_source_url_validation_preserves_path_and_query(monkeypatch):
    monkeypatch.setattr(
        web_research.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )

    normalized = web_research._validated_public_source_url("https://example.com/research?q=flying-car")

    assert normalized == "https://example.com/research?q=flying-car"


def test_duckduckgo_http_202_challenge_is_reported_as_unavailable(monkeypatch):
    class ChallengeResponse:
        status_code = 202
        text = "challenge"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(web_research.requests, "get", lambda *args, **kwargs: ChallengeResponse())
    query = "duckduckgo-challenge-regression-test"
    web_research._search_duckduckgo.cache_clear()

    with pytest.raises(requests.HTTPError, match="HTTP 202"):
        web_research._search_duckduckgo(query)


def test_google_news_rss_returns_source_url_and_publication_date(monkeypatch):
    xml = ET.Element("rss")
    channel = ET.SubElement(xml, "channel")
    item = ET.SubElement(channel, "item")
    ET.SubElement(item, "title").text = "FAA explains powered-lift rules"
    ET.SubElement(item, "link").text = "https://news.google.com/rss/articles/example"
    ET.SubElement(item, "description").text = "<a>FAA rules</a> &nbsp; source text"
    ET.SubElement(item, "pubDate").text = "Wed, 21 Oct 2026 09:00:01 GMT"

    class XmlResponse:
        status_code = 200
        content = ET.tostring(xml)

        def raise_for_status(self):
            return None

    monkeypatch.setattr(web_research.requests, "get", lambda *args, **kwargs: XmlResponse())
    web_research._search_google_news_rss.cache_clear()

    results = web_research._search_google_news_rss("powered lift FAA")

    assert results == ((
        "FAA explains powered-lift rules",
        "FAA rules source text",
        "https://news.google.com/rss/articles/example",
        "Wed, 21 Oct 2026 09:00:01 GMT",
    ),)


def test_research_search_drops_unrelated_engine_results_and_keeps_relevant_news(monkeypatch):
    monkeypatch.setattr(web_research, "_search_duckduckgo", lambda query: ())
    monkeypatch.setattr(
        web_research,
        "_search_bing_rss",
        lambda query: (("Marathi typing practice", "Typing tests and keyboard lessons", "https://example.com/typing"),),
    )
    monkeypatch.setattr(
        web_research,
        "_search_google_news_rss",
        lambda query: ((
            "Tesla Roadster flying car reveal",
            "Recent product announcement.",
            "https://example.com/tesla-roadster",
            "Wed, 21 Oct 2026 09:00:01 GMT",
        ),),
    )

    results = web_research.search_research_sources("Flying cars exist today? Tesla Roadster", fresh=True)

    assert len(results) == 1
    assert results[0]["search_provider"] == "Google News"
    assert results[0]["published_at"] == "Wed, 21 Oct 2026 09:00:01 GMT"


def test_google_news_article_url_resolves_to_a_validated_publisher_url(monkeypatch):
    publisher_url = "https://publisher.example/article"
    frame = ["wrb.fr", "Fbv4je", json.dumps(["garturlres", publisher_url])]

    class Response:
        status_code = 200
        headers = {}
        text = '<div data-n-a-sg="signature" data-n-a-ts="123456"></div>'

        def raise_for_status(self):
            return None

        def close(self):
            return None

    class ResolverResponse(Response):
        text = ")]}'\n\n" + json.dumps([frame])

    class Session:
        trust_env = True

        def get(self, url, **kwargs):
            assert url.startswith("https://news.google.com/rss/articles/opaque-id?")
            assert kwargs["allow_redirects"] is False
            return Response()

        def post(self, url, **kwargs):
            assert url.startswith("https://news.google.com/_/DotsSplashUi/data/batchexecute")
            assert kwargs["headers"]["Content-Type"] == "application/x-www-form-urlencoded;charset=UTF-8"
            return ResolverResponse()

        def close(self):
            return None

    monkeypatch.setattr(web_research.requests, "Session", Session)
    monkeypatch.setattr(web_research, "_validated_public_source_url", lambda url: url)
    web_research._resolve_google_news_url.cache_clear()

    resolved = web_research._resolve_google_news_url("https://news.google.com/rss/articles/opaque-id?oc=5")

    assert resolved == publisher_url
