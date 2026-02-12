from typing import Union, List, Tuple
import httpx
import asyncio
import math
import logging

from BAScraper.service_types import PullPushModel, ArcticShiftModel
from BAScraper.services import PullPush, ArcticShift
from BAScraper.utils import BAConfig

class BAScraper:
    # Note that `v_settings` mean "verified/validated settings"
    # which went through custom validations and/or `.model_validate`
    def __init__(self, config: BAConfig | None = None):
        if config is None:
            config = BAConfig()
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.logger.debug('Init complete.')

    async def get(self, settings: Union[PullPushModel, ArcticShiftModel, dict]) -> dict:

        v_settings, fetcher = self._match_settings(settings)

        # time partitioned auto pagination trigger
        if v_settings.after and v_settings.before:
            # `after` and `before` is validated/processed to be int(epoch)
            # but type checker still thinks it can be datetime
            # so this part, though redundant, is needed. (and also just in case)
            assert (
                isinstance(v_settings.after, int) and
                isinstance(v_settings.before, int)
            )

            # split-up time ranges into segments
            # !! after/before are inclusive for the API endpoints !!
            segment_duration = (v_settings.before - v_settings.after) / v_settings.no_workers
            segments = [
                [
                    math.ceil(v_settings.after + s * segment_duration),
                    math.ceil((v_settings.after + (s + 1) * segment_duration)) - 1
                ]
                for s in range(v_settings.no_workers)
            ]
            self.logger.debug(f'segments for coro: {segments}')

            # clamping the final end time to be exactly `before`
            segments[-1][-1] = v_settings.before

            tasks: List[asyncio.Task] = []

            async with httpx.AsyncClient(http2=True) as client, asyncio.TaskGroup() as tg:
                match (fetcher, v_settings):
                    case (PullPush(), PullPushModel()):
                        for i, segment in enumerate(segments):
                            v_settings_temp_P: PullPushModel = v_settings.model_copy()
                            v_settings_temp_P.after, v_settings_temp_P.before = segment
                            tasks.append(tg.create_task(
                                fetcher.fetch_time_window(
                                    client, v_settings_temp_P, i
                                )
                            ))
                            self.logger.info(f"PullPush worker-{i} for {segment} created")
                    case (ArcticShift(), ArcticShiftModel()):
                        for i, segment in enumerate(segments):
                            v_settings_temp_A: ArcticShiftModel = v_settings.model_copy()
                            v_settings_temp_A.after, v_settings_temp_A.before = segment
                            tasks.append(tg.create_task(
                                fetcher.fetch_time_window(
                                    client, v_settings_temp_A, i
                                )
                            ))
                            self.logger.info(f"ArcticShift worker-{i} for {segment} created")
                    case _:
                        raise TypeError("fetcher(service) & settings mismatch")

            tasks.reverse()  # segments are in reverse order (set to "new -> old")
            results_temp = list()
            for task in tasks:
                results_temp += task.result()

            # indexing: base36 id as key and json data as val
            return {ent.pop('id') : ent for ent in results_temp}

        # no time partitioned pagination, just single request to the endpoint
        else:
            v_settings, fetcher = self._match_settings(settings)
            single_result: List[dict]
            async with httpx.AsyncClient(http2=True) as client:
                match (fetcher, v_settings):
                    case (PullPush(), PullPushModel()):
                        single_result = await fetcher.fetch_once(client, v_settings)
                    case (ArcticShift(), ArcticShiftModel()):
                        single_result = await fetcher.fetch_once(client, v_settings)
                    case _:
                        raise TypeError("fetcher(service) & settings mismatch")

            return {ent.pop('id') : ent for ent in single_result}

    def _match_settings(
            self, settings: Union[PullPushModel, ArcticShiftModel, dict]
        ) -> Tuple[PullPushModel | ArcticShiftModel, PullPush | ArcticShift]:

        v_settings: PullPushModel | ArcticShiftModel
        fetcher: PullPush | ArcticShift

        # https://peps.python.org/pep-0636/#adding-a-ui-matching-objects
        match settings:
            case PullPushModel():
                return settings, PullPush(settings)

            case ArcticShiftModel():
                return settings, ArcticShift(settings)

            case dict():
                # service_type param needs to be added in the settings dict
                # cannot determine model type without it.
                try:
                    service_name = settings['service_type']
                except KeyError:
                    raise ValueError(
                    "`service_type` needs to exist to use dict input (to set the service type)")

                match service_name:
                    case "PullPush":
                        v_settings = PullPushModel.model_validate(settings)
                        fetcher = PullPush(v_settings)
                        return v_settings, fetcher
                    case "ArcticShift":
                        v_settings = ArcticShiftModel.model_validate(settings)
                        fetcher = ArcticShift(v_settings)
                        return v_settings, fetcher
                    case _:
                        raise ValueError(
                            "`service_type` needs to be either 'PullPush' or 'ArcticShift'")
            case _:
                raise TypeError("Wrong setting type for `get`, " \
                "needs to be one of PullPushModel, ArcticShiftModel or dict")
