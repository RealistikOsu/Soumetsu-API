from __future__ import annotations

from dataclasses import dataclass
from typing import override

from fastapi import status

from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError
from soumetsu_api.services import users


class TeamError(ServiceError):
    TEAM_NOT_FOUND = "team_not_found"

    @override
    def service(self) -> str:
        return "team"

    @override
    def status_code(self) -> int:
        match self:
            case TeamError.TEAM_NOT_FOUND:
                return status.HTTP_404_NOT_FOUND
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


# Team groups configuration: badge_id -> display name
TEAM_GROUPS = {
    2: "Developer Team",
    1018: "Administrator Team",
    1020: "Community Management Team",
    30: "Chat Moderation Team",
    5: "Beatmap Appreciation Team",
    1017: "Social Media Team",
    1002: "Supporters",
}


@dataclass
class TeamMemberResult:
    id: int
    username: str
    country: str
    privileges: int
    global_rank: int
    country_rank: int
    is_online: bool
    pp: int
    accuracy: float
    mode: int
    custom_mode: int


@dataclass
class TeamGroupResult:
    badge_id: int
    name: str
    members: list[TeamMemberResult]


@dataclass
class TeamResult:
    groups: list[TeamGroupResult]


async def get_team(ctx: AbstractContext) -> TeamError.OnSuccess[TeamResult]:
    """Get all team groups with member card data."""
    groups = []

    for badge_id, group_name in TEAM_GROUPS.items():
        # Get badge members
        members_data = await ctx.badges.get_members(badge_id, limit=100, offset=0)

        members = []
        for member in members_data:
            # Get card data for each member using the users service
            card_result = await users.get_card(ctx, member.user_id)

            if isinstance(card_result, users.UserCard):
                members.append(
                    TeamMemberResult(
                        id=card_result.id,
                        username=card_result.username,
                        country=card_result.country,
                        privileges=card_result.privileges,
                        global_rank=card_result.global_rank,
                        country_rank=card_result.country_rank,
                        is_online=card_result.is_online,
                        pp=card_result.pp,
                        accuracy=card_result.accuracy,
                        mode=card_result.mode,
                        custom_mode=card_result.custom_mode,
                    )
                )
            else:
                # Fallback if card data unavailable (user restricted, etc)
                members.append(
                    TeamMemberResult(
                        id=member.user_id,
                        username=member.username,
                        country=member.country,
                        privileges=1,
                        global_rank=0,
                        country_rank=0,
                        is_online=False,
                        pp=0,
                        accuracy=0.0,
                        mode=0,
                        custom_mode=0,
                    )
                )

        groups.append(
            TeamGroupResult(
                badge_id=badge_id,
                name=group_name,
                members=members,
            )
        )

    return TeamResult(groups=groups)
