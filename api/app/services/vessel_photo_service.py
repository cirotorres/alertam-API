from __future__ import annotations

from html import unescape
import re
from typing import Any, Callable, Mapping, Protocol
import urllib.parse

import httpx

from app.core.errors import VesselPhotoUnavailableError
from app.models.vessel_photo import VesselPhotoResponse

SPARQL_URL = "https://query.wikidata.org/sparql"
COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
DEFAULT_USER_AGENT = "AlertaM-Mobile/0.1"

JsonGetter = Callable[[str, Mapping[str, str], Mapping[str, str]], dict[str, Any]]

_SPARQL = """
SELECT ?item ?img WHERE {
  ?item wdt:P458 "%s" .
  OPTIONAL { ?item wdt:P18 ?img }
}
LIMIT 1
"""


class VesselPhotoLookup(Protocol):
    def get_photo(self, imo: str) -> VesselPhotoResponse: ...


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"<[^>]+>", "", unescape(value))
    normalized = " ".join(cleaned.split())
    return normalized or None


def _filename_from_p18(url: str) -> str:
    return urllib.parse.unquote(url.rsplit("/", 1)[-1])


def _photo_from_page(
    imo: str,
    page: Mapping[str, Any],
) -> VesselPhotoResponse | None:
    imageinfo = page.get("imageinfo")
    if not isinstance(imageinfo, list) or not imageinfo:
        return None

    info = imageinfo[0]
    if not isinstance(info, Mapping):
        return None

    photo_url = info.get("thumburl") or info.get("url")
    if not isinstance(photo_url, str) or not photo_url:
        return None

    metadata = info.get("extmetadata")
    if not isinstance(metadata, Mapping):
        metadata = {}

    artist = metadata.get("Artist")
    license_info = metadata.get("LicenseShortName")
    author_raw = artist.get("value") if isinstance(artist, Mapping) else None
    license_raw = (
        license_info.get("value")
        if isinstance(license_info, Mapping)
        else None
    )
    source_url = info.get("descriptionurl")

    return VesselPhotoResponse(
        imo=imo,
        photo_url=photo_url,
        author=_strip_html(
            author_raw if isinstance(author_raw, str) else None
        ),
        license=_strip_html(
            license_raw if isinstance(license_raw, str) else None
        ),
        source_url=source_url if isinstance(source_url, str) else None,
    )


class VesselPhotoService:
    def __init__(
        self,
        *,
        timeout: float = 8.0,
        user_agent: str = DEFAULT_USER_AGENT,
        get_json: JsonGetter | None = None,
    ) -> None:
        self._timeout = timeout
        self._user_agent = user_agent
        self._get_json = get_json or self._http_get_json

    def _http_get_json(
        self,
        url: str,
        params: Mapping[str, str],
        headers: Mapping[str, str],
    ) -> dict[str, Any]:
        response = httpx.get(
            url,
            params=params,
            headers=headers,
            timeout=self._timeout,
            follow_redirects=True,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("Resposta externa inválida.")
        return body

    def _get_wikidata_photo(self, imo: str) -> VesselPhotoResponse | None:
        wikidata = self._get_json(
            SPARQL_URL,
            {"query": _SPARQL % imo, "format": "json"},
            {
                "User-Agent": self._user_agent,
                "Accept": "application/sparql-results+json",
            },
        )
        bindings = wikidata["results"]["bindings"]
        if not bindings:
            return None

        image = bindings[0].get("img", {}).get("value")
        if not image:
            return None

        filename = _filename_from_p18(image)
        commons = self._get_json(
            COMMONS_API_URL,
            {
                "action": "query",
                "prop": "imageinfo",
                "iiprop": "url|extmetadata",
                "iiurlwidth": "640",
                "format": "json",
                "titles": f"File:{filename}",
            },
            {"User-Agent": self._user_agent},
        )
        pages = commons["query"]["pages"]
        page = next(iter(pages.values()))
        return _photo_from_page(imo, page)

    def get_photo(self, imo: str) -> VesselPhotoResponse:
        if re.fullmatch(r"\d{7}", imo) is None:
            return VesselPhotoResponse(imo=imo)

        try:
            photo = self._get_wikidata_photo(imo)
            return photo or VesselPhotoResponse(imo=imo)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise VesselPhotoUnavailableError() from exc
