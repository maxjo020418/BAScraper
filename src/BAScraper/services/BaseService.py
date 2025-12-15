import httpx
import asyncio

from typing import Union
from BAScraper.service_types import PullPushModel, ArcticShiftModel

class BaseService:
    def __init__(self, settings: Union[PullPushModel, ArcticShiftModel]) -> None:
        self.settings = settings

    async def get_segment(self) -> None:
        raise NotImplementedError('Not for direct use')

    async def get_single_page(self) -> None:
        raise NotImplementedError('Not for direct use')
    
    async def get_comments_for_post(self) -> None:
        raise NotImplementedError('Not for direct use')