import requests
import time
import logging
import json

from dataclasses import dataclass
from typing import List
from datetime import datetime

from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue

# imports no longer used
# from threading import Lock, RLock
# from dotenv import load_dotenv
# import os


# for Google custom search engine key - not implemented yet
# might add support for multiple accounts if needed
@dataclass
class CSEcred:
    CSE_ID: str
    CSE_API_KEY: str


class Pushpull:
    def __init__(self,
                 gcreds: List[CSEcred] = None,
                 sleepsec=1,
                 backoffsec=3,
                 max_retries=5,
                 timeout=10,
                 threads=10,
                 comment_t=None,
                 batch_size=0):

        """
        might add these params from pmaw
        mem_safe (boolean, optional): If True, stores responses in cache during operation, defaults to False
        safe_exit (boolean, optional): If True, will safely exit if interrupted by storing current responses
        and requests in the cache. Will also load previous requests / responses if found in cache, defaults to False
        """

        self.sleepsec = sleepsec  # cooldown per request
        self.backoffsec = backoffsec  # backoff amount after error happens in request
        self.threads = threads  # no. of threads if multithreading is used
        self.max_retries = max_retries  # maximum retry times
        self.timeout = timeout  # time until it's considered as timout err
        self.comment_t = comment_t if comment_t else threads  # no. of threads used for comment fetching, defaults to 'threads'
        self.batch_size = batch_size  # not implemented yet, for RAM offload to disk

        self.submission_url = 'https://api.pullpush.io/reddit/search/submission/'
        self.comment_url = 'https://api.pullpush.io/reddit/search/comment/'

        # locks are no longer used for now
        # self.print_lock = RLock()
        # self.data_lock = Lock()

        # google custom search engine creds
        if gcreds:
            print('CSEcred detected.')
            self.cse_id = gcreds.CSE_ID
            self.cse_api = gcreds.CSE_API_KEY
        else:
            print("no CSEcred detected. you'll need it to use the Google Custom Search Engine")

        self.logger = logging.getLogger('BAlogger')
        self.logger.setLevel(logging.DEBUG)

        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s:%(message)s',
                            filename='scrape_log.log',
                            filemode='w',
                            level=logging.DEBUG)

        # create console handler and set level
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)  # CHANGE HERE TO CONTROL DISPLAYED LOG MESSAGE LEVEL

        formatter = logging.Formatter('%(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def get_submissions(self,
                        after: datetime,
                        before: datetime,
                        get_comments: bool = False,
                        filters: List[str] = None,
                        sort: str = 'desc',
                        sort_type: str = 'created_utc',
                        limit: int = 100,
                        ids: List[str] = None,
                        q: str = None,
                        title: str = None,
                        selftext: str = None,
                        author: str = None,
                        subreddit: str = None,
                        score=None,
                        num_comments=None,
                        over_18: bool = None,
                        is_video: bool = None,
                        locked: bool = None,
                        stickied: bool = None,
                        spoiler: bool = None,
                        contest_mode: bool = None):

        """
        this will only scrape based on date, so 'after' and 'before' is mandatory
        also, 'limit' is the number of posts per request, not the total no.

        if ('after' OR 'before' is None) OR ('sort_type' is NOT 'created_utc')
        it will only scrape up to 'limit' amount of posts.

        might add these params from pmaw
        max_sleep (int, optional): Maximum rate-limit sleep time (in seconds) between requests, defaults to 60s.
        rate_limit (int, optional): Target number of requests per minute for rate-averaging,
                                    defaults to 60 requests per minute.
        """

        # check params
        assert sort in ['desc', 'asc'], "'sort' should be one of ['desc', 'asc']"
        assert sort_type in ['created_utc', 'score',
                             'num_comments'], \
            "'sort_type' should be one of ['created_utc', 'score', 'num_comments', 'created_utc']"
        assert limit <= 100, "'limit' should be <= 100"
        assert after <= before, "'after' cannot be bigger than 'before'!"

        def _ask():
            inp = input('Would you like to enable timeframe based scraping? (Y/n) ').lower()
            if inp in ['y', '']:
                self.logger.info("timeframe based scraping is enabled. 'sort' is fixed to 'desc'")
                return True
            elif inp == 'n':
                return False
            else:
                _ask()

        if sort_type != 'created_utc':
            (self.logger.warning
             (f"sort_type: '{sort_type}' does not support timeframe based scraping. "
              f"cannot fetch more than {limit} posts"))
            timeframe_mode = False
        else:
            timeframe_mode = _ask()
            if timeframe_mode:
                # in timeframe_mode sort needs to be fixed to descending
                # due to how _make_timeframe_submission_request works
                sort = 'desc'

        params = {
            'sort': sort,
            'sort_type': sort_type,
            'size': limit,
            'ids': ','.join(ids) if ids else None,
            'q': q,
            'title': title,
            'selftext': selftext,
            'author': author,
            'subreddit': subreddit,
            'after': round(after.timestamp()) if after else None,
            'before': round(before.timestamp()) if before else None,
            'score': score,
            'num_comments': num_comments,
            'over_18': over_18,
            'is_video': is_video,
            'locked': locked,
            'stickied': stickied,
            'spoiler': spoiler,
            'contest_mode': contest_mode,
        }

        if timeframe_mode:
            # splitting up the timeframe for multithreading
            interval = (before - after) / self.threads
            splitpoints = [interval * i + after for i in range(self.threads + 1)]
            response = [None for _ in range(self.threads)]
            s = time.time()

            with ThreadPoolExecutor() as executor:
                futures = []
                for i in range(self.threads):
                    thread_params = dict(params)  # make a shallow copy for thread safety
                    thread_params['after'] = round(splitpoints[i].timestamp())
                    thread_params['before'] = round(splitpoints[i + 1].timestamp())
                    self.logger.info(f"started thread no.{i} | {datetime.fromtimestamp(thread_params['before'])} <- "
                                     f"{datetime.fromtimestamp(thread_params['after'])}")
                    time.sleep(1)
                    futures.append(executor.submit(self._make_timeframe_submission_request,
                                                   params=thread_params, thread_id=i))
                for future in as_completed(futures):
                    # futures.as_completed will hold the main thread until complete
                    fu_result, thread_id = future.result()
                    response[thread_id] = fu_result

            response = [post for batch in response for post in batch]  # de-nest the response
            response = {d['id']: d for d in response}  # index based on ID to dict

            self.logger.info(f'submission fetching time: {time.time() - s}sec')

        else:
            response = self._make_request('submission', params)
            response = {d['id']: d for d in response}  # index based on ID to dict

        # comment fetching
        if get_comments:
            self.logger.info('starting comment fetching...')
            comment_ids = Queue()
            [comment_ids.put(post['id']) for _, post in response.items()]  # create a Queue of post_id
            s = time.time()
            with ThreadPoolExecutor() as executor:
                futures = []
                for i in range(self.comment_t):
                    self.logger.debug(f'started thread no.{i}')
                    futures.append(executor.submit(self._make_queued_comment_request, q=comment_ids,
                                                   params={}, thread_id=i))
                    time.sleep(.5)

                for future in as_completed(futures):
                    # futures.as_completed will hold the main thread until all threads are complete
                    fu_result, thread_id = future.result()
                    self.logger.debug(f't-{thread_id}: writing comments to data')
                    for post_id, comments in fu_result.items():
                        if post_id in response:
                            response[post_id]['comments'] = comments
            self.logger.info(f'comment fetching time: {time.time() - s}sec')

        # filtering - also includes the 'comments' field in case comments were scraped.e
        response = {post_id: {k: v[k] for k in filters + ['comments'] if k in v} for post_id, v in
                    response.items()} if filters else response

        return response

    def _make_request(self, mode, params, thread_id=0, headers=None) -> list:

        assert mode in ['submission', 'comment'], "`mode` should be one of ['submission', 'comment']"
        url = self.submission_url if mode == 'submission' else self.comment_url

        headers = dict() if not headers else headers

        retries = 0
        while retries < self.max_retries:
            try:
                response = requests.get(url, params=params, headers=headers, timeout=self.timeout)

                if response.ok:
                    self.logger.info(
                        f"t-{thread_id}: {response.status_code} - {response.elapsed}")
                else:
                    self.logger.warning(f"t-{thread_id}: {response.status_code} - {response.elapsed}"
                                        f"\n{response.text}\n")

                time.sleep(self.sleepsec)
                return response.json()['data']

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as err:
                retries += 1
                self.logger.warning(
                    f"t-{thread_id}: {err}\n{'='*25}\nRetrying... Attempt {retries}/{self.max_retries}")
                time.sleep(self.backoffsec * retries)  # backoff

            except json.decoder.JSONDecodeError:
                retries += 1
                self.logger.warning(
                    f"t-{thread_id}: JSONDecodeError: Retrying... Attempt {retries}/{self.max_retries}")

            except Exception as err:
                raise Exception(f't-{thread_id}: unexpected error: {err}')

        self.logger.error(f't-{thread_id}: failed request attempt. skipping...')
        return list()

    ######################################
    # worker functions for multithreading #
    ######################################

    def _make_queued_comment_request(self, q: Queue, params, thread_id, headers=None) -> (dict, int):
        """
        :param q: Queue obj containing post's link_ids
        :param params:
        :param thread_id: for debug and thread tracking purposes
        :param headers:
        :return:

        `_make_request` looper - requires a Queue object containing post's `link_id`s
        will loop through until all the `link_id` inside the `Queue` is empty
        used for getting all the comments in a list(`Queue`) of post `link_id`

        returns an indexed `dict` - `{link_id : [data], ...}` corresponding to that post's `link_id`
        """

        headers = dict() if not headers else headers

        results = dict()
        while not q.empty():  # if Queue is empty, end thread

            # retrieve an ID from the queue and set that as the link_id reqeust param
            self.logger.info(f't-{thread_id}: {q.qsize()} comments left')
            link_id = q.get()
            params['link_id'] = link_id

            # make a request using the new param
            self.logger.debug(f't-{thread_id}: making request')
            results[link_id] = self._make_request('comment', params, thread_id, headers)

        return results, thread_id

    def _make_timeframe_submission_request(self, params, thread_id, headers=None) -> (List[list], int):
        """
        :param params:
        :param thread_id: for debug and thread tracking purposes
        :param headers:
        :return:

        `_make_request` looper - given a `param` that has `before` and `after`,
        it'll scrape everything in that time range(timeframe).
        """

        assert (type(params['before']), type(params['after'])) == (int, int), \
            "params for _make_timeframe_submission_request needs to have 'before' and 'after' as epoch"

        headers = dict() if not headers else headers

        results = list()

        while True:
            self.logger.debug(f't-{thread_id}: making request')
            result = self._make_request('submission', params, thread_id, headers)

            if not len(result):  # when result is empty, finish scraping
                self.logger.info(f't-{thread_id}: finished.')
                return results, thread_id

            results += result

            try:
                # set new
                self.logger.debug(f't-{thread_id}: getting new pivot')
                params['before'] = round(float(results[-1]['created_utc']))

            except KeyError as err:
                with open("errfile.json", "w", encoding='utf-8') as f:
                    json.dump(result, f, indent=4)

                raise Exception(f't-{thread_id}: date format problem from submission. (dumped file):\n{err}')


if __name__ == '__main__':
    # example code
    pp = Pushpull(sleepsec=3, threads=4)

    res = pp.get_submissions(after=datetime(2024, 1, 1), before=datetime(2024, 1, 2),
                             subreddit='bluearchive', get_comments=True)

    with open("example.json", "w", encoding='utf-8') as outfile:
        json.dump(res, outfile, indent=4)
