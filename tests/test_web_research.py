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


def test_google_news_uses_india_locale_for_indian_locations(monkeypatch):
    captured = {}

    class XmlResponse:
        status_code = 200
        content = b"<rss><channel></channel></rss>"

        def raise_for_status(self):
            return None

    def get(url, **kwargs):
        captured.update(url=url, **kwargs)
        return XmlResponse()

    monkeypatch.setattr(web_research.requests, "get", get)
    web_research._search_google_news_rss.__wrapped__("Noida news when:7d")

    assert captured["params"]["hl"] == "en-IN"
    assert captured["params"]["gl"] == "IN"
    assert captured["params"]["ceid"] == "IN:en"
    assert captured["params"]["q"] == "Noida news when:7d"


def test_news_search_focuses_each_named_location_and_requires_fresh_dated_sources(monkeypatch):
    calls = []

    def search(query, **kwargs):
        calls.append((query, kwargs))
        return [{
            "title": f"Latest reports for {query}",
            "snippet": "A dated local report.",
            "url": f"https://example.com/{query.split()[0].casefold()}",
            "published_at": "Sat, 24 Oct 2026 09:00:00 GMT",
            "search_provider": "Google News",
        }]

    monkeypatch.setattr(web_research, "search_research_sources", search)
    results = web_research.search_news_sources("Summarize all news of Uttar Pradesh, Noida", fresh=True)

    assert [query for query, _ in calls] == ["Uttar Pradesh news", "Noida news"]
    assert all(kwargs["fresh"] is True for _, kwargs in calls)
    assert all(kwargs["news_window_days"] == 7 for _, kwargs in calls)
    assert len(results) == 2


def test_recent_news_search_discards_undated_and_stale_results(monkeypatch):
    captured = {}

    def google_news(query):
        captured["query"] = query
        return (
            ("Noida report from today", "Today’s local report.", "https://example.com/today", "Sat, 24 Oct 2026 09:00:00 GMT"),
            ("Noida report from summer", "An old report.", "https://example.com/old", "Mon, 03 Aug 2026 09:00:00 GMT"),
            ("Noida report without a date", "No publication date.", "https://example.com/undated", ""),
        )

    monkeypatch.setattr(web_research, "_search_google_news_rss", google_news)
    results = web_research.search_research_sources(
        "Noida news",
        fresh=True,
        relevance_query="Noida",
        news_window_days=7,
    )

    assert captured["query"] == "Noida news when:7d"
    assert [item["url"] for item in results] == ["https://example.com/today"]


def test_search_reports_provider_outage_when_every_backend_fails(monkeypatch):
    def unavailable(query):
        raise requests.ConnectionError("search backend unreachable")

    monkeypatch.setattr(web_research, "_search_duckduckgo", unavailable)
    monkeypatch.setattr(web_research, "_search_bing_rss", unavailable)
    monkeypatch.setattr(web_research, "_search_google_news_rss", unavailable)

    with pytest.raises(web_research.WebResearchError, match="temporarily unreachable"):
        web_research.search_research_sources("NASA Artemis", fresh=True)


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


def test_normal_web_search_cleans_task_instructions_before_search(monkeypatch):
    calls = []
    source = {
        "title": "NASA mission update",
        "snippet": "The mission update is published by NASA.",
        "url": "https://www.nasa.gov/example",
        "published_at": "Sat, 24 Oct 2026 09:00:00 GMT",
        "search_provider": "Bing",
    }

    def search(query, **kwargs):
        calls.append((query, kwargs))
        return [source]

    monkeypatch.setattr(web_research, "search_research_sources", search)
    results = web_research.search_web_results("web search NASA mission")

    assert calls[0][0] == "NASA mission"
    assert calls[0][1]["relevance_query"] == "NASA mission"
    assert results[0]["title"] == "NASA mission update"


def test_web_context_marks_retrieved_results_as_evidence_and_preserves_metadata(monkeypatch):
    source = {
        "title": "Noida local report",
        "snippet": "A report published today.",
        "url": "https://example.com/noida-report",
        "published_at": "Sat, 24 Oct 2026 09:00:00 GMT",
        "search_provider": "Google News",
    }
    monkeypatch.setattr(web_research, "search_web_results", lambda query: [source])
    monkeypatch.setattr(web_research, "fetch_research_page", lambda url: {
        "url": url,
        "status": "fetched",
        "title": "Noida local report",
        "text": "A report published today about Noida.",
    })

    context, sources = web_research.retrieve_web_context(
        "Summarize all news of Noida today",
        {"requires_web": True},
    )

    assert "past 1 days" in context
    assert "Never claim that web or current-information access is unavailable" in context
    assert "Publication date: Sat, 24 Oct 2026 09:00:00 GMT" in context
    assert sources[0]["search_provider"] == "Google News"


