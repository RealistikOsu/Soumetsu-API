from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.responses import Response
from pydantic import BaseModel

from soumetsu_api.services import ServiceError
from soumetsu_api.utilities import logging

logger = logging.get_logger(__name__)


class BaseResponse[T](BaseModel):
    status: int
    data: T


class ServiceInterruptionException(Exception):
    def __init__(self, response: Response) -> None:
        self.response = response


def create(data: Any, *, status: int = status.HTTP_200_OK) -> Response:

    model_json = BaseResponse(status=status, data=data).model_dump_json(
        exclude_none=False,
    )
    return Response(
        content=model_json,
        media_type="application/json",
        status_code=status,
    )


def unwrap[T](service_response: ServiceError.OnSuccess[T]) -> T:
    if isinstance(service_response, ServiceError):
        logger.debug(
            "API call was interrupted by a service error.",
            extra={
                "error": service_response.resolve_name(),
                "status_code": service_response.status_code(),
            },
        )

        raise ServiceInterruptionException(
            create(
                data=service_response.resolve_name(),
                status=service_response.status_code(),
            ),
        )

    return service_response
