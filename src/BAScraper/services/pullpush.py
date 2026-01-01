from BAScraper.services import BaseService
from BAScraper.service_types import PullPushModel

from asyncio import Semaphore
from httpx import AsyncClient

class PullPush(BaseService):
    def __init__(self, settings: PullPushModel) -> None:
        super().__init__(settings)

    async def _fetch_time_window(self,
                           client: AsyncClient,
                           semaphore: Semaphore,
                           settings: PullPushModel) -> None:
        raise NotImplementedError('Not done yet')

    async def _fetch_once(self,
                               client: AsyncClient,
                               settings: PullPushModel) -> None:
        raise NotImplementedError('Not done yet')

    async def _fetch_post_comments(self,
                                     client: AsyncClient,
                                     semaphore: Semaphore,
                                     settings: PullPushModel) -> None:
        raise NotImplementedError('Not done yet')
