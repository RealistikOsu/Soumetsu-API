from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from urllib.parse import urlsplit

import httpx

from soumetsu_api.utilities import logging

logger = logging.get_logger(__name__)

MAX_URL_LENGTH = 255

# The sites Bathbot accepts without a check. Most of them hide behind Cloudflare or a login and
# serve a page rather than the file, so a HEAD request would tell us nothing.
APPROVED_SITES = re.compile(
    r"^https://(?:"
    r"(?:www\.)?(?:drive\.google\.com|dropbox\.com|mega\.nz|mediafire\.com|(?:gist\.)?github\.com)/.+"
    r"|skins\.osuck\.net/(?:skins/\d+|authors/\d+|users/\d+).*"
    r"|osu\.ppy\.sh/community/forums/topics/\d+.*"
    r"|link\.issou\.best/skin/\d+"
    r")$",
)

_FILENAME = re.compile(r'filename="?([^";]+)"?', re.IGNORECASE)


async def _is_public_host(host: str) -> bool:
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            host,
            443,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror:
        return False

    return all(ipaddress.ip_address(info[4][0]).is_global for info in infos)


def _disposition_filename(header: str) -> str | None:
    kind, _, params = header.partition(";")
    if kind.strip().lower() not in ("attachment", "inline"):
        return None

    match = _FILENAME.search(params)
    return match[1] if match else None


async def is_valid_skin_url(url: str) -> bool:
    """Whether the link is a direct .osk download, or one of the approved skin sites."""
    if len(url) > MAX_URL_LENGTH:
        return False

    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or "." not in parts.hostname:
        return False

    if APPROVED_SITES.match(url):
        return True

    # The server fetches whatever it's given, so private addresses are off limits.
    if not await _is_public_host(parts.hostname):
        return False

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.head(url)
    except httpx.HTTPError:
        logger.debug("Skin link could not be reached.", extra={"url": url})
        return False

    if not response.is_success:
        return False

    disposition = response.headers.get("content-disposition")
    filename = _disposition_filename(disposition) if disposition else parts.path
    return filename is not None and filename.lower().endswith(".osk")
