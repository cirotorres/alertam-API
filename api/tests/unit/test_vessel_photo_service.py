import httpx
import pytest

from app.core.errors import VesselPhotoUnavailableError
from app.services.vessel_photo_service import VesselPhotoService


def _commons_page(title: str, thumb: str = "https://upload.wikimedia.org/ship.jpg"):
    return {
        "title": title,
        "imageinfo": [{
            "thumburl": thumb,
            "descriptionurl": f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}",
            "extmetadata": {
                "Artist": {"value": "<b>Jane Doe</b>"},
                "LicenseShortName": {"value": "CC BY-SA 4.0"},
            },
        }],
    }


def test_commons_search_prefers_exact_imo_title_and_skips_wikidata():
    calls = []

    def get_json(url, params, headers):
        calls.append((url, params, headers))
        assert "commons.wikimedia.org" in url
        return {
            "query": {
                "pages": {
                    "1": _commons_page("File:Front view of the Nike of Samothrace.jpg"),
                    "2": _commons_page(
                        "File:Nike IMO 9431032 T Hamburg.jpg",
                        "https://upload.wikimedia.org/nike-640.jpg",
                    ),
                }
            }
        }

    result = VesselPhotoService(get_json=get_json).get_photo("9431032")

    assert result.photo_url == "https://upload.wikimedia.org/nike-640.jpg"
    assert result.author == "Jane Doe"
    assert result.license == "CC BY-SA 4.0"
    assert len(calls) == 1
    assert calls[0][1]["generator"] == "search"
    assert calls[0][1]["gsrsearch"] == "9431032"


def test_lookup_falls_back_to_wikidata_when_commons_has_no_exact_imo_title():
    calls = []

    def get_json(url, params, headers):
        calls.append(url)
        if "commons.wikimedia.org" in url and params.get("generator") == "search":
            return {
                "query": {
                    "pages": {
                        "1": _commons_page("File:Unrelated ship.jpg"),
                    }
                }
            }
        if "wikidata" in url:
            return {
                "results": {
                    "bindings": [{
                        "item": {"value": "http://www.wikidata.org/entity/Q123"},
                        "img": {"value": "http://commons.wikimedia.org/wiki/Special:FilePath/Test%20Ship.jpg"},
                    }]
                }
            }
        return {
            "query": {
                "pages": {
                    "2": _commons_page(
                        "File:Test Ship.jpg",
                        "https://upload.wikimedia.org/test-640.jpg",
                    )
                }
            }
        }

    result = VesselPhotoService(get_json=get_json).get_photo("1234567")

    assert result.photo_url == "https://upload.wikimedia.org/test-640.jpg"
    assert any("wikidata" in call for call in calls)
    assert len(calls) == 3


def test_lookup_without_photo_returns_valid_empty_photo():
    def get_json(url, params, headers):
        if "commons.wikimedia.org" in url:
            return {"query": {"pages": {}}}
        return {"results": {"bindings": []}}

    result = VesselPhotoService(get_json=get_json).get_photo("1234567")

    assert result.imo == "1234567"
    assert result.photo_url is None
    assert result.author is None
    assert result.license is None
    assert result.source_url is None


def test_external_failure_remains_retryable_instead_of_becoming_no_photo():
    def get_json(url, params, headers):
        if "commons.wikimedia.org" in url:
            return {"query": {"pages": {}}}
        request = httpx.Request("GET", url)
        response = httpx.Response(429, request=request)
        raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    with pytest.raises(VesselPhotoUnavailableError):
        VesselPhotoService(get_json=get_json).get_photo("1234567")


def test_invalid_imo_never_calls_external_services():
    calls = []

    def get_json(url, params, headers):
        calls.append(url)
        return {}

    result = VesselPhotoService(get_json=get_json).get_photo("bad-imo")

    assert result.photo_url is None
    assert calls == []
