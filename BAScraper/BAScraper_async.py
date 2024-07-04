import requests
from collections import defaultdict
import time
import os
import logging
from typing import Union
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

        # declaring service type, for all pre-configured variables and params
        self.SERVICE = Params.PullPush

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

        # start timer for API pool refill
        self.last_refilled = time.time()

    def get_submissions(self, **params):
        pass

    def get_comments(self, **params):
        pass
