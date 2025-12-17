from BAScraper.services import BaseService
from BAScraper.service_types import PullPushModel

import logging
from asyncio import Semaphore
from httpx import AsyncClient

class PullPush(BaseService):
    def __init__(self, settings: PullPushModel) -> None:
        super().__init__(settings)

    async def get_segment(self, client: AsyncClient, semaphore: Semaphore, settings: PullPushModel) -> None:
        raise NotImplementedError('Not for direct use')

    async def get_single_page(self, client: AsyncClient, settings: PullPushModel) -> None:
        raise NotImplementedError('Not for direct use')
    
    async def get_comments_for_post(self, client: AsyncClient, semaphore: Semaphore, settings: PullPushModel) -> None:
        raise NotImplementedError('Not for direct use')