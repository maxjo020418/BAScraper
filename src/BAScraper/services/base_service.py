from asyncio import Semaphore, Event, Lock
import httpx
from httpx import AsyncClient
import logging
from tenacity import (
    retry, 
    wait_random_exponential, 
    stop_after_attempt, 
    before_sleep_log, 
    retry_if_exception_type
)

from BAScraper.service_types import ArcticShiftModel, PullPushModel

# TODO: check if there are duplicate results and add duplicate handling if needed.

class BaseService:
    NOT_PARAMETER = {
        "_BASE_URL", "service_type", "endpoint", "lookup", 
        "no_coro", "interval_sleep_ms", "max_retries", "backoff_factor"
    }

    def __init__(self, settings: PullPushModel | ArcticShiftModel) -> None:
        self.logger = logging.getLogger(__name__)
        self.lock = Lock()
        self.interval_sleep_ms = settings.interval_sleep_ms

        # True `.set()` if it's okay to proceed
        self.rate_limit_clear = Event()
        self.rate_limit_clear.set()

        self.service_retry = retry(  # retry decorator
            wait=wait_random_exponential(multiplier=1, min=1, max=20),
            stop=stop_after_attempt(settings.max_retries),
            before_sleep=before_sleep_log(self.logger, logging.WARNING),
            retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException))
        )
    
    async def get_segment(self, client: AsyncClient, semaphore: Semaphore, settings):
        raise NotImplementedError('Not for direct use')

    async def get_single_page(self, client: AsyncClient, settings):
        raise NotImplementedError('Not for direct use')
    
    async def get_comments_for_post(self, client: AsyncClient, semaphore: Semaphore, settings):
        raise NotImplementedError('Not for direct use')
