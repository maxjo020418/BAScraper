import requests
from collections import defaultdict
import re
import time
import os
import logging
from typing import List
from datetime import datetime
import json

from .utils import *


class PullPushAsync:
    def __init__(self,
                 sleep_sec: float = 1,
                 backoff_sec: float = 3,
                 max_retries: float = 5,
                 timeout: float = 10,
                 pace_mode: str = 'auto-hard',
                 cwd=os.getcwd(),
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
        :param log_stream_level: sets the log level for logs streamed on the terminal
        :param log_level: sets the log level for logging (file)
        :param duplicate_action: decides what to do with duplicate entries (usually caused by deletion)

        ### some extra explanations here: ###

        for `pace_mode`, HARD and SOFT means it'll shoot requests until reaching that limit and
        sleep until the pool is filled back up (controlled by REFILL_SECOND)

        for `duplicate_action`, it'll decide what to do with duplicate comments/submissions.
            for keep_original, it'll find the version before it was removed. (restore if possible)
            for keep_removed, it'll find the deleted version. (get the deleted/removed version)
            for removed, it'll just exclude it from the results. (remove altogether)
        """

        # constants settings
        # rate limit metrics as of feb 9th 2023
        self.MAX_POOL_SOFT = 15
        self.MAX_POOL_HARD = 30
        self.REFILL_SECOND = 60
        self.SUBMISSION_URI = 'https://api.pullpush.io/reddit/search/submission/'
        self.COMMENT_URI = 'https://api.pullpush.io/reddit/search/comment/'
        self.DIAGNOSTIC_URI = "https://api.pullpush.io/ping"
        self.last_refilled = time.time()

        assert pace_mode in ['auto-soft', 'auto-hard', 'manual']
        self.pace_mode = pace_mode
        if pace_mode == 'auto-soft':
            self.max_pool = self.MAX_POOL_SOFT
        elif pace_mode == 'auto-hard':
            self.max_pool = self.MAX_POOL_HARD
        self.pool_amount = self.max_pool

        assert duplicate_action in ['keep_newest', 'keep_oldest', 'remove', 'keep_original', 'keep_removed'], \
            ("`duplicate_action` should be one of "
             "['keep_newest', 'keep_oldest', 'remove', 'keep_original', 'keep_removed']")

        self.sleep_sec = sleep_sec
        self.backoff_sec = backoff_sec
        self.max_retries = max_retries
        self.timeout = timeout
        self.cwd = cwd

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

        # create console logging handler and set level
        ch = logging.StreamHandler()
        ch.setLevel(log_stream_level)
        ch.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
        self.logger.addHandler(ch)

    def get_submissions(self, **params):
        pass

    def get_comments(self, **params):
        pass

    def _process_params(self, mode, **params) -> str:
        """
        :param mode: mode as in whether it's for comments or submissions
        :param params: all the params needed
        :return: string that contains the structured URI

        check `URI_params.md` for accepted parameters and more details

        TODO: I forgot what the endpoint did when it had no params...
        """
        def assert_op(val: str) -> bool:
            pattern = r"^(<|>)\d+$"
            return True if re.match(pattern, val) else False

        # {parameter : [accepted_type, assertion_func]} key, val pair
        comment_params = {
            'q': [str, None],
            'ids': [list, None],
            'size': [int, lambda x: x <= 100],
            'sort': [str, lambda x: x in ["asc", "desc"]],
            'sort_type': [str, lambda x: x in ["score", "num_comments", "created_utc"]],
            'author': [str, None],
            'subreddit': [str, None],
            'after': [int, None],
            'before': [int, None],
            'link_id': [str, None]
        }

        submission_params = {
            'ids': [list, None],
            'q': [str, None],
            'title': [str, None],
            'selftext': [str, None],
            'size': [int, lambda x: x <= 100],
            'sort': [str, lambda x: x in ["asc", "desc"]],
            'sort_type': [str, lambda x: x in ["score", "num_comments", "created_utc"]],
            'author': [str, None],
            'subreddit': [str, None],
            'after': [int, None],
            'before': [int, None],
            'score': [str, assert_op],
            'num_comments': [str, assert_op],
            'over_18': [bool, None],
            'is_video': [bool, None],
            'locked': [bool, None],
            'stickied': [bool, None],
            'spoiler': [bool, None],
            'contest_mode': [bool, None]
        }

        # setting up the mode (whether it's for comments or submissions)
        if mode == 'comments':
            scheme = comment_params
            uri_string = self.COMMENT_URI
        elif mode == 'submissions':
            scheme = submission_params
            uri_string = self.SUBMISSION_URI
        else:
            raise Exception('wrong `mode` param for `_process_params`')

        # assertion stuffs using the `submission_params` and `comment_params`
        for k, v in params.items():
            if (dat := scheme.get(k)) is not None:
                assert isinstance(v, dat[0]), f'Param "{v}" should be {dat[0]}'
                if dat[1] is not None:
                    assert dat[1](v), f"Param \"{v}\" doesn't meet or satisfy the requirements"
            else:
                raise Exception(f'{v} is not accepted as a parameter')

        # empty `params` don't need the URI parts after, so just return
        if len(params) <= 0:
            return uri_string

        def param2str(param_k, param_v) -> str:
            # for when the param is 'ids' (List[str])
            if param_k == 'ids':
                return ','.join(param_v)
            # if `param` is `bool`, the resulting string would be 'True', 'False' not 'true', 'false' we want
            return str(param_v).lower() if isinstance(param_v, bool) else str(param_v)

        return uri_string + '?' + '&'.join([f'{k}={param2str(k, v)}' for k, v in params.items()])

    def _make_request(self, uri: str) -> defaultdict:
        retries = 0
        while retries < self.max_retries:
            try:
                response = requests.get(uri, timeout=self.timeout)
                result = response.json()['data']

                if response.ok:
                    self.logger.info(
                        f"pool: {self.pool_amount} | len: {len(result)} | time: {response.elapsed}")
                else:
                    self.logger.error(f"{response.status_code} - {response.elapsed}"
                                      f"\n{response.text}\n")

                self._request_sleep()
                return result

            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.HTTPError) as err:
                retries += 1
                self.logger.warning(
                    f"t-{thread_id}: {err}\nRetrying... Attempt {retries}/{self.max_retries}")
                self._request_sleep(thread_id, self.backoffsec * retries)  # backoff

            except json.decoder.JSONDecodeError:
                retries += 1
                self.logger.warning(
                    f"JSONDecodeError: Retrying... Attempt {retries}/{self.max_retries}")
                self._request_sleep(thread_id, self.backoffsec * retries)  # backoff

            except Exception as err:
                raise Exception(f'unexpected error: \n{err}')

        self.logger.error(f'failed request attempt. skipping...')
        return list()

    def _request_sleep(self, sleep_sec=None):
        # in case of manual override
        sleep_sec = self.sleep_sec if sleep_sec is None else sleep_sec

        match self.pace_mode:
            case 'auto-hard':
                if time.time() - self.last_refilled > self.REFILL_SECOND:
                    self.pool_amount = self.MAX_POOL_HARD
                    self.last_refilled = time.time()
                    self.logger.info(f'pool refilled!')

                if self.pool_amount > 0:
                    time.sleep(sleep_sec)
                    self.pool_amount -= 1
                    return
                else:
                    self.logger.info(f't-{thread_no}: hard limit reached! throttling for {s}...')
                    self.logger.info(f'sleeping for {s}sec')
                    time.sleep(s)
                    self.request_sleep()

            case 'auto-soft':
                if time.time() - self.last_refilled > self.REFILL_SECOND:
                    self.pool_amount = self.MAX_POOL_SOFT
                    self.last_refilled = time.time()
                    self.logger.info(f'pool refilled!')

                if self.pool_amount > 0:
                    time.sleep(sleep_sec)
                    self.pool_amount -= 1
                    return
                else:
                    self.logger.info(f't-{thread_no}: soft limit reached! throttling for {s}...')
                    self.logger.info(f'sleeping for {s}sec')
                    time.sleep(s)
                    self.request_sleep()


            case 'manual':
                time.sleep(sleep_sec)
                return

            case _:
                raise Exception(f'{thread_no}: Wrong variable for `mode`!')

