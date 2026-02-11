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
from httpx import AsyncClient
from urllib.parse import urljoin
from aiolimiter import AsyncLimiter

class ArcticShift(BaseService[ArcticShiftModel]):
    def __init__(self,
                 settings: ArcticShiftModel) -> None:
        super().__init__(settings)
        self.logger = logging.getLogger(__name__)
        self.async_limiter: AsyncLimiter | None = None
        # TODO: expose granular control paramters (no hardcoded params)
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
        # both are already converted to (utc) int in the Model but IDE complains...
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

    # https://peps.python.org/pep-0484/#function-method-overloading
    @overload  # for static type checking
    async def _fetch_once(self,
                          client: AsyncClient,
                          settings: ArcticShiftModel,
                          return_count: Literal[False] = False,
                          ) -> List[dict]: ...

    @overload  # for static type checking
    async def _fetch_once(self,
                          client: AsyncClient,
                          settings: ArcticShiftModel,
                          return_count: Literal[True],
                          ) -> Tuple[List[dict], int]: ...

    async def _fetch_once(self,
                          client: AsyncClient,
                          settings: ArcticShiftModel,
                          return_count: bool = False,
                          ) -> List[dict] | Tuple[List[dict], int]:
        # !! `return_count=True` is only used by `_fetch_time_window` !!
        # return_count returns the "count of posts/comments"
        # used for time window fetching which needs this to
        # determine fetch termination for time-blocks

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

        # already asserted that 'data' key exists
        resp_json: List[dict] = response.json()['data']
        ratelimit_remaining = response.headers.get("X-RateLimit-Remaining")
        ratelimit_reset = response.headers.get("X-RateLimit-Reset")

        assert ratelimit_remaining is not None and ratelimit_reset is not None, \
            'X-RateLimit header was expected from response, but not found!'
        await self.limiter.update(ratelimit_remaining, ratelimit_reset)

        result_count = len(resp_json)
        self.logger.info(f"GET Recieved: "
                         f"res-count: {result_count} | "
                         f"ratelimit-remaining: {ratelimit_remaining} | "
                         f"ratelimit-reset: {ratelimit_reset}")

        return resp_json if not return_count else (resp_json, result_count)

    async def _fetch_post_comments(self,
                                   client: AsyncClient,
                                   settings: ArcticShiftModel) -> List[dict]:
        # would be triggered when fetch_post_comments exists, but still...
        assert settings.fetch_post_comments, \
            '`fetch_post_comments` needs to be set properly for it to fetch comments.'

        raise NotImplementedError()
        # TODO: 어떻게 ID 회수를 해서 fetching을 해야하나?

