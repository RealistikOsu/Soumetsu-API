from __future__ import annotations

from abc import ABC
from abc import ABCMeta
from abc import abstractmethod
from enum import EnumMeta
from enum import StrEnum
from typing import Self

try:
    from typing import TypeIs
except ImportError:
    from typing_extensions import TypeIs

from fastapi import status

from soumetsu_api.adapters.mysql import ImplementsMySQL
from soumetsu_api.adapters.redis import RedisClient
from soumetsu_api.adapters.storage import StorageAdapter
from soumetsu_api.resources import AchievementsRepository
from soumetsu_api.resources import AdminRepository
from soumetsu_api.resources import BadgesRepository
from soumetsu_api.resources import BeatmapsRepository
from soumetsu_api.resources import ClansRepository
from soumetsu_api.resources import CommentsRepository
from soumetsu_api.resources import ExampleRepository
from soumetsu_api.resources import FriendsRepository
from soumetsu_api.resources import LeaderboardRepository
from soumetsu_api.resources import ScoresRepository
from soumetsu_api.resources import SessionRepository
from soumetsu_api.resources import UserFilesRepository
from soumetsu_api.resources import UserHistoryRepository
from soumetsu_api.resources import UserRepository
from soumetsu_api.resources import UserStatsRepository


class _CombinedMeta(EnumMeta, ABCMeta):
    pass


class ServiceError(ABC, StrEnum, metaclass=_CombinedMeta):
    _ignore_ = ["OnSuccess"]
    type OnSuccess[T] = T | Self

    @abstractmethod
    def service(self) -> str: ...

    def status_code(self) -> int:
        return status.HTTP_500_INTERNAL_SERVER_ERROR

    def resolve_name(self) -> str:
        return f"{self.service()}.{self.value}"


def is_success[V](result: ServiceError.OnSuccess[V]) -> TypeIs[V]:
    return not isinstance(result, ServiceError)


def is_error[V](result: ServiceError.OnSuccess[V]) -> TypeIs[ServiceError]:
    return isinstance(result, ServiceError)


class AbstractContext(ABC):
    @property
    @abstractmethod
    def _mysql(self) -> ImplementsMySQL: ...

    @property
    @abstractmethod
    def _redis(self) -> RedisClient: ...

    @property
    @abstractmethod
    def _storage(self) -> StorageAdapter: ...

    @property
    def examples(self) -> ExampleRepository:
        return ExampleRepository(self._mysql)

    @property
    def users(self) -> UserRepository:
        return UserRepository(self._mysql)

    @property
    def user_stats(self) -> UserStatsRepository:
        return UserStatsRepository(self._mysql)

    @property
    def sessions(self) -> SessionRepository:
        return SessionRepository(self._redis)

    @property
    def scores(self) -> ScoresRepository:
        return ScoresRepository(self._mysql)

    @property
    def beatmaps(self) -> BeatmapsRepository:
        return BeatmapsRepository(self._mysql)

    @property
    def leaderboard(self) -> LeaderboardRepository:
        return LeaderboardRepository(self._mysql, self._redis)

    @property
    def clans(self) -> ClansRepository:
        return ClansRepository(self._mysql)

    @property
    def friends(self) -> FriendsRepository:
        return FriendsRepository(self._mysql)

    @property
    def comments(self) -> CommentsRepository:
        return CommentsRepository(self._mysql)

    @property
    def admin(self) -> AdminRepository:
        return AdminRepository(self._mysql)

    @property
    def badges(self) -> BadgesRepository:
        return BadgesRepository(self._mysql)

    @property
    def achievements(self) -> AchievementsRepository:
        return AchievementsRepository(self._mysql)

    @property
    def user_history(self) -> UserHistoryRepository:
        return UserHistoryRepository(self._mysql)

    @property
    def user_files(self) -> UserFilesRepository:
        return UserFilesRepository(self._storage)
