from BAScraper.services import BaseService
from BAScraper.service_types import ArcticShiftModel
from BAScraper.utils import AdaptiveRateLimiter

import tempfile
import json
import os
import logging
from tenacity import RetryError
from math import ceil
from typing import List, Tuple, Literal, overload
from asyncio import Semaphore
from httpx import AsyncClient
from urllib.parse import urljoin
from aiolimiter import AsyncLimiter

class ArcticShift(BaseService[ArcticShiftModel]):
    def __init__(self,
                 settings: ArcticShiftModel) -> None:
        super().__init__(settings)
        self.logger = logging.getLogger(__name__)
        self.async_limiter: AsyncLimiter | None = None
        # TODO: expose granular control paramters (no hardcode)
        self.limiter = AdaptiveRateLimiter(safety_margin=1)

    async def _fetch_time_window(self,
                                 client: AsyncClient,
                                 settings: ArcticShiftModel,
                                 worker_id: int = -1) -> List[dict]:
        def _cleanup(temp_file):
            temp_file.flush()
            temp_file.close()
            self.logger.info(f"cleaning up tempfile '{temp_file.name}'...")
            os.unlink(temp_file.name)

        # for type checker suppression
        # (both are already converted to (utc) int in the Model)
        assert isinstance(settings.after, int) and isinstance(settings.before, int)

        cursor = settings.before  # start point cursor
        start_time = settings.before

        temp_file = tempfile.NamedTemporaryFile(mode="w+", dir="./",
                                                prefix="BAScraper_",
                                                suffix="_tempfile.json",
                                                delete=False)
        self.logger.info(f"temp file created as: {temp_file.name}")

        data: List[dict] = list()
        try:
            # condition is not rly need in practice but just in case
            while cursor > settings.after:
                settings.before = cursor
                resp_json, result_count = await self._fetch_once(client, settings, True)

                if result_count <= 0:
                    break

                cursor = int(resp_json[-1]['created_utc'])
                data += resp_json
                json.dump(resp_json, temp_file)

                self.logger.info(f"worker-{worker_id} progress: "
                                f"{ceil((start_time-cursor)/(start_time-settings.after)*100)}%")

        except self.retryable_exception as err:
            # perform cleanup to prevent tempfile accumulating between retries
            _cleanup(temp_file)
            raise err  # passed to tencity to attempt retry

        except RetryError as err:
            # tempfile will not be closed (for progress recovery if needed)
            self.logger.error(f"worker-{worker_id} Maximum retry reached! Aborting...\n{err}")
            return data

        except KeyboardInterrupt:
            # tempfile will not be closed (for progress recovery if needed)
            self.logger.error(f"worker-{worker_id} Has been cancelled!")
            return data

        else:
            _cleanup(temp_file)
            return data

    @overload
    async def _fetch_once(self,
                          client: AsyncClient,
                          settings: ArcticShiftModel,
                          return_count: Literal[False] = False,
                          ) -> List[dict]: ...

    @overload
    async def _fetch_once(self,
                          client: AsyncClient,
                          settings: ArcticShiftModel,
                          return_count: Literal[True],
                          ) -> Tuple[List[dict], int]: ...

    async def _fetch_once(self,
                          client: AsyncClient,
                          settings: ArcticShiftModel,
                          return_count: bool = False,  # only used by `_fetch_time_window`
                          ) -> List[dict] | Tuple[List[dict], int]:
        params = settings.model_dump(
            exclude=self.NOT_REQUEST_PARAMETER,
            exclude_none=True
        )
        url = urljoin(
            settings._BASE_URL, f"{settings.endpoint}/{settings.lookup}"
        )

        await self.limiter.acquire()
        response = await client.get(url=url, params=params)
        response = await self.check_response(response)

        # already asserted that 'data' is there
        resp_json: List[dict] = response.json()['data']
        ratelimit_remaining = response.headers.get("X-RateLimit-Remaining")
        ratelimit_reset = response.headers.get("X-RateLimit-Reset")

        if ratelimit_remaining is not None and ratelimit_reset is not None:
            await self.limiter.update(ratelimit_remaining, ratelimit_reset)

        result_count = len(resp_json)
        self.logger.info(f"GET Recieved: "
                         f"res-count: {result_count} | "
                         f"ratelimit-remaining: {ratelimit_remaining} | "
                         f"ratelimit-reset: {ratelimit_reset}")

        return resp_json if not return_count else (resp_json, result_count)

    async def _fetch_post_comments(self,
                                   client:AsyncClient,
                                   semaphore: Semaphore,
                                   settings: ArcticShiftModel) -> List[dict]:
        raise NotImplementedError('Not for direct use')
