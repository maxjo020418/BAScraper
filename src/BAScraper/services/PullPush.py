from BAScraper.services import BaseService
from BAScraper.service_types import PullPushModel

import logging

class PullPush(BaseService):
    def __init__(self, settings: PullPushModel) -> None:
        super().__init__(settings)
        logger = logging.getLogger(__name__)
    
    async def get_segment(self) -> None:
        raise NotImplementedError('Not for direct use')

    async def get_single_page(self) -> None:
        raise NotImplementedError('Not for direct use')
    
    async def get_comments_for_post(self) -> None:
        raise NotImplementedError('Not for direct use')