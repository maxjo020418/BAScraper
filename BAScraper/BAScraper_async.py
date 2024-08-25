import os
import logging
import datetime
from tempfile import TemporaryDirectory
from collections import defaultdict

from BAScraper.utils import *


# TODO: for docs =>
#  1. recommend to make multiple kinds of requests under the same PullPushAsync class.
#  (needs to share some values like timeout stuffs)
#  also need to mention that restarting the script would reset the used up pool values,
#  so users need to keep that in mind
#  2. At any moment an empty result is returned, the coro will stop making requests.
#  This is an unintended behavior(in the while loop) and might cause problems if filters are used
#  since it might return empty results in certain segments and would end the search early.
#  need to work/workaround on a fix regarding that.


class PullPushAsync:
    def __init__(self,
                 sleep_sec: float = 1,
                 backoff_sec: float = 3,
                 max_retries: int = 5,
                 timeout: float = 10,
                 pace_mode: str = 'auto-hard',
                 save_dir=os.getcwd(),
                 task_num=3,
                 log_stream_level: str = 'INFO',
                 log_level: str = 'DEBUG',
                 duplicate_action: str = 'keep_newest',
                 ) -> None:
        """
        :param sleep_sec: cooldown per request
        :param backoff_sec: backoff amount after error happens in request
        :param max_retries: maximum retry times before failing
        :param timeout: time until it's considered as timout err
        :param pace_mode: methods of pacing to mitigate the ratelimit(pool), auto-hard by default
        :param save_dir: directory to save the results, defaults to current directory
        :param task_num: number of async tasks to be made
        :param log_stream_level: sets the log level for logs streamed on the terminal
        :param log_level: sets the log level for logging (file)
        :param duplicate_action: decides what to do with duplicate entries (usually caused by deletion)

        ### some extra explanations:

        for `pace_mode`, HARD and SOFT means it'll shoot requests until reaching that limit and
        sleep until the pool is filled back up (controlled by REFILL_SECOND)

        for `duplicate_action`, it'll decide what to do with duplicate comments/submissions.
        for keep_original, it'll find the version before it was removed. (restore if possible)
        for keep_removed, it'll find the deleted version. (get the deleted/removed version)
        for removed, it'll just exclude it from the results. (remove altogether)
        """

        # declaring service type, for all pre-configured variables, params and stuffs
        self.SERVICE = Params.PullPush

        assert pace_mode in ['auto-soft', 'auto-hard', 'manual']
        self.pace_mode = pace_mode
        if pace_mode == 'auto-soft':
            self.max_pool = Params.PullPush.MAX_POOL_SOFT
        elif pace_mode == 'auto-hard':
            self.max_pool = Params.PullPush.MAX_POOL_HARD
        self.pool_amount = self.max_pool

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

        # logger stuffs
        log_levels = ['NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        assert log_stream_level in log_levels and log_level in log_levels, \
            '`log_level` should be a string representation of logging level such as `INFO`'

        self.logger = logging.getLogger(__name__)
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s: %(message)s',
                            filename=os.path.join(self.workdir, 'request_log.log'),
                            filemode='w',
                            level=log_level)

        # log stream stuffs for terminal
        # Add a new handler only if no handlers are present
        # prevents multiple instances from forming when PullPushAsync instance is made more than once
        if not self.logger.handlers:
            # create console logging handler and set level
            ch = logging.StreamHandler()
            ch.setLevel(log_stream_level)
            ch.setFormatter(logging.Formatter('%(asctime)s: %(levelname)s - %(message)s'))
            self.logger.addHandler(ch)

        # Prevent logging from propagating to the root logger
        # uncomment below to prevent logging stuff from the subprocesses (async functions)
        # self.logger.propagate = False

        # start timer for API pool refill
        self.last_refilled = time.time()

        # temp dir for storing received results
        self.temp_dir: Union[TemporaryDirectory, None] = None

    async def get_submissions(self, file_name=None, get_comments=False, **params) -> Union[None, dict]:
        """
        :param file_name: file name to use for the saves json result. If `None`, doesn't save the file.
        :param get_comments: if `True`, will also fetch comments belonging to the submission
        :param params:

        if `after` and `before` both exists, it'll get all the stuff in-between
        if only `after` exists, it'll get the `after` ~> current-time
        if only `before` exists, it'll only make a single request (100 entries, newest starting from `before`)
        if neither `after` nor `before` exists, it'll only make a single request (100 entries, newest)
        """
        single_request = False

        # basic parameter check
        if 'after' in params and 'before' in params:
            assert params['after'] < params['before'], '`before` needs to be bigger than `after`'
        elif 'after' in params and 'before' not in params:
            assert params['after'] < int(time.time()), '`after` needs to be smaller than current time'
            params['before'] = int(time.time())
            self.logger.info(f'only `after` was detected for time parameters, '
                             f'making requests until current time starting from '
                             f'{datetime.fromtimestamp(params['after'])}')
        elif 'after' not in params and 'before' in params:
            self.task_num = 1
            self.logger.info('only `before` was detected for time parameters, making single request')
            single_request = True
        else:  # both not in params
            self.task_num = 1
            self.logger.info('no time parameter was detected, making single request')
            single_request = True

        # temp dir for storing received results
        self.temp_dir = TemporaryDirectory(prefix='BAScraper-submission-temp_', dir=self.workdir, delete=False)
        self.logger.debug(f'Temp directory created: {self.temp_dir.name}')
        exception_occurred = False
        try:
            if single_request:
                self.logger.debug('Running request in single-coro-mode')
                result = await make_request(self, 'submissions', **params)
                result = preprocess_json(self, result)
            else:  # regular ranged request
                # segment time is from oldest -> newest
                segment_ranges = split_range(params['after'], params['before'], self.task_num)
                async with asyncio.TaskGroup() as tg:
                    tasks = list()
                    seg_num = 1
                    for segment in segment_ranges:
                        params['after'], params['before'] = segment
                        tasks.append(tg.create_task(make_request_loop(self, 'submissions', **params),
                                                    name=f'coro-{seg_num}'))
                        seg_num += 1
                result = preprocess_json(self, [res for task in tasks for res in task.result()])

        except* (asyncio.exceptions.CancelledError, asyncio.CancelledError) as err:
            self.logger.error(f'Task has been cancelled! : {err.exceptions}')
            exception_occurred = True

        except* (KeyboardInterrupt, SystemExit) as err:
            self.logger.error(f'terminated by user or system! : {err.exceptions}')
            exception_occurred = True

        except* Exception as err:
            raise err

        else:
            if get_comments:
                self.logger.info('Starting comment fetching...')
                submission_ids = asyncio.Queue()
                for submission_id in result.keys():
                    await submission_ids.put(submission_id)
                comments = await self._get_link_ids_comments(submission_ids)

                # TODO: I should add the field while creating the dict rather than looping through it later.
                #  too lazy to implement it now though
                for submission in result.values():
                    submission.update({'comments': list()})

                for comment in comments.values():
                    # needs comment['link_id'][3:] due to 't3_' prefix for the ID
                    result[comment['link_id'][3:]]['comments'].append(comment)

            if file_name:
                save_json(self, file_name, result)
            return result

        finally:
            if exception_occurred:
                self.logger.warning('Some errors occurred while fetching, '
                                    f'preserving temp_dir as {self.temp_dir.name}')
                # might add some extra actions here
                return  # don't close/cleanup the `self.temp_dir`
            else:
                self.temp_dir.cleanup()

    async def get_comments(self, file_name=None, **params) -> Union[None, dict]:
        """
        :param file_name: file name to use for the saves json result. If `None`, doesn't sava the file.
        :param params:
        :return:
        """
        single_request = False

        # basic parameter check
        if 'after' in params and 'before' in params:
            assert params['after'] < params['before'], '`before` needs to be bigger than `after`'
        elif 'after' in params and 'before' not in params:
            assert params['after'] < int(time.time()), '`after` needs to be smaller than current time'
            params['before'] = int(time.time())
            self.logger.info(f'only `after` was detected for time parameters, '
                             f'making requests until current time starting from '
                             f'{datetime.fromtimestamp(params['after'])}')
        elif 'after' not in params and 'before' in params:
            self.task_num = 1
            self.logger.info('only `before` was detected for time parameters, making single request')
            single_request = True
        elif 'link_id' in params:  # comment group fetch from submission (done in single request)
            self.logger.debug('making `link_id` single request')
            single_request = True
        else:  # both not in params
            self.task_num = 1
            self.logger.info('no time parameter was detected, making single request')
            single_request = True

        # temp dir for storing received results
        self.temp_dir = TemporaryDirectory(prefix='BAScraper-comment-temp_', dir=self.workdir, delete=False)
        self.logger.debug(f'Temp directory created: {self.temp_dir.name}')
        exception_occurred = False
        try:
            if single_request:
                self.logger.debug('Running request in single-coro-mode')
                result = await make_request(self, 'comments', **params)
                result = preprocess_json(self, result)
            else:  # regular ranged request
                # segment time is from oldest -> newest
                segment_ranges = split_range(params['after'], params['before'], self.task_num)
                async with asyncio.TaskGroup() as tg:
                    tasks = list()
                    seg_num = 1
                    for segment in segment_ranges:
                        params['after'], params['before'] = segment
                        tasks.append(tg.create_task(make_request_loop(self, 'comments', **params),
                                                    name=f'coro-{seg_num}'))
                        seg_num += 1
                result = preprocess_json(self, [res for task in tasks for res in task.result()])

        except* (asyncio.exceptions.CancelledError, asyncio.CancelledError) as err:
            self.logger.error(f'Task has been cancelled! : {err.exceptions}')
            exception_occurred = True

        except* (KeyboardInterrupt, SystemExit) as err:
            self.logger.error(f'terminated by user or system! : {err.exceptions}')
            exception_occurred = True

        except* Exception as err:
            raise err

        else:
            if file_name:
                save_json(self, file_name, result)
            return result

        finally:
            if exception_occurred:
                self.logger.warning('Some errors occurred while fetching, '
                                    f'preserving temp_dir as {self.temp_dir.name}')
                # might add some extra actions here
                return  # don't close/cleanup the `self.temp_dir`
            else:
                self.temp_dir.cleanup()

    async def _get_link_ids_comments(self, link_ids: asyncio.Queue) -> Union[dict, None]:
        """
        :param link_ids: `Queue` containing `link_id`. Needs to be an `asyncio.Queue`
        :return: dict of comments, indexed based on `link_id`

        stripped down version of `get_comments` used for `get_submissions`'s `link_id` fetch functionality

        TODO: make it more seamlessly integrated. also, the `self.temp_dir` should be re-worked to incorporate
         temp saving of the `_get_link_ids_comments` results. when this function uses the `self.temp_dir` to handle
         temp directories, it overwrites the existing `self.temp_dir` used previously in `get_submissions`,
         causing problems (not cleaning up the temp_dir)
        """

        # temp dir for storing received results
        # self.temp_dir = TemporaryDirectory(prefix='BAScraper-link-id-comment-temp_', dir=self.workdir, delete=False)
        # self.logger.debug(f'Temp directory created: {self.temp_dir.name}')
        exception_occurred = False

        # temp function for custom request loop
        async def link_id_worker(queue: asyncio.Queue) -> List[dict]:
            res = list()
            while not queue.empty():
                link_id = await queue.get()
                queue.task_done()  # Mark the task as done (needed for asyncio.Queue consumers)
                res.append(await make_request(self, 'comments', link_id=link_id))
                self.logger.info(f'{queue.qsize()} items left')
            return [comment for comments in res for comment in comments]

        try:
            async with asyncio.TaskGroup() as tg:
                tasks = list()
                for task_no in range(self.task_num):
                    tasks.append(tg.create_task(link_id_worker(link_ids), name=f'coro-{task_no}'))
            result = preprocess_json(self, [res for task in tasks for res in task.result()])

        except* (asyncio.exceptions.CancelledError, asyncio.CancelledError) as err:
            self.logger.error(f'Task has been cancelled! : {err.exceptions}')
            exception_occurred = True

        except* (KeyboardInterrupt, SystemExit) as err:
            self.logger.error(f'terminated by user or system! : {err.exceptions}')
            exception_occurred = True

        except* Exception as err:
            raise err

        else:
            return result

        finally:
            if exception_occurred:
                self.logger.warning('Some errors occurred while fetching, '
                                    f'preserving temp_dir as {self.temp_dir.name}')
                # might add some extra actions here
                return  # don't close/cleanup the `self.temp_dir`
            else:
                pass
                # self.temp_dir.cleanup()
