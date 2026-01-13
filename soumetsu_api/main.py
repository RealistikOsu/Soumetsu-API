from __future__ import annotations

from soumetsu_api import api
from soumetsu_api import settings
from soumetsu_api.utilities import logging
from soumetsu_api.utilities import loop

logging.configure_from_yaml()
loop.install_optimal_loop()

match settings.APP_COMPONENT:
    case "fastapi":
        # Will be ran by the uvicorn CLI.
        asgi_app = api.create_app()
    case _:
        raise ValueError(f"Invalid app component: {settings.APP_COMPONENT}")
