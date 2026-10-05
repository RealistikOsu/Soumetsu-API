"""Unit tests for the skin link check."""

from __future__ import annotations

import httpx
import pytest

from soumetsu_api.adapters import skins


def _serve(
    monkeypatch: pytest.MonkeyPatch,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, headers=headers)

    real = httpx.AsyncClient
    monkeypatch.setattr(
        skins.httpx,
        "AsyncClient",
        lambda **kwargs: real(transport=httpx.MockTransport(handler), **kwargs),
    )

    async def public(host: str) -> bool:
        return True

    monkeypatch.setattr(skins, "_is_public_host", public)
    return seen


class TestIsValidSkinUrl:
    @pytest.mark.asyncio
    async def test_approved_site_skips_the_request(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        seen = _serve(monkeypatch, status=403)

        assert await skins.is_valid_skin_url("https://skins.osuck.net/skins/123")
        assert not seen

    @pytest.mark.asyncio
    async def test_accepts_an_osk_attachment(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _serve(
            monkeypatch,
            headers={"Content-Disposition": 'attachment; filename="My Skin.osk"'},
        )

        assert await skins.is_valid_skin_url("https://example.com/download?id=1")

    @pytest.mark.asyncio
    async def test_rejects_other_attachments(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _serve(
            monkeypatch,
            headers={"Content-Disposition": 'attachment; filename="skin.zip"'},
        )

        assert not await skins.is_valid_skin_url("https://example.com/download?id=1")

    @pytest.mark.asyncio
    async def test_falls_back_to_the_path_without_a_disposition(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _serve(monkeypatch)

        assert await skins.is_valid_skin_url("https://example.com/skins/cool.osk")
        assert not await skins.is_valid_skin_url("https://example.com/skins/cool")

    @pytest.mark.asyncio
    async def test_rejects_failing_responses(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _serve(monkeypatch, status=404)

        assert not await skins.is_valid_skin_url("https://example.com/cool.osk")

    @pytest.mark.asyncio
    async def test_rejects_private_hosts_without_a_request(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        seen = _serve(monkeypatch)

        async def private(host: str) -> bool:
            return False

        monkeypatch.setattr(skins, "_is_public_host", private)

        assert not await skins.is_valid_skin_url("https://internal.example/cool.osk")
        assert not seen

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "url",
        [
            "http://example.com/cool.osk",
            "https://localhost/cool.osk",
            "ftp://example.com/cool.osk",
            "https://example.com/" + "a" * 300,
        ],
    )
    async def test_rejects_malformed_links(self, url: str) -> None:
        assert not await skins.is_valid_skin_url(url)