def test_unrelated_bro_youtube_result_is_not_attached_to_ai_ethics_answer(monkeypatch):
    title = "Theme of BRO Lyrical | BRO Telugu Movie | Pawan Kalyan - YouTube"
    url = "https://www.youtube.com/watch?v=bro-theme"
    monkeypatch.setattr(web_research, "search_web_results", lambda query: [{
        "title": title,
        "snippet": "Official lyrical theme song from the Telugu movie BRO.",
        "url": url,
        "search_provider": "Bing",
    }])

    context, sources = web_research.retrieve_web_context(
        "Would you sacrifice your AI databases to save five people?",
        {"requires_web": True},
    )

    assert sources == []
    assert title not in context
    assert url not in context
    assert "No result's source text passed the relevance check" in context


def test_relevant_youtube_citation_is_preserved_when_video_supports_query(monkeypatch):
    title = "Theme of BRO Lyrical | BRO Telugu Movie | Pawan Kalyan - YouTube"
    url = "https://www.youtube.com/watch?v=bro-theme"
    monkeypatch.setattr(web_research, "search_web_results", lambda query: [{
        "title": title,
        "snippet": "Official lyrical theme song from the Telugu movie BRO.",
        "url": url,
        "search_provider": "DuckDuckGo",
    }])
    monkeypatch.setattr(web_research, "fetch_research_page", lambda page_url: {
        "url": page_url,
        "status": "fetched",
        "title": title,
        "text": "Theme of BRO is a Telugu movie song featuring Pawan Kalyan.",
    })

    context, sources = web_research.retrieve_web_context(
        "Find the official BRO theme lyric video by Pawan Kalyan",
        {"requires_web": True},
    )

    assert [source["url"] for source in sources] == [url]
    assert sources[0]["title"] == title
    assert title in context
    assert "Pawan Kalyan" in context


def test_search_excerpt_cannot_override_unrelated_fetched_page_content(monkeypatch):
    url = "https://example.com/ai-database-discussion"
    monkeypatch.setattr(web_research, "search_web_results", lambda query: [{
        "title": "AI database sacrifice discussion",
        "snippet": "Would sacrificing an AI database save five people?",
        "url": url,
        "search_provider": "Bing",
    }])
    monkeypatch.setattr(web_research, "fetch_research_page", lambda page_url: {
        "url": page_url,
        "status": "fetched",
        "title": "Theme of BRO Lyrical | BRO Telugu Movie | Pawan Kalyan - YouTube",
        "text": "Official lyrical theme song from the Telugu movie BRO.",
    })

    context, sources = web_research.retrieve_web_context(
        "Would you sacrifice your AI databases to save five people?",
        {"requires_web": True},
    )

    assert sources == []
    assert url not in context


def test_web_source_metadata_is_scoped_to_each_consecutive_request(monkeypatch):
    nasa_url = "https://example.com/nasa-artemis"
    video_url = "https://www.youtube.com/watch?v=bro-theme"
    results_by_query = {
        "NASA Artemis schedule": [{
            "title": "NASA Artemis III schedule",
            "snippet": "NASA published the Artemis mission schedule.",
            "url": nasa_url,
            "search_provider": "Bing",
        }],
        "Pawan Kalyan BRO theme song": [{
            "title": "Theme of BRO Lyrical | BRO Telugu Movie | Pawan Kalyan - YouTube",
            "snippet": "Official theme song from the Telugu movie BRO.",
            "url": video_url,
            "search_provider": "DuckDuckGo",
        }],
    }
    pages_by_url = {
        nasa_url: {
            "url": nasa_url,
            "status": "fetched",
            "title": "NASA Artemis III schedule",
            "text": "NASA published the Artemis mission schedule.",
        },
        video_url: {
            "url": video_url,
            "status": "fetched",
            "title": "Theme of BRO Lyrical | BRO Telugu Movie | Pawan Kalyan - YouTube",
            "text": "Official theme song from the Telugu movie BRO featuring Pawan Kalyan.",
        },
    }
    monkeypatch.setattr(web_research, "search_web_results", lambda query: results_by_query[query])
    monkeypatch.setattr(web_research, "fetch_research_page", lambda url: pages_by_url[url])

    nasa_context, nasa_sources = web_research.retrieve_web_context(
        "NASA Artemis schedule", {"requires_web": True}
    )
    video_context, video_sources = web_research.retrieve_web_context(
        "Pawan Kalyan BRO theme song", {"requires_web": True}
    )

    assert [source["url"] for source in nasa_sources] == [nasa_url]
    assert [source["url"] for source in video_sources] == [video_url]
    assert nasa_url in nasa_context and video_url not in nasa_context
    assert video_url in video_context and nasa_url not in video_context


def test_web_context_with_no_results_has_no_citation_sources(monkeypatch):
    monkeypatch.setattr(web_research, "search_web_results", lambda query: [])

    context, sources = web_research.retrieve_web_context(
        "Current Artemis launch status", {"requires_web": True}
    )

    assert sources == []
    assert "No result's source text passed the relevance check" in context


def test_research_relevance_rejects_queries_with_no_topic_terms():
    assert web_research._research_relevance(
        "latest news", "Theme of BRO Lyrical", "Official Telugu movie song"
    ) == 0.0


def test_news_query_cleaning_preserves_noida_spelling():
    assert web_research.focus_search_query("Summarize all news of Noida today") == "Noida"


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
