from BAScraper.services import BaseService
from BAScraper.service_types import ArcticShiftModel

import tempfile
import json
import os
import logging
from typing import List
from asyncio import Semaphore
from httpx import AsyncClient, Client, Response
from urllib.parse import urljoin
from aiolimiter import AsyncLimiter

class ArcticShift(BaseService[ArcticShiftModel]):
    def __init__(self,
                 settings: ArcticShiftModel,
                 connection_test_url: str | None = None) -> None:
        super().__init__(settings)
        self.logger = logging.getLogger(__name__)
        self.connection_test_url = (
            "https://arctic-shift.photon-reddit.com/api/subreddits/rules?subreddits=help"
            if connection_test_url is None
            else connection_test_url
        )
        self.async_limiter: AsyncLimiter | None = None

    def _test_connection(self):
        """
        used for getting the initial X-ratelimit-remaining and X-ratelimit-reset headers
        """
        with Client() as client:
            response: Response = self \
                .service_retry(client.get)(self.connection_test_url) \
                .raise_for_status()

            assert response.status_code != 429, \
                f"Currently rate-limited!, " \
                f"Try again after {response.headers.get("X-RateLimit-Remaining")}s"

            self.async_limiter = AsyncLimiter(
                max_rate=response.headers.get("X-RateLimit-Reset"),
                time_period=response.headers.get("X-RateLimit-Remaining")
            )
            self.logger.info(f"Ratelimit initialized - "
                             f"max rate: {self.async_limiter.max_rate} | "
                             f"time period: {self.async_limiter.time_period}")

    async def _fetch_time_window(self,
                                 client: AsyncClient,
                                 settings: ArcticShiftModel) -> list:
        # for type checker suppression
        # (both are already converted to (utc) int in the Model)
        assert isinstance(settings.after, int) and isinstance(settings.before, int)

        cursor = settings.before  # start point cursor

        temp_file = tempfile.NamedTemporaryFile(mode="w+", dir="./",
                                                prefix="BAScraper_",
                                                suffix="_tempfile.json",
                                                delete=False)
        self.logger.info(f"temp file created as: {temp_file.name}")

        data = list()
        # condition is not rly need in practice but just in case
        while cursor > settings.after:
            params = settings.model_dump(
                exclude=self.NOT_REQUEST_PARAMETER,
                exclude_none=True
            )
            url = urljoin(
                settings._BASE_URL, f"{settings.endpoint}/{settings.lookup}"
            )
            print(params['after'], params['before'])
            params['before'] = cursor

            # TODO: request sent logs (need worker ID and such)
            # self.logger.debug("")
            response = await client.get(url=url, params=params)
            response = await self.check_response(response)

            # already asserted that 'data' is there
            resp_json: List[dict] = response.json()['data']

            result_count = len(resp_json)
            self.logger.info(f"GET Recieved: "
                             f"res-count: {result_count} | cursor: {cursor} | "
                             f"ratelimit-remaining: {response.headers.get("X-RateLimit-Remaining")} | "
                             f"ratelimit-reset: {response.headers.get("X-RateLimit-Reset")}")
            if result_count <= 0:
                break

            cursor = int(resp_json[-1]['created_utc'])
            data.append(resp_json)
            json.dump(resp_json, temp_file)

        # tempfile won't be closed/ulinked if it errors out
        # if it throws an exception, it should error out before this point (I think)
        temp_file.flush()
        temp_file.close()
        self.logger.info(f"cleaning up tempfile '{temp_file.name}'...")
        os.unlink(temp_file.name)

        return data

    async def _fetch_once(self,
                          client: AsyncClient,
                          settings: ArcticShiftModel) -> None:
        raise NotImplementedError('Not for direct use')

    async def _fetch_post_comments(self,
                                   client:AsyncClient,
                                   semaphore: Semaphore,
                                   settings: ArcticShiftModel) -> None:
        raise NotImplementedError('Not for direct use')
