from typing import Union
import httpx
import asyncio

from BAScraper.service_types import PullPushModel, ArcticShiftModel

async def get(settings: Union[PullPushModel, dict]):
    if not isinstance(settings, PullPushModel):
        v_settings: PullPushModel = PullPushModel.model_validate(settings)

    # TODO: verify http/2 usage(how to leverage) and maybe configurable
    async with httpx.AsyncClient(http2=True) as client:
        async with asyncio.TaskGroup() as tg:
            pass
