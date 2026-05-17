from __future__ import annotations

ALLOWED_IMAGE_MAGIC: tuple[bytes, ...] = (
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"\xff\xd8\xff",  # JPEG
    b"GIF87a",
    b"GIF89a",
)


def validate_image_magic(data: bytes) -> bool:
    """Check if image data starts with a valid magic byte sequence."""
    return any(data.startswith(magic) for magic in ALLOWED_IMAGE_MAGIC)
