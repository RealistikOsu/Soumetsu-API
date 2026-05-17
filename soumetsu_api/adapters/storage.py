from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from soumetsu_api import settings


class StorageAdapter:
    """File storage adapter for user avatars, banners, and clan icons."""

    __slots__ = ("_avatar_path", "_banner_path", "_clan_icon_path")

    def __init__(
        self,
        avatar_path: str,
        banner_path: str,
        clan_icon_path: str,
    ) -> None:
        self._avatar_path = Path(avatar_path)
        self._banner_path = Path(banner_path)
        self._clan_icon_path = Path(clan_icon_path)

    def ensure_directories(self) -> None:
        self._avatar_path.mkdir(parents=True, exist_ok=True)
        self._banner_path.mkdir(parents=True, exist_ok=True)
        self._clan_icon_path.mkdir(parents=True, exist_ok=True)

    async def save_avatar(self, user_id: int, image_data: bytes) -> str | None:
        try:
            img = Image.open(io.BytesIO(image_data))
            img.thumbnail((256, 256), Image.Resampling.LANCZOS)

            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            output = io.BytesIO()
            img.save(output, format="PNG")

            avatar_path = self._avatar_path / f"{user_id}.png"
            avatar_path.write_bytes(output.getvalue())

            return f"/avatars/{user_id}.png"
        except Exception:
            return None

    async def save_banner(self, user_id: int, image_data: bytes) -> str | None:
        try:
            img = Image.open(io.BytesIO(image_data))
            img.thumbnail((1920, 640), Image.Resampling.LANCZOS)

            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            output = io.BytesIO()
            img.save(output, format="PNG")

            banner_path = self._banner_path / f"{user_id}.png"
            banner_path.write_bytes(output.getvalue())

            return f"/banners/{user_id}.png"
        except Exception:
            return None

    async def delete_avatar(self, user_id: int) -> bool:
        avatar_path = self._avatar_path / f"{user_id}.png"
        if avatar_path.exists():
            avatar_path.unlink()
            return True
        return False

    async def delete_banner(self, user_id: int) -> bool:
        banner_path = self._banner_path / f"{user_id}.png"
        if banner_path.exists():
            banner_path.unlink()
            return True
        return False

    async def save_clan_icon(self, clan_id: int, image_data: bytes) -> str | None:
        try:
            img = Image.open(io.BytesIO(image_data))
            img.thumbnail((256, 256), Image.Resampling.LANCZOS)

            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            output = io.BytesIO()
            img.save(output, format="PNG")

            icon_path = self._clan_icon_path / f"{clan_id}.png"
            icon_path.write_bytes(output.getvalue())

            return f"/clan-icons/{clan_id}.png"
        except Exception:
            return None

    async def delete_clan_icon(self, clan_id: int) -> bool:
        icon_path = self._clan_icon_path / f"{clan_id}.png"
        if icon_path.exists():
            icon_path.unlink()
            return True
        return False

    def clan_icon_path(self, clan_id: int) -> Path:
        return self._clan_icon_path / f"{clan_id}.png"


def default() -> StorageAdapter:
    """Creates a default storage adapter using settings."""
    return StorageAdapter(
        avatar_path=settings.AVATAR_PATH,
        banner_path=settings.BANNER_PATH,
        clan_icon_path=settings.CLAN_ICON_PATH,
    )
