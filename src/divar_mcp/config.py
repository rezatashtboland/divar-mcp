"""Static configuration for the divar-mcp server."""

from __future__ import annotations

import os

BASE_URL = "https://divar.ir"
# Unverified from this environment (returns 403 without app headers); optional probing only.
API_BASE_URL = "https://api.divar.ir/v8"

DEFAULT_TIMEOUT = 10.0
MAX_RETRIES = 3
RATE_LIMIT_RPS = 2.0

CITIES_CACHE_TTL = 24 * 60 * 60
SEARCH_CACHE_TTL = 5 * 60
DETAIL_CACHE_TTL = 60 * 60

MAX_CURSOR_HOPS = 10
MAX_PAGE_SIZE = 50
DEFAULT_PAGE_SIZE = 20
DEFAULT_MATCH_LIMIT = 20
MAX_COMPARE_LISTINGS = 5

# divar.ir serves listing pages to browser-like clients; a bot UA is blocked.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)


def default_headers() -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
    }


def language() -> str:
    """Error-message language: 'fa' (default) or 'en', via DIVAR_MCP_LANG."""
    value = os.environ.get("DIVAR_MCP_LANG", "fa").strip().lower()
    return value if value in {"fa", "en"} else "fa"


# (slug, name_fa, name_en) fallback used when live discovery fails.
STATIC_CITIES: tuple[tuple[str, str, str], ...] = (
    ("tehran", "تهران", "Tehran"),
    ("mashhad", "مشهد", "Mashhad"),
    ("isfahan", "اصفهان", "Isfahan"),
    ("karaj", "کرج", "Karaj"),
    ("shiraz", "شیراز", "Shiraz"),
    ("tabriz", "تبریز", "Tabriz"),
    ("qom", "قم", "Qom"),
    ("ahvaz", "اهواز", "Ahvaz"),
    ("kermanshah", "کرمانشاه", "Kermanshah"),
    ("urmia", "ارومیه", "Urmia"),
    ("rasht", "رشت", "Rasht"),
    ("zanjan", "زنجان", "Zanjan"),
    ("hamedan", "همدان", "Hamedan"),
    ("kerman", "کرمان", "Kerman"),
    ("yazd", "یزد", "Yazd"),
    ("arak", "اراک", "Arak"),
    ("ardabil", "اردبیل", "Ardabil"),
    ("bandar-abbas", "بندرعباس", "Bandar Abbas"),
    ("qazvin", "قزوین", "Qazvin"),
    ("zahedan", "زاهدان", "Zahedan"),
    ("sanandaj", "سنندج", "Sanandaj"),
    ("birjand", "بیرجند", "Birjand"),
    ("bojnurd", "بجنورد", "Bojnurd"),
    ("yasouj", "یاسوج", "Yasouj"),
    ("ilam", "ایلام", "Ilam"),
    ("semnan", "سمنان", "Semnan"),
    ("gorgan", "گرگان", "Gorgan"),
    ("sari", "ساری", "Sari"),
    ("chalus", "چالوس", "Chalus"),
    ("gonbad-kavus", "گنبدکاوس", "Gonbad Kavus"),
)
