import os
import logging
import datetime
from tempfile import TemporaryDirectory

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
                 workdir=os.getcwd(),
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
        :param workdir: path where this will store stuffs needed, defaults to `workdir`
        :param save_dir: directory to save the results
        :param task_num: number of async tasks to be made per-segment
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
        self.workdir = workdir
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

    async def get_submissions(self, file_name=None, **params) -> Union[None, dict]:
        """
        :param file_name: file name to use for the saves json result. If `None`, doesn't sava the file.
        :param params:

        if `after` and `before` both exists, it'll get all the stuff in-between
        if only `after` exists, it'll get the `after` ~> current-time
        if only `before` exists, it'll only make a single request (100 entries, newest starting from `before`)
        if neither `after` nor `before` exists, it'll only make a single request (100 entries, newest)
        """
        single_request = False

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
        self.temp_dir = TemporaryDirectory(prefix='BAScraper-temp_', dir=self.workdir, delete=False)
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
            if file_name:
                self.logger.info('saving result...')
                with open(os.path.join(self.save_dir, file_name + '.json'), 'w+') as f:
                    json.dump(result, f, indent=4)

            return result

        finally:
            # TODO: some more robust file saving - check is file exist, file extensions... etc
            if exception_occurred:
                self.logger.warning('Some errors occurred while fetching, '
                                    f'preserving temp_dir as {self.temp_dir.name}')
                # might add some extra actions here
                return  # don't close/cleanup the `self.temp_dir`
            else:
                self.temp_dir.cleanup()

    async def get_comments(self, **params) -> Union[None, dict]:
        # TODO: add comment fetching
        pass
