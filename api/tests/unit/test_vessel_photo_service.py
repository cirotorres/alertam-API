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


def test_photo_uses_wikidata_p18_as_the_only_photo_source():
    calls = []

    def get_json(url, params, headers):
        calls.append((url, params, headers))
        if "wikidata" in url:
            return {
                "results": {
                    "bindings": [{
                        "item": {"value": "http://www.wikidata.org/entity/Q123"},
                        "img": {
                            "value": (
                                "http://commons.wikimedia.org/wiki/"
                                "Special:FilePath/Nike%20IMO%209431032.jpg"
                            )
                        },
                    }]
                }
            }
        return {
            "query": {
                "pages": {
                    "2": _commons_page(
                        "File:Nike IMO 9431032.jpg",
                        "https://upload.wikimedia.org/nike-640.jpg",
                    )
                }
            }
        }

    result = VesselPhotoService(get_json=get_json).get_photo("9431032")

    assert result.photo_url == "https://upload.wikimedia.org/nike-640.jpg"
    assert result.author == "Jane Doe"
    assert result.license == "CC BY-SA 4.0"
    assert len(calls) == 2
    assert "wikidata" in calls[0][0]
    assert all(call[1].get("generator") != "search" for call in calls)


def test_lookup_without_wikidata_p18_never_accepts_textual_commons_match():
    calls = []

    def get_json(url, params, headers):
        calls.append((url, params))
        assert "wikidata" in url
        return {
            "results": {
                "bindings": [{
                    "item": {"value": "http://www.wikidata.org/entity/Q123"},
                }]
            }
        }

    result = VesselPhotoService(get_json=get_json).get_photo("9987366")

    assert result.photo_url is None
    assert len(calls) == 1
    assert calls[0][1].get("generator") is None


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
