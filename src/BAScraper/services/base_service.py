from asyncio import Event, Lock, Queue
import asyncio
import httpx
from httpx import AsyncClient, Response
import logging
import tempfile
import os
from typing import (
    Generic,
    TypeVar,
    List,
    Tuple,
    Literal,
    Callable,
    Awaitable,
    overload)
from tenacity import (
    retry,
    wait_random_exponential,
    stop_after_attempt,
    before_sleep_log,
    retry_if_exception_type,
    RetryError
)

from BAScraper.service_types import ArcticShiftModel, PullPushModel

TSettings = TypeVar("TSettings", PullPushModel, ArcticShiftModel)
T = TypeVar('T')

class BaseService(Generic[TSettings]):
    class RateLimitRetry(Exception):
        """Raised to manually trigger the tenacity retry loop."""
        pass

    def __init__(self, settings: TSettings) -> None:
        self.logger = logging.getLogger(__name__)
        self.lock = Lock()

        self.interval_sleep_ms = settings.interval_sleep_ms
        self.cooldown_sleep_ms = settings.cooldown_sleep_ms

        self.rate_limit_clear = Event()
        self.rate_limit_clear.set()  # `.set()` if it's okay to proceed

        self.retryable_exception = (
            httpx.NetworkError,
            httpx.TimeoutException,
            self.RateLimitRetry
        )
        self.service_retry = retry(  # retry decorator func.
            wait=wait_random_exponential(multiplier=settings.backoff_factor,
                                         min=1, max=10),
            stop=stop_after_attempt(settings.max_retries),
            before_sleep=before_sleep_log(self.logger, logging.WARNING),
            retry=retry_if_exception_type(self.retryable_exception)
        )

    async def response_code_handler(self, response: Response) -> Response:
        """
        will check the response code and raise appropriate exceptions.

        tenacity's retry will only trigger when exception is raised,
        no exception is raised for 429 ratelimit somehow,
        so manual "raise exception" is needed! (RateLimitRetry will be raised)
        (thundering herd will be prevented via wait_random_exponential)

        For ArcticShift, `X-RateLimit-Reset` is used for cooldown,
        default cooldown time (for ratelimit events) is waiting for
        cooldown_sleep_ms (5000ms default, adjustable).
        """
        match response.status_code:
            case 429:
                self.rate_limit_clear.clear()  # stop all async jobs
                ratelimit_reset = \
                    int(response.headers.get("X-RateLimit-Reset", self.cooldown_sleep_ms))
                self.logger.warning(
                    "Rate limit reached!\n"
                    f"Ratelimit reset/cooldown time: {ratelimit_reset}\n"
                    "Sleeping until ratelimit cooldown..."
                )
                # TODO:
                #   check if this is safe? Never tested if this actually works
                #   as in: I've never hit the ratelimit_reset reliably
                await asyncio.sleep(ratelimit_reset)
                self.rate_limit_clear.set()
                raise self.RateLimitRetry()  # should trigger retry
            case 422:
                # ArcticShift occasionally returns 422 for some reason
                # (retrying works for some reason...)
                self.logger.warning(
                    "HTTP 422 from %s - retrying. Response body: %s",
                    response.request.url,
                    response.text[:1000],
                )
                raise self.RateLimitRetry()  # should trigger retry
            case _:
                # not implemented for each error codes (4xx, 5xx)
                # just throw exception for now
                ...

        assert "data" in response.json(), \
            "Cannot find `data` in response json, maybe malformed response?" \
                f"Response body: {response.text}"

        return response.raise_for_status()

    async def response_exception_handler(
            self, *,
            op: Callable[[], Awaitable[T]],
            on_retryable: Callable[[BaseException], Awaitable[T]],
            on_terminal_retryable: Callable[[BaseException], Awaitable[T]],
            on_cancel: Callable[[BaseException], Awaitable[T]],
            on_final: Callable[[], Awaitable[None]]
        ) -> T:
        '''
        unified try/except/else block for reqeust handling, handles common exceptions.
        use with `response_code_handler` to get appropriate exception thrown inside `op`
        '''
        try:
            return await op()

        except self.retryable_exception as err:
            return await on_retryable(err)

        except RetryError as err:
            return await on_terminal_retryable(err)

        except KeyboardInterrupt as err:
            return await on_cancel(err)

        finally:
            await on_final()

    def create_tempfile(self, file_suffix: str, dir: str = "./") -> tempfile._TemporaryFileWrapper:
        temp_file = tempfile.NamedTemporaryFile(mode="w+", dir=dir,
                                                prefix="BAScraper_",
                                                suffix=file_suffix,
                                                delete=False)
        self.logger.info(f"temp file created as: {temp_file.name}")
        return temp_file

    def cleanup_tempfile(self, temp_file: tempfile._TemporaryFileWrapper):
            temp_file.flush()
            temp_file.close()
            self.logger.info(f"cleaning up tempfile '{temp_file.name}'...")
            os.unlink(temp_file.name)

    ### wrappers for the actual function (to include the retry function) ###

    async def fetch_time_window(self,
                                client: AsyncClient,
                                settings: TSettings,
                                link_ids: Queue[str],
                                worker_id: int) -> List[dict]:
        return await self.service_retry \
            (self._fetch_time_window)(client, settings, link_ids, worker_id)

    async def fetch_once(self,
                         client: AsyncClient,
                         settings: TSettings,
                         link_ids: Queue[str]) -> List[dict]:
        return await self.service_retry(self._fetch_once)(client, settings, link_ids)

    async def fetch_post_comments(self,
                                  client: AsyncClient,
                                  settings: TSettings,
                                  link_ids: Queue[str],
                                  worker_id: int = -1) -> List[dict]:
        return await self.service_retry \
            (self._fetch_post_comments)(client, settings, link_ids, worker_id)

    ### actual logics for requesting ###

    @overload
    async def _fetch_once(self,
                          client: AsyncClient,
                          settings: TSettings,
                          link_ids: Queue[str],
                          return_count: Literal[False] = False,
                          ) -> List[dict]: ...

    @overload
    async def _fetch_once(self,
                          client: AsyncClient,
                          settings: TSettings,
                          link_ids: Queue[str],
                          return_count: Literal[True],
                          ) -> Tuple[List[dict], int]: ...

    async def _fetch_once(self,
                          client: AsyncClient,
                          settings: TSettings,
                          link_ids: Queue[str],
                          return_count: bool = False,  # only used by `_fetch_time_window`
                          ) -> List[dict] | Tuple[List[dict], int]:
        raise NotImplementedError('Not for direct use')

    async def _fetch_time_window(self,
                                 client: AsyncClient,
                                 settings: TSettings,
                                 link_ids: Queue[str],
                                 worker_id: int) -> List[dict]:
        raise NotImplementedError('Not for direct use')

    async def _fetch_post_comments(self,
                                   client: AsyncClient,
                                   settings: TSettings,
                                   link_ids: Queue[str],
                                   worker_id: int = -1) -> List[dict]:
        raise NotImplementedError('Not for direct use')


    ### helper functions ###

    # TODO: check if there are duplicate results and add duplicate handling if needed.
    async def parse_response(self, response: Response):
        raise NotImplementedError('Not for direct use')
