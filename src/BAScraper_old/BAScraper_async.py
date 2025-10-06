import datetime
import logging
import os
from tempfile import TemporaryDirectory
from typing import Union, Callable, Optional
from functools import wraps

from BAScraper_old.utils import *
from .services import Params

# TODO: for docs =>
#  1. recommend to make multiple kinds of requests under the same PullPushAsync class.
#  (needs to share some values like timeout stuffs)
#  also need to mention that restarting the script would reset the used up pool values,
#  so users need to keep that in mind

def iso_to_epoch(iso: str) -> int:
    return datetime.fromisoformat(iso).timestamp()

class BaseAsync:
    def __init__(self,
                 sleep_sec: float = 1,
                 backoff_sec: float = 3,
                 max_retries: int = 5,
                 timeout: float = 10,
                 save_dir=os.getcwd(),
                 task_num=3,
                 comment_task_num=None,
                 log_stream_level: str = 'INFO',
                 log_level: str = 'DEBUG',
                 duplicate_action: str = 'keep_newest') -> None:
        self.sleep_sec = sleep_sec
        self.backoff_sec = backoff_sec
        self.max_retries = max_retries
        self.timeout = timeout
        self.save_dir = save_dir
        self.task_num = task_num
        self.comment_task_num = comment_task_num if comment_task_num is not None else task_num

        self.SERVICE = Params.Base()
        self.PACE_MODES = ['auto-soft', 'auto-hard', 'auto-header', 'manual']

        assert duplicate_action in ['keep_newest', 'keep_oldest', 'remove', 'keep_original', 'keep_removed'], \
            ("`duplicate_action` should be one of "
             "['keep_newest', 'keep_oldest', 'remove', 'keep_original', 'keep_removed']")
        self.duplicate_action = duplicate_action

        log_levels = ['NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        assert log_stream_level in log_levels and log_level in log_levels, \
            '`log_level` should be a string representation of logging level such as `INFO`'

        self.logger = logging.getLogger(__name__)
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s: %(message)s',
                            filename=os.path.join(self.save_dir, 'request_log.log'),
                            filemode='w',
                            level=log_level)

        if not self.logger.handlers:
            ch = logging.StreamHandler()
            ch.setLevel(log_stream_level)
            ch.setFormatter(logging.Formatter('%(asctime)s: %(levelname)s - %(message)s'))
            self.logger.addHandler(ch)

        self.last_refilled = time.time()
        self.temp_dir: Union[TemporaryDirectory, None] = None

    async def fetch(self, mode: str, **params):
        raise NotImplementedError("BaseAsync must implement the `fetch` method.")

    async def _multi_requests(self, mode: str, params: dict,
                              # manual override parameters
                              task_num: int = None,
                              loop_elems: tuple[str, asyncio.Queue] = None) -> dict:
        """
        :param mode:
        :param params:
        :param task_num:
        :param loop_elems:
             tuple of [k: param to modify/add] and [v: list of values for that]
        :return:

        by default, it would loop through the dates to overcome the "returned results per request" limitations
        if overridden via 'manual override parameters', would loop through based on loop_params
        (based on the key value in the `params`)
        """
        task_num = task_num if task_num is not None else self.task_num
        overridden = True if loop_elems is not None else False
        loop_segments = loop_elems if overridden \
            else split_range(params['after'], params['before'], task_num)
            # segment time is from oldest -> newest for default

        self.logger.debug(f'starting with service: {self.SERVICE}')
        self.logger.debug(f'starting _multi_requests with task_num={task_num}')
        if overridden:
            self.logger.debug(f'_multi_requests was overridden by {loop_elems}')

        async with asyncio.TaskGroup() as tg:
            tasks = list()
            self.logger.debug(f'Segment ranges: {loop_segments}')
            for seg_num in range(task_num):
                if not overridden:  # for default settings
                    params['after'], params['before'] = loop_segments[seg_num]
                    self.logger.debug(f'coro-{seg_num + 1} | after: {params["after"]}, before: {params["before"]}')
                    tasks.append(tg.create_task(make_request_time_pagination(self, mode, **params),
                                                name=f'coro-{seg_num + 1}'))
                else:  # overridden
                    async def override_worker() -> list:
                        coro_name = asyncio.current_task().get_name()
                        res = list()
                        q = loop_elems[1]
                        k = loop_elems[0]
                        while not q.empty():
                            elem = await q.get()
                            q.task_done()  # Mark the task as done (needed for asyncio.Queue consumers)
                            params[k] = elem

                            self.logger.debug(f'{coro_name} | custom param info: {k}: {elem}')
                            res += await make_request(self, mode, **params)
                            self.logger.info(f'{q.qsize()} items left')

                        return res

                    self.logger.debug(
                        f'coro-{seg_num + 1} | custom param multi_req. ready for {loop_elems[0]}')
                    tasks.append(tg.create_task(override_worker(), name=f'coro-{seg_num + 1}'))

        return preprocess_json(self, [res for task in tasks for res in task.result()])

    def _validate_and_set_params(self, params: dict, mode: str):
        raise NotImplementedError("BaseAsync must implement the `_validate_and_set_params` method.")

    async def _fetch_comments(self, result, mode,
                              extra_preprocess: Callable[[dict], dict] = None) -> dict:
        self.logger.info(f'=== Fetching comments under submissions ===')
        submission_ids = asyncio.Queue()
        for submission_id in result.keys():  # enqueue all the submission ids
            await submission_ids.put(submission_id)
        comments = await self._multi_requests(mode, {}, self.task_num,
                                              ('link_id', submission_ids))
        for submission in result.values():
            submission.update({'comments': []})
        for comment in comments.values():
            try:
                comment_link_id = comment['link_id'][3:]  # [3:] because of 't3_' prefix
                if extra_preprocess is not None:
                    result[comment_link_id]['comments'].append(extra_preprocess(comment))
                else:
                    result[comment_link_id]['comments'].append(comment)
            except TypeError:
                # sometimes 'link_id' is empty, corruption or deletion?
                self.logger.warning('missing comment info! passing...')

        return result

    def catch_taskgroup_err(self, mode: str) -> Callable:
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs) -> Callable:
                self.temp_dir = TemporaryDirectory(prefix=f'BAScraper-{mode}-temp_', dir=self.save_dir, delete=False)
                self.logger.debug(f'Temp directory created: {self.temp_dir.name}')
                try:
                    result = await func(*args, **kwargs)  # func execution here

                except* (asyncio.exceptions.CancelledError, asyncio.CancelledError) as err:
                    self.logger.error(f'Task has been cancelled!: {err.exceptions}')

                except* (KeyboardInterrupt, SystemExit) as err:
                    self.logger.error(f'terminated by user or system!: {err.exceptions}')

                except* Exception as err:
                    self.logger.error(f"Unexpected error during fetch: {err}")
                    for sub_err in err.exceptions:
                        self.logger.error(f"Sub-exception: {sub_err}")
                        raise sub_err

                else:
                    if self.temp_dir:
                        self.logger.debug('cleaning up temp dir...')
                        self.temp_dir.cleanup()
                    return result

                finally:
                    pass

            return wrapper
        return decorator


