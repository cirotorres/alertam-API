from app.services.vessel_photo_service import VesselPhotoService


def test_lookup_returns_commons_thumbnail_and_credit():
    calls = []

    def get_json(url, params, headers):
        calls.append((url, params, headers))
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
                    "1": {
                        "imageinfo": [{
                            "thumburl": "https://upload.wikimedia.org/test-640.jpg",
                            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Test_Ship.jpg",
                            "extmetadata": {
                                "Artist": {"value": "<b>Jane Doe</b>"},
                                "LicenseShortName": {"value": "CC BY-SA 4.0"},
                            },
                        }]
                    }
                }
            }
        }

    result = VesselPhotoService(get_json=get_json).get_photo("1234567")

    assert result.imo == "1234567"
    assert result.photo_url == "https://upload.wikimedia.org/test-640.jpg"
    assert result.author == "Jane Doe"
    assert result.license == "CC BY-SA 4.0"
    assert result.source_url.endswith("File:Test_Ship.jpg")
    assert len(calls) == 2


def test_lookup_without_p18_returns_valid_empty_photo():
    def get_json(url, params, headers):
        return {
            "results": {
                "bindings": [{
                    "item": {"value": "http://www.wikidata.org/entity/Q456"}
                }]
            }
        }

    result = VesselPhotoService(get_json=get_json).get_photo("1234567")

    assert result.imo == "1234567"
    assert result.photo_url is None
    assert result.author is None
    assert result.license is None
    assert result.source_url is None


def test_invalid_imo_never_calls_external_services():
    calls = []

    def get_json(url, params, headers):
        calls.append(url)
        return {}

    result = VesselPhotoService(get_json=get_json).get_photo("bad-imo")

    assert result.photo_url is None
    assert calls == []
