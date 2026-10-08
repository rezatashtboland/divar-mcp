import os

from divar_mcp import config


def test_static_cities_has_30_unique_slugs() -> None:
    assert len(config.STATIC_CITIES) == 30
    slugs = [c[0] for c in config.STATIC_CITIES]
    assert len(set(slugs)) == 30
    assert "tehran" in slugs


def test_static_cities_fields_non_empty() -> None:
    for slug, name_fa, name_en in config.STATIC_CITIES:
        assert slug and slug == slug.strip().lower()
        assert name_fa
        assert name_en


def test_core_constants_match_prd() -> None:
    assert config.BASE_URL == "https://divar.ir"
    assert config.DEFAULT_TIMEOUT == 10.0
    assert config.MAX_RETRIES == 3
    assert config.RATE_LIMIT_RPS == 2.0
    assert config.CITIES_CACHE_TTL == 24 * 3600
    assert config.SEARCH_CACHE_TTL == 5 * 60
    assert config.DETAIL_CACHE_TTL == 3600
    assert config.MAX_CURSOR_HOPS == 10


def test_default_headers_identify_accept_language() -> None:
    headers = config.default_headers()
    assert "User-Agent" in headers
    assert "fa" in headers["Accept-Language"]


def test_language_default_and_override(monkeypatch: os.environ) -> None:  # type: ignore[valid-type]
    monkeypatch.delenv("DIVAR_MCP_LANG", raising=False)
    assert config.language() == "fa"
    monkeypatch.setenv("DIVAR_MCP_LANG", "EN")
    assert config.language() == "en"
