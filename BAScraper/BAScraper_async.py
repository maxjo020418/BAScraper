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

        ### some extra explanations here:

        for `pace_mode`, HARD and SOFT means it'll shoot requests until reaching that limit and
        sleep until the pool is filled back up (controlled by REFILL_SECOND)

        for `duplicate_action`, it'll decide what to do with duplicate comments/submissions.
            for keep_original, it'll find the version before it was removed. (restore if possible)
            for keep_removed, it'll find the deleted version. (get the deleted/removed version)
            for removed, it'll just exclude it from the results. (remove altogether)
        """
        self.last_refilled = time.time()

        assert pace_mode in ['auto-soft', 'auto-hard', 'manual']
        self.pace_mode = pace_mode
        if pace_mode == 'auto-soft':
            self.max_pool = Params.PullPush.MAX_POOL_SOFT
        elif pace_mode == 'auto-hard':
            self.max_pool = Params.PullPush.MAX_POOL_HARD
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
                    f"{err}\nRetrying... Attempt {retries}/{self.max_retries}")
                self._request_sleep(self.backoff_sec * retries)  # backoff

            except json.decoder.JSONDecodeError:
                retries += 1
                self.logger.warning(
                    f"JSONDecodeError: Retrying... Attempt {retries}/{self.max_retries}")
                self._request_sleep(self.backoff_sec * retries)  # backoff

            except Exception as err:
                raise Exception(f'unexpected error: \n{err}')

        self.logger.error(f'failed request attempt. skipping...')
        return list()

    def _request_sleep(self, sleep_sec=None):
        # in case of manual override
        sleep_sec = self.sleep_sec if sleep_sec is None else sleep_sec

        if time.time() - self.last_refilled > self.REFILL_SECOND:
            self.pool_amount = self.MAX_POOL_SOFT
            self.last_refilled = time.time()
            self.logger.info(f'pool refilled!')

        match self.pace_mode:
            case 'auto-hard' | 'auto-soft':
                if time.time() - self.last_refilled > self.REFILL_SECOND:

                    match self.pace_mode:
                        case 'auto-hard':
                            self.pool_amount = self.MAX_POOL_HARD

                        case 'auto-soft':
                            self.pool_amount = self.MAX_POOL_SOFT

                    self.last_refilled = time.time()
                    self.logger.info(f'pool refilled!')

                if self.pool_amount > 0:
                    time.sleep(sleep_sec)
                    self.pool_amount -= 1
                    return
                else:
                    s = self.REFILL_SECOND - (time.time() - self.last_refilled)
                    self.logger.info(f'hard limit reached! throttling for {s}...')
                    self.logger.info(f'sleeping for {s}sec')
                    time.sleep(s)
                    self._request_sleep()

            case 'manual':
                time.sleep(sleep_sec)
                return

            case _:
                raise Exception(f' Wrong variable for `mode`!')

