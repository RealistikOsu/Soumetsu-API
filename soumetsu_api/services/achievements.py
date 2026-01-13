from __future__ import annotations

from dataclasses import dataclass
from typing import override

from fastapi import status

from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError
from soumetsu_api.utilities import privileges


class AchievementError(ServiceError):
    USER_NOT_FOUND = "user_not_found"

    @override
    def service(self) -> str:
        return "achievements"

    @override
    def status_code(self) -> int:
        match self:
            case AchievementError.USER_NOT_FOUND:
                return status.HTTP_404_NOT_FOUND
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


@dataclass
class AchievementResult:
    id: int
    name: str
    description: str
    file: str
    achieved: bool
    achieved_at: int | None


async def get_user_achievements(
    ctx: AbstractContext,
    user_id: int,
) -> AchievementError.OnSuccess[list[AchievementResult]]:
    user = await ctx.users.find_by_id(user_id)
    if not user:
        return AchievementError.USER_NOT_FOUND

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return AchievementError.USER_NOT_FOUND

    all_achievements = await ctx.achievements.get_all()
    user_achievements = await ctx.achievements.get_user_achievements(user_id)

    user_ach_map = {ua.achievement_id: ua.time for ua in user_achievements}

    results = []
    for ach in all_achievements:
        achieved = ach.id in user_ach_map
        results.append(
            AchievementResult(
                id=ach.id,
                name=ach.name,
                description=ach.description,
                file=ach.file,
                achieved=achieved,
                achieved_at=user_ach_map.get(ach.id),
            ),
        )

    return results
