from __future__ import annotations

import socket
import time

from soumetsu_api import settings

RESOLVE_EVERY = 60

_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
_sock.setblocking(False)
_address: tuple[str, int] | None = None
_next_resolve = 0.0


def _resolve() -> tuple[str, int] | None:
    """The agent container usually starts after this service, so look it up again every minute."""
    global _address, _next_resolve

    if time.monotonic() < _next_resolve:
        return _address

    _next_resolve = time.monotonic() + RESOLVE_EVERY
    try:
        _address = (socket.gethostbyname(settings.STATSD_HOST), settings.STATSD_PORT)
    except OSError:
        pass

    return _address


def _send(name: str, value: float, kind: str, tags: list[str] | None) -> None:
    if not settings.STATSD_HOST:
        return

    address = _resolve()
    if address is None:
        return

    line = f"{name}:{value}|{kind}"
    if tags:
        line += "|#" + ",".join(tags)

    try:
        _sock.sendto(line.encode(), address)
    except OSError:
        pass


def gauge(name: str, value: float, tags: list[str] | None = None) -> None:
    _send(name, value, "g", tags)


def timing(name: str, milliseconds: float, tags: list[str] | None = None) -> None:
    _send(name, milliseconds, "ms", tags)
