from typing import Union, List, Tuple, overload, Dict
import httpx
import asyncio
import math
import logging
from tqdm import tqdm

from BAScraper.service_types import PullPushModel, ArcticShiftModel
from BAScraper.services import PullPush, ArcticShift
from BAScraper.utils import BAConfig

END = "<END>"


class BAScraper:
    # Note that `v_settings` mean "verified/validated settings"
    # which went through custom validations and/or `.model_validate`
    def __init__(self, config: BAConfig | None = None):
        if config is None:
            config = BAConfig()
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.logger.debug("Init complete.")

    async def get(self, settings: Union[PullPushModel, ArcticShiftModel, dict]) -> dict:

        v_settings, fetcher = self._match_settings(settings)

        # will only be used when settings.fetch_post_comments is true,
        # still needed regardless of use cause function interface needs this
        link_id_queue: asyncio.Queue[str] = asyncio.Queue()

        # time partitioned auto pagination trigger
        if v_settings.after and v_settings.before:
            # `after` and `before` is validated/processed to be int(epoch)
            # but type checker still thinks it can be datetime
            # so this part, though redundant, is needed. (and also just in case)
            assert isinstance(v_settings.after, int) and isinstance(v_settings.before, int)

            # split-up time ranges into segments
            # !! after/before are inclusive for the API endpoints !!
            segment_duration = (v_settings.before - v_settings.after) / v_settings.no_workers
            segments = [
                [
                    math.ceil(v_settings.after + s * segment_duration),
                    math.ceil((v_settings.after + (s + 1) * segment_duration)) - 1,
                ]
                for s in range(v_settings.no_workers)
            ]
            self.logger.debug(f"segments for coro: {segments}")

            # clamping the final end time to be exactly `before`
            segments[-1][-1] = v_settings.before

            tasks: Dict[str, List[asyncio.Task[List]]] = {
                "submissions": [],
                "comment_trees": [],  # for comment fetching from submissions
            }

            async with (
                httpx.AsyncClient(http2=True) as client,
                asyncio.TaskGroup() as tg,
            ):
                if isinstance(fetcher, PullPush):
                    assert isinstance(v_settings, PullPushModel)
                    self._schedule_workers(
                        tg=tg,
                        tasks=tasks,
                        client=client,
                        fetcher=fetcher,
                        settings=v_settings,
                        segments=segments,
                        link_ids=link_id_queue,
                    )
                elif isinstance(fetcher, ArcticShift):
                    assert isinstance(v_settings, ArcticShiftModel)
                    self._schedule_workers(
                        tg=tg,
                        tasks=tasks,
                        client=client,
                        fetcher=fetcher,
                        settings=v_settings,
                        segments=segments,
                        link_ids=link_id_queue,
                    )
                else:
                    raise TypeError("fetcher(service) & settings mismatch")

                if v_settings.fetch_post_comments:
                    # wait for producer completion
                    await asyncio.gather(*tasks["submissions"])
                    for _ in range(v_settings.no_sub_comment_workers):
                        await link_id_queue.put(END)

            # segments are in reverse order (set to "new -> old")
            tasks["submissions"].reverse()

            submissions: Dict[str, dict] = dict()
            for task in tqdm(tasks["submissions"], dynamic_ncols=True, desc="indexing submissions"):
                # indexing: base36 id as key and json data as val
                _submissions: Dict[str, dict] = {submission["id"]: submission for submission in task.result()}
                conflicts = submissions.keys() & _submissions.keys()

                if conflicts:
                    self.logger.warning(f"Conflicts in submissions found!: \n{conflicts}")

                submissions = submissions | _submissions

            # add comment to submission results if flag enabled
            if v_settings.fetch_post_comments:
                for elem in submissions.values():
                    elem["comments"] = list()

                for task in tqdm(tasks["comment_trees"], dynamic_ncols=True, desc="inserting comments"):
                    for comment_tree in task.result():
                        if comment_tree:  # empty results may exist
                            # link_id is same for all comment result within the same tree
                            # [3:] is to remove the "t3_xxx" prefix for the link_id
                            link_id = comment_tree[0]["link_id"][3:]
                            submissions[link_id]["comments"] = comment_tree

            return submissions

        # no time partitioned pagination, just single request to the endpoint
        else:
            # TODO: post comment fetching is NOT implemented
            single_result: List[dict]
            async with httpx.AsyncClient(http2=True) as client:
                if isinstance(fetcher, PullPush):
                    assert isinstance(v_settings, PullPushModel)
                    single_result = await fetcher.fetch_once(client, v_settings, link_id_queue)
                elif isinstance(fetcher, ArcticShift):
                    assert isinstance(v_settings, ArcticShiftModel)
                    single_result = await fetcher.fetch_once(client, v_settings, link_id_queue)
                else:
                    raise TypeError("fetcher(service) & settings mismatch")

            return {ent.pop("id"): ent for ent in single_result}

    @overload
    def _schedule_workers(
        self,
        tg: asyncio.TaskGroup,
        tasks: Dict[str, List[asyncio.Task[list]]],
        client: httpx.AsyncClient,
        fetcher: PullPush,
        settings: PullPushModel,
        segments: List[List[int]],
        link_ids: asyncio.Queue[str],
    ) -> None: ...

    @overload
    def _schedule_workers(
        self,
        tg: asyncio.TaskGroup,
        tasks: Dict[str, List[asyncio.Task[list]]],
        client: httpx.AsyncClient,
        fetcher: ArcticShift,
        settings: ArcticShiftModel,
        segments: List[List[int]],
        link_ids: asyncio.Queue[str],
    ) -> None: ...

    def _schedule_workers(
        self,
        tg: asyncio.TaskGroup,
        tasks: Dict[str, List[asyncio.Task[list]]],
        client: httpx.AsyncClient,
        fetcher: PullPush | ArcticShift,
        settings: PullPushModel | ArcticShiftModel,
        segments: List[List[int]],
        link_ids: asyncio.Queue[str],
    ) -> None:
        if isinstance(fetcher, PullPush):
            assert isinstance(settings, PullPushModel)
        elif isinstance(fetcher, ArcticShift):
            assert isinstance(settings, ArcticShiftModel)
        else:
            raise TypeError("fetcher(service) & settings mismatch")

        service_name = type(fetcher).__name__
        for i, (after, before) in enumerate(segments):
            segment_settings = settings.model_copy(update={"after": after, "before": before})
            tasks["submissions"].append(
                tg.create_task(fetcher.fetch_time_window(client, segment_settings, link_ids, i))
            )
            self.logger.info(f"{service_name} worker-{i} for {[after, before]} created")

        # create link_id CONSUMER for comment fetching
        if settings.fetch_post_comments:
            for i in range(settings.no_sub_comment_workers):
                tasks["comment_trees"].append(
                    tg.create_task(fetcher.fetch_post_comments(client, settings, link_ids, i))
                )
                self.logger.info(f"{service_name} comment-sub-worker-{i} created")
            tg.create_task(link_ids.join())

    @overload
    def _match_settings(self, settings: PullPushModel) -> Tuple[PullPushModel, PullPush]: ...

    @overload
    def _match_settings(self, settings: ArcticShiftModel) -> Tuple[ArcticShiftModel, ArcticShift]: ...

    @overload
    def _match_settings(
        self, settings: dict
    ) -> Tuple[PullPushModel | ArcticShiftModel, PullPush | ArcticShift]: ...

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
                    service_name = settings["service_type"]
                except KeyError:
                    raise ValueError(
                        "`service_type` needs to exist to use dict input (to set the service type)"
                    )

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
                        raise ValueError("`service_type` needs to be either 'PullPush' or 'ArcticShift'")
            case _:
                raise TypeError(
                    "Wrong setting type for `get`, needs to be one of PullPushModel, ArcticShiftModel or dict"
                )
