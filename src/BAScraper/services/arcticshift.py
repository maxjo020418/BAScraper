from BAScraper.services import BaseService
from BAScraper.service_types import ArcticShiftModel

import logging
from asyncio import Semaphore
from httpx import AsyncClient, Client
from urllib.parse import urljoin

class ArcticShift(BaseService):
    def __init__(self, settings: ArcticShiftModel) -> None:
        super().__init__(settings)
        self.ratelimit_remaining: int = 0
    
    def test_connection(self):
        """
        used for getting the initial X-ratelimit-remaining and X-ratelimit-reset headers.
        """
        with Client() as client:
            r = client.get("https://arctic-shift.photon-reddit.com/api/subreddits/rules?subreddits=help")

    async def get_segment(self, client: AsyncClient, semaphore: Semaphore, settings: ArcticShiftModel) -> None:
        async with semaphore:
            # for type checker suppression (both are converted to (utc) int in the Model)
            assert isinstance(settings.after, int) and isinstance(settings.before, int)

            count = 1  # temp val to pass first iteration for the while loop
            cursor = settings.before
            
            while count > 0 and cursor > settings.after:
                params = settings.model_dump(
                    exclude=self.NOT_PARAMETER, 
                    exclude_none=True
                )
                url = urljoin(settings._BASE_URL, f"{settings.endpoint}/{settings.lookup}")

                await client.get(url=url, params=params)


    async def get_single_page(self, client: AsyncClient, settings: ArcticShiftModel) -> None:
        raise NotImplementedError('Not for direct use')
    
    async def get_comments_for_post(self, client: AsyncClient, semaphore: Semaphore, settings: ArcticShiftModel) -> None:
        raise NotImplementedError('Not for direct use')