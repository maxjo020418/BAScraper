import os
import logging

from BAScraper.utils import *


class PullPushAsync:
    def __init__(self,
                 sleep_sec: float = 1,
                 backoff_sec: float = 3,
                 max_retries: int = 5,
                 timeout: float = 10,
                 pace_mode: str = 'auto-hard',
                 cwd=os.getcwd(),
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
        :param cwd: path where this will store all the stuffs needed, defaults to cwd
        :param save_dir: directory to save the results
        :param task_num: number of async tasks to be made per-segment
        :param log_stream_level: sets the log level for logs streamed on the terminal
        :param log_level: sets the log level for logging (file)
        :param duplicate_action: decides what to do with duplicate entries (usually caused by deletion)

        ### some extra explanations here:

        for `pace_mode`, HARD and SOFT means it'll shoot requests until reaching that limit and
        sleep until the pool is filled back up (controlled by REFILL_SECOND)

        for `duplicate_action`, it'll decide what to do with duplicate comments/submissions.
        for keep_original, it'll find the version before it was removed. (restore if possible)
        for keep_removed, it'll find the deleted version. (get the deleted/removed version)
        for removed, it'll just exclude it from the results. (remove altogether)
        """

        # declaring service type, for all pre-configured variables and params
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
        self.cwd = cwd
        self.save_dir = save_dir
        self.task_num = task_num

        assert duplicate_action in ['keep_newest', 'keep_oldest', 'remove', 'keep_original', 'keep_removed'], \
            ("`duplicate_action` should be one of "
             "['keep_newest', 'keep_oldest', 'remove', 'keep_original', 'keep_removed']")
        self.duplicate_action = duplicate_action

        # TODO: fix logger(log_stream works) not properly working in async

        # logger stuffs
        log_levels = ['NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        assert log_stream_level in log_levels and log_level in log_levels, \
            '`log_level` should be a string representation of logging level such as `INFO`'

        self.logger = logging.getLogger('BALogger')
        self.logger.setLevel(log_level)
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s:%(message)s',
                            filename=os.path.join(self.cwd, 'scrape_log.log'),
                            filemode='w',
                            level=logging.DEBUG)
        # Add a new handler only if no handlers are present
        if not self.logger.handlers:
            # create console logging handler and set level
            ch = logging.StreamHandler()
            ch.setLevel(log_stream_level)
            ch.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
            self.logger.addHandler(ch)
        self.logger.propagate = False  # Prevent logging from propagating to the root logger

        # start timer for API pool refill
        self.last_refilled = time.time()

    async def get_submissions(self, **params) -> Union[None, dict]:
        """
        :param params:

        will save the results on disk, in the specified dir(`save_dir`).

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
                             f'making requests until current time starting from {params['after']}')
        elif 'after' not in params and 'before' in params:
            self.task_num = 1
            self.logger.info('only `before` was detected for time parameters, making single request')
            single_request = True
        else:  # both not in params
            self.task_num = 1
            self.logger.info('no time parameter was detected, making single request')
            single_request = True

        if single_request:
            self.logger.debug('Running request in single-coro-mode')
            result = await make_request(self, 'submissions', **params)
            # TODO: make and put save-to-disk function here
            return preprocess_json(self, result)

        # segment time is from oldest -> newest
        segment_ranges = split_range(params['after'], params['before'], self.task_num)

        try:
            async with asyncio.TaskGroup() as tg:
                tasks = list()
                seg_num = 1
                for segment in segment_ranges:
                    params['after'], params['before'] = segment
                    tasks.append(tg.create_task(make_request_loop(self, 'submissions', **params),
                                                name=f'coro-{seg_num}'))
                    seg_num += 1

        # TODO: have to handle errors as ExceptionGroup here. not regular ones

        except asyncio.CancelledError as err:
            print(f'asyncio.CancelledError: {err}')

        except (KeyboardInterrupt, SystemExit) as err:
            print('terminated by user or system.')

        except Exception as err:
            raise err

        else:
            results = preprocess_json(self, [res for task in tasks for res in task.result()])
            print(len(results))
            return results

        finally:
            pass
            # TODO: make and put save-to-disk function here
            # since there may have been exceptions, try to safely save

    async def get_comments(self, **params) -> Union[None, dict]:
        pass
