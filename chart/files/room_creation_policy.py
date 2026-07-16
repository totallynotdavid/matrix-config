from synapse.module_api import NOT_SPAM
from synapse.module_api.errors import Codes


class ApprovedRoomsOnly:
    """Allow only configured room managers or Synapse admins to create/invite."""

    def __init__(self, config, api):
        self._api = api
        self._allowed_users = frozenset(config.get("allowed_users", []))
        api.register_spam_checker_callbacks(
            user_may_create_room=self.user_may_create_room,
            user_may_invite=self.user_may_invite,
        )

    async def _may_manage_rooms(self, user_id):
        return user_id in self._allowed_users or await self._api.is_user_admin(user_id)

    async def user_may_create_room(self, user_id):
        if await self._may_manage_rooms(user_id):
            return NOT_SPAM
        return Codes.FORBIDDEN

    async def user_may_invite(self, inviter, invitee, room_id):
        if await self._may_manage_rooms(inviter):
            return NOT_SPAM
        return Codes.FORBIDDEN
