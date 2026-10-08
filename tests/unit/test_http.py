import asyncio

import httpx
import pytest
import respx

from divar_mcp import config
from divar_mcp.client.http import DivarUnavailableError, HttpClient

URL = "https://divar.ir/s/tehran/real-estate"


@pytest.fixture
async def client():
    c = HttpClient(rate_rps=10_000, wait_base=0.001)
    yield c
    await c.close()


@respx.mock
async def test_get_text_ok_and_sends_browser_headers(client: HttpClient) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, text="<html>ok</html>"))
    body = await client.get_text(URL)
    assert body == "<html>ok</html>"
    assert route.call_count == 1
    sent = route.calls[0].request.headers["user-agent"]
    assert sent.startswith("Mozilla/")
    assert "fa" in route.calls[0].request.headers["accept-language"]


@respx.mock
async def test_retries_on_500_then_succeeds(client: HttpClient) -> None:
    route = respx.get(URL).mock(side_effect=[httpx.Response(500), httpx.Response(200, text="ok")])
    assert await client.get_text(URL) == "ok"
    assert route.call_count == 2


@respx.mock
async def test_retries_on_429(client: HttpClient) -> None:
    route = respx.get(URL).mock(side_effect=[httpx.Response(429), httpx.Response(200, text="ok")])
    assert await client.get_text(URL) == "ok"
    assert route.call_count == 2


@respx.mock
async def test_gives_up_after_max_retries(client: HttpClient) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(503))
    with pytest.raises(DivarUnavailableError):
        await client.get_text(URL)
    assert route.call_count == config.MAX_RETRIES


@respx.mock
async def test_404_does_not_retry(client: HttpClient) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    with pytest.raises(DivarUnavailableError):
        await client.get_text(URL)
    assert route.call_count == 1


@respx.mock
async def test_403_blocked_message(client: HttpClient, monkeypatch: pytest.MonkeyPatch) -> None:
    respx.get(URL).mock(return_value=httpx.Response(403))
    monkeypatch.setenv("DIVAR_MCP_LANG", "en")
    with pytest.raises(DivarUnavailableError) as excinfo:
        await client.get_text(URL)
    assert "blocked" in excinfo.value.user_message().lower()
    monkeypatch.setenv("DIVAR_MCP_LANG", "fa")
    assert any("\u0600" <= ch <= "\u06ff" for ch in excinfo.value.user_message())


@respx.mock
async def test_ttl_cache_dedupes_same_bucket(client: HttpClient) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, text="a"))
    assert await client.get_text(URL, cache="search") == "a"
    assert await client.get_text(URL, cache="search") == "a"
    assert route.call_count == 1
    # a different bucket fetches again
    assert await client.get_text(URL, cache="detail") == "a"
    assert route.call_count == 2
    # uncached always fetches
    assert await client.get_text(URL) == "a"
    assert route.call_count == 3


@respx.mock
async def test_rate_limiter_spaces_requests() -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, text="ok"))
    c = HttpClient(rate_rps=50, wait_base=0.001)  # 20 ms minimum spacing
    try:
        start = asyncio.get_running_loop().time()
        for _ in range(4):
            await c.get_text(URL)
        elapsed = asyncio.get_running_loop().time() - start
    finally:
        await c.close()
    assert elapsed >= 3 * 0.02 * 0.8  # 3 gaps of 20 ms, 20% timer tolerance


@respx.mock
async def test_network_error_wrapped(client: HttpClient) -> None:
    respx.get(URL).mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(DivarUnavailableError):
        await client.get_text(URL)
