from .base_service import BaseService
from BAScraper.service_types import ArcticShiftModel
from BAScraper.utils import AdaptiveRateLimiter

import json
import logging
from math import ceil
from typing import List, Tuple, Literal, overload
from httpx import AsyncClient
from urllib.parse import urljoin
from asyncio import Queue
from tenacity import RetryError

TSettings = ArcticShiftModel
END = "<END>"


class ArcticShift(BaseService[ArcticShiftModel]):
    def __init__(self, settings: ArcticShiftModel) -> None:
        super().__init__(settings)
        self.logger = logging.getLogger(__name__)
        # TODO: expose granular control paramters (no hardcoded params)
        self.limiter = AdaptiveRateLimiter(safety_margin=1)

    # https://peps.python.org/pep-0484/#function-method-overloading
    @overload  # for static type checking
    async def _fetch_once(
        self,
        client: AsyncClient,
        settings: ArcticShiftModel,
        link_ids: Queue[str],
        return_count: Literal[False] = False,
    ) -> List[dict]: ...

    @overload  # for static type checking
    async def _fetch_once(
        self,
        client: AsyncClient,
        settings: ArcticShiftModel,
        link_ids: Queue[str],
        return_count: Literal[True],
    ) -> Tuple[List[dict], int]: ...

    async def _fetch_once(
        self,
        client: AsyncClient,
        settings: ArcticShiftModel,
        link_ids: Queue[str],
        return_count: bool = False,
    ) -> List[dict] | Tuple[List[dict], int]:
        # !! `return_count=True` is only used by `_fetch_time_window` !!
        # return_count returns the "count of posts/comments"
        # used for time window fetching which needs this to
        # determine fetch termination for time-blocks

        params = settings.model_dump(exclude_none=True)
        url = urljoin(settings._BASE_URL, f"{settings.endpoint}/{settings.lookup}")

        await self.wait_for_ratelimit_clear()
        await self.limiter.acquire()
        response = await client.get(url=url, params=params)
        response = await self.response_code_handler(response)

        # already asserted that 'data' key exists @ response_code_handler
        resp_json: List[dict] = response.json()["data"]
        ratelimit_remaining = response.headers.get("X-RateLimit-Remaining")
        ratelimit_reset = response.headers.get("X-RateLimit-Reset")

        assert ratelimit_remaining is not None and ratelimit_reset is not None, (
            "X-RateLimit header was expected from response, but not found!"
        )
        await self.limiter.update(ratelimit_remaining, ratelimit_reset)

        result_count = len(resp_json)
        self.logger.info(
            f"GET Recieved: "
            f"res-count: {result_count} | "
            f"ratelimit-remaining: {ratelimit_remaining} | "
            f"ratelimit-reset: {ratelimit_reset}"
        )

        if settings.fetch_post_comments:  # populate the Queue for comment fetching
            for elem in resp_json:
                await link_ids.put(elem["id"])

        return resp_json if not return_count else (resp_json, result_count)

    async def _fetch_time_window(
        self,
        client: AsyncClient,
        settings: ArcticShiftModel,
        link_ids: Queue[str],
        worker_id: int = -1,
    ) -> List[dict]:
        # !! for type checker suppression !!
        # both are already converted to (utc) int in the Model but IDE complains...
        assert isinstance(settings.after, int) and isinstance(settings.before, int)

        cursor: int = settings.before  # start point cursor
        start_time: int = settings.before
        end_time: int = settings.after
        temp_file = self.create_tempfile("_tempfile.json")
        data: List[dict] = list()
        retry_fetch_once = self.service_retry(self._fetch_once)

        try:
            # condition is not rly need in practice but just in case to prevent inf loop
            while cursor > end_time:
                settings.before = cursor
                try:
                    resp_json, result_count = await retry_fetch_once(client, settings, link_ids, True)
                except RetryError as err:
                    # !! tenacity.RetryError is when retry options are exhausted !!
                    self.logger.error(
                        f"worker-{worker_id} Maximum retry reached for cursor={cursor}! Aborting...\n{err}"
                    )
                    break

                if result_count <= 0:
                    break

                cursor = int(resp_json[-1]["created_utc"])
                data += resp_json
                # TODO: simple json.dump results in invalid json,
                # either concat as jsonl or use proper parsing
                json.dump(resp_json, temp_file)

                self.logger.info(
                    f"worker-{worker_id} progress: "
                    f"{ceil((start_time - cursor) / (start_time - end_time) * 100)}%"
                )
        except KeyboardInterrupt:
            self.logger.error(f"worker-{worker_id} Has been cancelled!")
        finally:
            self.cleanup_tempfile(temp_file)

        return data

    async def _fetch_post_comments(
        self,
        client: AsyncClient,
        settings: ArcticShiftModel,
        link_ids: Queue[str],
        worker_id: int = -1,
    ) -> List[List[dict]]:
        temp_file = self.create_tempfile("_comments_tempfile.json")
        data: List[List[dict]] = list()
        # Build and validate once per worker; only `link_id` changes per request.
        comment_settings: ArcticShiftModel | None = None
        """
        data = [
            [{comment 1}, {comment 2}, ...],  # comment tree for submission 1
            [{comment 1}, {comment 2}, ...],  # comment tree for submission 2
            ...
        ]
        """

        async def get_comment_tree(current_id: str) -> List[dict]:
            nonlocal comment_settings
            if comment_settings is None:
                comment_settings = ArcticShiftModel(
                    endpoint="comments",
                    lookup="tree",
                    no_workers=settings.no_sub_comment_workers,
                    limit=25000,
                    link_id=current_id,
                    timezone=settings.timezone,
                    interval_sleep_ms=settings.interval_sleep_ms,
                    cooldown_sleep_ms=settings.cooldown_sleep_ms,
                    max_retries=settings.max_retries,
                    backoff_factor=settings.backoff_factor,
                )
            else:
                comment_settings.link_id = current_id

            result = await self._fetch_once(
                client,
                comment_settings,
                link_ids,
            )
            json.dump(result, temp_file)
            return result

        retry_get_comment_tree = self.service_retry(get_comment_tree)

        try:
            while True:  # main consumer loop
                current_id = await link_ids.get()

                if current_id == END:  # check for sentinel token
                    link_ids.task_done()
                    return data

                try:
                    tree = await retry_get_comment_tree(current_id)
                except RetryError:
                    self.logger.error(f"Worker-{worker_id}: Max retries for item! Skipping.")
                    link_ids.task_done()
                    continue

                data.append([d["data"] for d in tree])
                link_ids.task_done()
                self.logger.info(f"Remaining comment queue: {link_ids.qsize()}")
        except KeyboardInterrupt as err:
            self.logger.error(f"Worker-{worker_id}: Cancelled.")
            raise err
        finally:
            self.cleanup_tempfile(temp_file)