class PullPushAsync(BaseAsync):
    def __init__(self, pace_mode: str = 'auto-hard', **kwargs):
        super().__init__(**kwargs)
        self.SERVICE = Params.PullPush()
        assert pace_mode in self.PACE_MODES
        self.pace_mode = pace_mode
        self.max_pool = self.SERVICE.MAX_POOL_SOFT if pace_mode == 'auto-soft' else self.SERVICE.MAX_POOL_HARD
        self.pool_amount = self.max_pool

    async def fetch(self, mode: str, get_comments=False, file_name=None, **params):
        @self.catch_taskgroup_err(mode)
        async def _fetch():
            is_single_request = self._validate_and_set_params(params, mode)
            if is_single_request:
                result = await make_request(self, mode, **params)
                result = preprocess_json(self, result)
            else:  # loop through after segmentation
                result = await self._multi_requests(mode, params)

            if mode == 'submissions' and get_comments:
                result = await self._fetch_comments(result, 'comments')

            if file_name:
                save_json(self, file_name, result)

            return result

        return await _fetch()


    def _validate_and_set_params(self, params: dict, mode: str):
        is_single_request = False
        if 'after' in params and 'before' in params:
            assert iso_to_epoch(params['after']) < iso_to_epoch(params['before']), \
                '`before` needs to be bigger than `after`'
        elif 'after' in params and 'before' not in params:
            params['before'] = datetime.now().isoformat()
        elif 'after' not in params and 'before' in params:
            self.task_num = 1
            is_single_request = True
        else:
            self.task_num = 1
            is_single_request = True

        return is_single_request

class ArcticShiftAsync(BaseAsync):
    def __init__(self, pace_mode: str = 'auto-header', **kwargs):
        super().__init__(**kwargs)
        self.SERVICE = Params.ArcticShift()
        assert pace_mode in self.PACE_MODES
        self.pace_mode = pace_mode

        # only for placeholder, pool_amount would be from header response
        self.max_pool = self.SERVICE.MAX_POOL_SOFT if pace_mode == 'auto-soft' else self.SERVICE.MAX_POOL_HARD
        self.pool_amount = self.max_pool

    async def fetch(self, mode: str, get_comments=False, file_name=None, **params):
        @self.catch_taskgroup_err(mode)
        async def _fetch():
            is_single_request = self._validate_and_set_params(params, mode)
            if is_single_request:
                result = await make_request(self, mode, **params)
                result = preprocess_json(self, result)
            else:
                result = await self._multi_requests(mode, params)

            if mode in ['submissions_id_lookup', 'submissions_search'] and get_comments:
                result = await self._fetch_comments(result, 'comments_tree_search')

            if file_name:
                save_json(self, file_name, result)

            return result

        return await _fetch()

    def _validate_and_set_params(self, params: dict, mode: str):
        is_single_request = False
        if mode in ('submissions_search', 'comments_search', 'subreddits_search') or mode.endswith('_interactions'):
            if 'after' in params and 'before' in params:
                assert iso_to_epoch(params['after']) < iso_to_epoch(params['before']), \
                    '`before` needs to be bigger than `after`'
            elif 'after' in params and 'before' not in params:
                params['before'] = datetime.now().isoformat()
            elif 'after' not in params and 'before' in params:
                self.task_num = 1
                is_single_request = True
            else:  # both 'after' and 'before' not in params
                self.logger.warning("no 'after' or 'before' params found")
                self.task_num = 1
                is_single_request = True

        else:
            is_single_request = True

        return is_single_request
