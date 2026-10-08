"""Extract the embedded ``window.__PRELOADED_STATE__`` JSON from divar.ir HTML.

divar.ir server-renders a preloaded application state; all list-page data
(post rows, schema.org linked data, pagination cursors, category tree) lives
there. Keeping every access to its shape in this one module isolates format
drift.
"""

from __future__ import annotations

import codecs
import html as html_lib
import json
import re
from dataclasses import dataclass, field
from typing import Any

STATE_MARKER_RE = re.compile(r"window\.__PRELOADED_STATE__\s*=\s*")


class PageStateError(ValueError):
    """The embedded page state is missing or unparsable."""


@dataclass(frozen=True)
class WebInfo:
    city_persian: str = ""
    district_persian: str = ""
    category_slug_persian: str = ""
    title: str = ""


@dataclass(frozen=True)
class PostRow:
    token: str
    title: str = ""
    url: str = ""
    image_url: str = ""
    web_info: WebInfo = field(default_factory=WebInfo)
    top_text: str = ""
    middle_text: str = ""
    bottom_text: str = ""
    red_text: str = ""
    post_type: str = ""
    posted_at: str | None = None
    index: int = -1
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Pagination:
    has_more: bool = False
    last_post_date: str | None = None
    page: int | None = None
    search_uid: str | None = None
    cumulative_count: int = 0


def extract_state(html: str) -> dict[str, Any]:
    """Return the ``window.__PRELOADED_STATE__`` object from a page."""
    match = STATE_MARKER_RE.search(html)
    if match is None:
        raise PageStateError("window.__PRELOADED_STATE__ not found in page HTML")
    raw = _scan_balanced_object(html, match.end())
    if raw is None:
        raise PageStateError("unterminated state object in page HTML")
    for candidate in (raw, html_lib.unescape(raw)):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    try:
        parsed = json.loads(codecs.decode(raw, "unicode_escape"))
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    raise PageStateError("embedded state is not valid JSON")


def _scan_balanced_object(text: str, start: int) -> str | None:
    """Slice the JSON object literal starting at the first '{' at/after start."""
    i = text.find("{", start)
    if i == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    j = i
    n = len(text)
    while j < n:
        ch = text[j]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[i : j + 1]
        j += 1
    return None


def parse_pagination(state: dict[str, Any]) -> Pagination:
    node = _dig(state, "nb", "pagination") or {}
    data = node.get("data") or {}
    return Pagination(
        has_more=bool(node.get("hasMore", False)),
        last_post_date=data.get("last_post_date") or None,
        page=data.get("page"),
        search_uid=data.get("search_uid") or None,
        cumulative_count=int(data.get("cumulative_widgets_count") or 0),
    )


def iter_post_widgets(state: dict[str, Any]) -> list[PostRow]:
    rows: list[PostRow] = []
    widgets = _dig(state, "nb", "listWidgets") or []
    for widget in widgets:
        body = widget.get("data") if isinstance(widget, dict) else None
        if not isinstance(body, dict):
            body = widget if isinstance(widget, dict) else {}
        if body.get("widgetType") != "POST_ROW":
            continue
        dto = body.get("dto") or {}
        data = dto.get("data") or {}
        payload = _dig(data, "action", "payload") or {}
        info = _dig(dto, "action_log", "server_side_info", "info") or {}
        token = str(data.get("token") or payload.get("token") or "")
        if not token:
            continue
        web_info_raw = payload.get("web_info") or {}
        rows.append(
            PostRow(
                token=token,
                title=str(data.get("title") or web_info_raw.get("title") or ""),
                image_url=str(data.get("image_url") or ""),
                web_info=WebInfo(
                    city_persian=str(web_info_raw.get("city_persian") or ""),
                    district_persian=str(web_info_raw.get("district_persian") or ""),
                    category_slug_persian=str(web_info_raw.get("category_slug_persian") or ""),
                    title=str(web_info_raw.get("title") or ""),
                ),
                top_text=str(data.get("top_description_text") or ""),
                middle_text=str(data.get("middle_description_text") or ""),
                bottom_text=str(data.get("bottom_description_text") or ""),
                red_text=str(data.get("red_text") or ""),
                post_type=str(info.get("post_type") or ""),
                posted_at=info.get("sort_date") or None,
                index=int(info.get("index") or -1),
                raw=data,
            )
        )
    return rows


def linked_data(state: dict[str, Any]) -> list[dict[str, Any]]:
    entries = _dig(state, "nb", "seoDetails", "linkedData") or []
    return [e for e in entries if isinstance(e, dict)]


def root_category(state: dict[str, Any]) -> dict[str, Any] | None:
    root = _dig(state, "search", "rootCat")
    return root if isinstance(root, dict) and root.get("slug") else None


def current_post(state: dict[str, Any]) -> dict[str, Any] | None:
    post = _dig(state, "currentPost", "post")
    if isinstance(post, dict) and post.get("token"):
        return post
    return None


def extract_current_post(html: str) -> dict[str, Any] | None:
    return current_post(extract_state(html))


def _dig(data: Any, *keys: str) -> Any:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
