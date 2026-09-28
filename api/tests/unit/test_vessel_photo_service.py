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


def test_photo_prefers_structured_wikidata_p18():
    calls = []

    def get_json(url, params, headers):
        calls.append((url, params, headers))
        if params.get("list") == "search":
            return {"query": {"search": [{"title": "Q123"}]}}
        if params.get("action") == "wbgetentities":
            return {
                "entities": {
                    "Q123": {
                        "claims": {
                            "P458": [{
                                "mainsnak": {
                                    "datavalue": {"value": "9431032"}
                                }
                            }],
                            "P18": [{
                                "mainsnak": {
                                    "datavalue": {
                                        "value": "Nike IMO 9431032.jpg"
                                    }
                                }
                            }],
                        }
                    }
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
    assert len(calls) == 3
    assert all(call[1].get("generator") != "search" for call in calls)
    assert all("github.com/cirotorres/alertam-API" in call[2]["User-Agent"] for call in calls)


def test_wikidata_rate_limit_falls_back_to_explicit_imo_commons_title():
    def get_json(url, params, headers):
        if "wikidata.org" in url:
            request = httpx.Request("GET", url)
            response = httpx.Response(429, request=request)
            raise httpx.HTTPStatusError(
                "rate limited",
                request=request,
                response=response,
            )
        return {
            "query": {
                "pages": {
                    "1": _commons_page(
                        "File:Magnes (9348065).jpg",
                        "https://upload.wikimedia.org/wrong.jpg",
                    ),
                    "2": _commons_page(
                        "File:Monte Alegre (ship, 2008) IMO 9348065 Port of Antwerp.JPG",
                        "https://upload.wikimedia.org/monte-alegre.jpg",
                    ),
                }
            }
        }

    result = VesselPhotoService(get_json=get_json).get_photo("9348065")

    assert result.photo_url == "https://upload.wikimedia.org/monte-alegre.jpg"


def test_fallback_rejects_bare_numeric_commons_false_positive():
    def get_json(url, params, headers):
        if "wikidata.org" in url:
            return {"query": {"search": []}}
        return {
            "query": {
                "pages": {
                    "1": _commons_page(
                        "File:Magnes Sive De Arte Magnetica 1654 (9987366).jpg",
                    )
                }
            }
        }

    result = VesselPhotoService(get_json=get_json).get_photo("9987366")

    assert result.photo_url is None


def test_lookup_without_photo_returns_valid_empty_photo():
    def get_json(url, params, headers):
        if "commons.wikimedia.org" in url:
            return {"query": {"pages": {}}}
        return {"query": {"search": []}}

    result = VesselPhotoService(get_json=get_json).get_photo("1234567")

    assert result.imo == "1234567"
    assert result.photo_url is None
    assert result.author is None
    assert result.license is None
    assert result.source_url is None


def test_structured_outage_without_safe_fallback_remains_retryable():
    def get_json(url, params, headers):
        if "wikidata.org" in url:
            request = httpx.Request("GET", url)
            response = httpx.Response(429, request=request)
            raise httpx.HTTPStatusError(
                "rate limited",
                request=request,
                response=response,
            )
        return {"query": {"pages": {}}}

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
