from .base_service import BaseService
from BAScraper.service_types import PullPushModel

from asyncio import Queue
from typing import List, Literal, Tuple, overload
from httpx import AsyncClient


class PullPush(BaseService[PullPushModel]):
    def __init__(self, settings: PullPushModel) -> None:
        super().__init__(settings)

    async def _fetch_time_window(
        self, client: AsyncClient, settings: PullPushModel, worker_id: int
    ) -> List[dict]:
        raise NotImplementedError("Not for direct use")

    @overload
    async def _fetch_once(
        self,
        client: AsyncClient,
        settings: PullPushModel,
        return_count: Literal[False] = False,
    ) -> List[dict]: ...

    @overload
    async def _fetch_once(
        self,
        client: AsyncClient,
        settings: PullPushModel,
        return_count: Literal[True],
    ) -> Tuple[List[dict], int]: ...

    async def _fetch_once(
        self,
        client: AsyncClient,
        settings: PullPushModel,
        return_count: bool = False,  # only used by `_fetch_time_window`
    ) -> List[dict] | Tuple[List[dict], int]:
        raise NotImplementedError("Not for direct use")

    async def _fetch_post_comments(
        self, client: AsyncClient, settings: PullPushModel, ids: Queue[str]
    ) -> List[dict]:
        raise NotImplementedError("Not for direct use")
