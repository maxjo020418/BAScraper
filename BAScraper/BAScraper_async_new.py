import datetime
import logging
import os
from tempfile import TemporaryDirectory

from BAScraper.utils import *

def iso_to_epoch(iso):
    return datetime.fromisoformat(iso).timestamp()

class BaseAsync:
    def __init__(self,
                 sleep_sec: float = 1,
                 backoff_sec: float = 3,
                 max_retries: int = 5,
                 timeout: float = 10,
                 save_dir=os.getcwd(),
                 task_num=3,
                 log_stream_level: str = 'INFO',
                 log_level: str = 'DEBUG',
                 duplicate_action: str = 'keep_newest'):
        self.sleep_sec = sleep_sec
        self.backoff_sec = backoff_sec
        self.max_retries = max_retries
        self.timeout = timeout
        self.save_dir = save_dir
        self.task_num = task_num

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
        raise NotImplementedError("Subclasses must implement the `fetch` method.")

    def create_temp_dir(self, mode):
        self.temp_dir = TemporaryDirectory(prefix=f'BAScraper-{mode}-temp_', dir=self.save_dir, delete=False)
        self.logger.debug(f'Temp directory created: {self.temp_dir.name}')

    def cleanup_temp_dir(self):
        if self.temp_dir:
            self.temp_dir.cleanup()

class PullPushAsync(BaseAsync):
    def __init__(self, pace_mode: str = 'auto-hard', **kwargs):
        super().__init__(**kwargs)
        self.SERVICE = Params.PullPush()
        assert pace_mode in ['auto-soft', 'auto-hard', 'manual']
        self.pace_mode = pace_mode
        self.max_pool = Params.PullPush.MAX_POOL_SOFT if pace_mode == 'auto-soft' else Params.PullPush.MAX_POOL_HARD
        self.pool_amount = self.max_pool

    async def fetch(self, mode: str, get_comments=False, file_name=None, **params):
        is_single_request = self._validate_and_set_params(mode, params)
        self.create_temp_dir(mode)
        exception_occurred = False
        try:
            if is_single_request:
                result = await make_request(self, mode, **params)
                result = preprocess_json(self, result)
            else:
                result = await self._process_segments(mode, params)

            if mode == 'submissions' and get_comments:
                result = await self._fetch_comments(result)

            if file_name:
                save_json(self, file_name, result)

            return result
        except Exception as err:
            self.logger.error(f"Error during fetch: {err}")
            exception_occurred = True
        finally:
            if not exception_occurred:
                self.cleanup_temp_dir()

    def _validate_and_set_params(self, mode, params):
        is_single_request = False
        if 'after' in params and 'before' in params:
            assert iso_to_epoch(params['after']) < iso_to_epoch(params['before']), '`before` needs to be bigger than `after`'
        elif 'after' in params and 'before' not in params:
            params['before'] = datetime.now().isoformat()
        elif 'after' not in params and 'before' in params:
            self.task_num = 1
            is_single_request = True
        else:
            self.task_num = 1
            is_single_request = True

        return is_single_request

    async def _process_segments(self, mode, params):
        segment_ranges = split_range(params['after'], params['before'], self.task_num)
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(make_request_loop(self, mode, after=start, before=end)) for start, end in segment_ranges]
        return preprocess_json(self, [res for task in tasks for res in task.result()])

    async def _fetch_comments(self, result):
        submission_ids = asyncio.Queue()
        for submission_id in result.keys():
            await submission_ids.put(submission_id)
        comments = await self._get_link_ids_comments(submission_ids)
        for submission in result.values():
            submission.update({'comments': []})
        for comment in comments.values():
            result[comment['link_id'][3:]]['comments'].append(comment)
        return result

    async def _get_link_ids_comments(self, link_ids: asyncio.Queue):
        res = []
        while not link_ids.empty():
            link_id = await link_ids.get()
            res.append(await make_request(self, 'comments', link_id=link_id))
        return preprocess_json(self, [comment for comments in res for comment in comments])

class ArcticShiftAsync(BaseAsync):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.SERVICE = Params.ArcticShift()

    async def fetch(self, mode: str, **params):
        is_single_request = self._validate_and_set_params(mode, params)
        self.create_temp_dir(mode)
        exception_occurred = False
        try:
            if is_single_request:
                result = await make_request(self, mode, **params)
                result = preprocess_json(self, result)
            else:
                result = await self._process_segments(mode, params)
            return result
        except Exception as err:
            self.logger.error(f"Error during fetch: {err}")
            exception_occurred = True
        finally:
            if not exception_occurred:
                self.cleanup_temp_dir()

    def _validate_and_set_params(self, mode, params):
        is_single_request = False
        if mode in ('submissions_search', 'comments_search', 'subreddits_search') or mode.endswith('_interactions'):
            if 'after' in params and 'before' in params:
                assert iso_to_epoch(params['after']) < iso_to_epoch(params['before']), '`before` needs to be bigger than `after`'
            elif 'after' in params and 'before' not in params:
                params['before'] = datetime.now().isoformat()
            elif 'after' not in params and 'before' in params:
                self.task_num = 1
                is_single_request = True
            else:
                self.task_num = 1
                is_single_request = True

        return is_single_request

    async def _process_segments(self, mode, params):
        segment_ranges = split_range(params['after'], params['before'], self.task_num)
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(make_request_loop(self, mode, after=start, before=end)) for start, end in segment_ranges]
        return preprocess_json(self, [res for task in tasks for res in task.result()])
