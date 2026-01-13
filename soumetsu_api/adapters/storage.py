from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from soumetsu_api import settings


def ensure_directories() -> None:
    Path(settings.AVATAR_PATH).mkdir(parents=True, exist_ok=True)
    Path(settings.BANNER_PATH).mkdir(parents=True, exist_ok=True)


async def save_avatar(user_id: int, image_data: bytes) -> str | None:
    try:
        img = Image.open(io.BytesIO(image_data))
        img.thumbnail((256, 256), Image.Resampling.LANCZOS)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        output = io.BytesIO()
        img.save(output, format="PNG")

        avatar_path = Path(settings.AVATAR_PATH) / f"{user_id}.png"
        avatar_path.write_bytes(output.getvalue())

        return f"/avatars/{user_id}.png"
    except Exception:
        return None


async def save_banner(user_id: int, image_data: bytes) -> str | None:
    try:
        img = Image.open(io.BytesIO(image_data))
        img.thumbnail((1920, 640), Image.Resampling.LANCZOS)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        output = io.BytesIO()
        img.save(output, format="PNG")

        banner_path = Path(settings.BANNER_PATH) / f"{user_id}.png"
        banner_path.write_bytes(output.getvalue())

        return f"/banners/{user_id}.png"
    except Exception:
        return None


async def delete_avatar(user_id: int) -> bool:
    avatar_path = Path(settings.AVATAR_PATH) / f"{user_id}.png"
    if avatar_path.exists():
        avatar_path.unlink()
        return True
    return False


async def delete_banner(user_id: int) -> bool:
    banner_path = Path(settings.BANNER_PATH) / f"{user_id}.png"
    if banner_path.exists():
        banner_path.unlink()
        return True
    return False
