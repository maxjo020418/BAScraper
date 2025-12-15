from typing import Union
import httpx
import asyncio
import math

from BAScraper.service_types import PullPushModel, ArcticShiftModel

async def get(settings: Union[PullPushModel, dict]):
    if not isinstance(settings, PullPushModel):
        v_settings: PullPushModel = PullPushModel.model_validate(settings)
    else:
        v_settings = settings
    
    # time partitioned auto pagination
    if v_settings.after and v_settings.before:
        # after and before is set to int but type checker still thinks it can be datetime
        # so this part though redundant, is needed.
        assert isinstance(v_settings.after, int) and isinstance(v_settings.before, int)
        
        # split-up time ranges into segments
        # after/before are inclusive for the API endpoints
        segment_duration = (v_settings.before - v_settings.after) / v_settings.no_coro
        segments = [
            [
                math.ceil(v_settings.after + s * segment_duration),
                math.ceil((v_settings.after + (s + 1) * segment_duration)) - 1
            ]
            for s in range(v_settings.no_coro)
        ]
        
        # clamping the final end time to be exactly `before`
        segments[-1][-1] = v_settings.before

        async with httpx.AsyncClient(http2=True) as client:
            pass
    
    else:  # no time partitioned pagination, just single request to the endpoint
        pass
