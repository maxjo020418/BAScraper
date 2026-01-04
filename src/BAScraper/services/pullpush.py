from BAScraper.services import BaseService
from BAScraper.service_types import PullPushModel

from asyncio import Semaphore
from typing import List
from httpx import AsyncClient

class PullPush(BaseService[PullPushModel]):
    def __init__(self, settings: PullPushModel) -> None:
        super().__init__(settings)

    async def _fetch_time_window(self,
                                 client: AsyncClient,
                                 settings: PullPushModel) -> List[dict]:
        raise NotImplementedError('Not done yet')

    async def _fetch_once(self,
                          client: AsyncClient,
                          settings: PullPushModel,
                          return_count: bool = False) -> List[dict]:
        raise NotImplementedError('Not done yet')

    async def _fetch_post_comments(self,
                                   client: AsyncClient,
                                   semaphore: Semaphore,
                                   settings: PullPushModel) -> List[dict]:
        raise NotImplementedError('Not done yet')
