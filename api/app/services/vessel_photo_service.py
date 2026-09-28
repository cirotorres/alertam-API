from __future__ import annotations

from html import unescape
import re
from typing import Any, Callable, Mapping, Protocol

import httpx

from app.core.errors import VesselPhotoUnavailableError
from app.models.vessel_photo import VesselPhotoResponse

WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
DEFAULT_USER_AGENT = (
    "AlertaM-Mobile/0.1 "
    "(https://github.com/cirotorres/alertam-API)"
)

JsonGetter = Callable[[str, Mapping[str, str], Mapping[str, str]], dict[str, Any]]


class VesselPhotoLookup(Protocol):
    def get_photo(self, imo: str) -> VesselPhotoResponse: ...


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"<[^>]+>", "", unescape(value))
    normalized = " ".join(cleaned.split())
    return normalized or None


def _claim_values(
    entity: Mapping[str, Any],
    property_id: str,
) -> list[str]:
    claims = entity.get("claims")
    if not isinstance(claims, Mapping):
        return []

    raw_claims = claims.get(property_id)
    if not isinstance(raw_claims, list):
        return []

    values: list[str] = []
    for claim in raw_claims:
        if not isinstance(claim, Mapping):
            continue
        mainsnak = claim.get("mainsnak")
        if not isinstance(mainsnak, Mapping):
            continue
        datavalue = mainsnak.get("datavalue")
        if not isinstance(datavalue, Mapping):
            continue
        value = datavalue.get("value")
        if isinstance(value, str):
            values.append(value)
    return values


def _title_has_explicit_imo(title: str, imo: str) -> bool:
    return (
        re.search(
            rf"(?i)\bIMO(?:[\s:_-]+){re.escape(imo)}(?!\d)",
            title,
        )
        is not None
    )


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

    def _get_commons_file(
        self,
        imo: str,
        filename: str,
    ) -> VesselPhotoResponse | None:
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
        pages = commons.get("query", {}).get("pages", {})
        if not isinstance(pages, Mapping) or not pages:
            return None
        page = next(iter(pages.values()))
        if not isinstance(page, Mapping):
            return None
        return _photo_from_page(imo, page)

    def _get_wikidata_photo(self, imo: str) -> VesselPhotoResponse | None:
        headers = {"User-Agent": self._user_agent}
        search = self._get_json(
            WIKIDATA_API_URL,
            {
                "action": "query",
                "list": "search",
                "srsearch": f"haswbstatement:P458={imo}",
                "srnamespace": "0",
                "srlimit": "5",
                "format": "json",
            },
            headers,
        )
        raw_results = search.get("query", {}).get("search", [])
        if not isinstance(raw_results, list):
            return None

        entity_ids = [
            item["title"]
            for item in raw_results
            if isinstance(item, Mapping)
            and isinstance(item.get("title"), str)
            and re.fullmatch(r"Q\d+", item["title"])
        ]
        if not entity_ids:
            return None

        entities_body = self._get_json(
            WIKIDATA_API_URL,
            {
                "action": "wbgetentities",
                "ids": "|".join(entity_ids),
                "props": "claims",
                "format": "json",
            },
            headers,
        )
        entities = entities_body.get("entities", {})
        if not isinstance(entities, Mapping):
            return None

        for entity_id in entity_ids:
            entity = entities.get(entity_id)
            if not isinstance(entity, Mapping):
                continue
            if imo not in _claim_values(entity, "P458"):
                continue
            images = _claim_values(entity, "P18")
            if not images:
                continue
            return self._get_commons_file(imo, images[0])
        return None

    def _get_commons_fallback(self, imo: str) -> VesselPhotoResponse | None:
        body = self._get_json(
            COMMONS_API_URL,
            {
                "action": "query",
                "generator": "search",
                "gsrsearch": f"IMO {imo}",
                "gsrnamespace": "6",
                "gsrlimit": "10",
                "prop": "imageinfo",
                "iiprop": "url|extmetadata",
                "iiurlwidth": "640",
                "format": "json",
            },
            {"User-Agent": self._user_agent},
        )
        pages = body.get("query", {}).get("pages", {})
        if not isinstance(pages, Mapping):
            return None

        for page in pages.values():
            if not isinstance(page, Mapping):
                continue
            title = page.get("title")
            if not isinstance(title, str):
                continue
            if not _title_has_explicit_imo(title, imo):
                continue
            photo = _photo_from_page(imo, page)
            if photo is not None:
                return photo
        return None

    def get_photo(self, imo: str) -> VesselPhotoResponse:
        if re.fullmatch(r"\d{7}", imo) is None:
            return VesselPhotoResponse(imo=imo)

        structured_failed = False
        try:
            photo = self._get_wikidata_photo(imo)
            if photo is not None:
                return photo
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
            structured_failed = True

        try:
            fallback = self._get_commons_fallback(imo)
            if fallback is not None:
                return fallback
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise VesselPhotoUnavailableError() from exc

        if structured_failed:
            raise VesselPhotoUnavailableError()
        return VesselPhotoResponse(imo=imo)
