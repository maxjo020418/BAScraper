from typing import Union, Callable
import httpx
import asyncio
import math
import logging

from BAScraper.service_types import PullPushModel, ArcticShiftModel
from BAScraper.services import PullPush, ArcticShift
from BAScraper.utils import BAConfig

class BAScraper:
    def __init__(self, config: BAConfig | None = None):
        if config is None:
            config = BAConfig()
        self.logger = logging.getLogger(__name__)
        self.timezone = config.timezone
        self.logger.debug('Init complete.')

    async def get(self, settings: Union[PullPushModel, ArcticShiftModel, dict]):

        v_settings: PullPushModel | ArcticShiftModel
        fetcher: PullPush | ArcticShift

        # https://peps.python.org/pep-0636/#adding-a-ui-matching-objects
        match settings:
            case PullPushModel():
                v_settings = settings
                fetcher = PullPush(v_settings)
            case ArcticShiftModel():
                v_settings = settings
                fetcher = ArcticShift(v_settings)
            case dict():  # service_type param needs to be added in the settings dict
                try: 
                    service_name = settings['service_type']
                except: raise ValueError(
                    "`service_type` needs to exist to use dict input (to set the service type)")
                match service_name:
                    case "PullPush":
                        v_settings = PullPushModel.model_validate(settings)
                        fetcher = PullPush(v_settings)
                    case "ArcticShift":
                        v_settings = ArcticShiftModel.model_validate(settings)
                        fetcher = ArcticShift(v_settings)
                    case _:
                        raise ValueError("`service_type` needs to be either 'PullPush' or 'ArcticShift'")
            case _:
                raise TypeError("Wrong setting type for `get`, " \
                "needs to be one of PullPushModel, ArcticShiftModel or dict")

        # time partitioned auto pagination
        if v_settings.after and v_settings.before:
            # after and before is validated/processed to be int but type checker still thinks it can be datetime
            # so this part, though redundant, is needed.
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
            self.logger.info(f'segments for coro: {segments}')
            
            # clamping the final end time to be exactly `before`
            segments[-1][-1] = v_settings.before

            semaphore = asyncio.Semaphore(v_settings.no_coro)

            async with httpx.AsyncClient(http2=True) as client:
                pass
        
        else:  # no time partitioned pagination, just single request to the endpoint
            pass
