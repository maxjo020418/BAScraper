import requests
import time
import logging
import json

from dataclasses import dataclass
from typing import List
from datetime import datetime, timedelta

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
                 Gcreds: List[CSEcred] = None,
                 sleepsec=1,
                 backoffsec=3,
                 max_retries=5,
                 timeout=10,
                 threads=10,
                 comment_t=None,
                 batch_size=0):

        '''
        might add these params from pmaw
        mem_safe (boolean, optional): If True, stores responses in cache during operation, defaults to False
        safe_exit (boolean, optional): If True, will safely exit if interrupted by storing current responses
        and requests in the cache. Will also load previous requests / responses if found in cache, defaults to False
        '''

        self.sleepsec = sleepsec  # cooldown per request
        self.backoffsec = backoffsec  # backoff amount after error happens in request
        self.threads = threads  # no. of threads if multithreading is used
        self.max_retries = max_retries  # maximum retry times
        self.timeout = timeout  # time until it's considered as timout err
        self.comment_t = comment_t if comment_t else threads  # no. of threads used for comment fetching, defaults to 'threads'
        self.batch_size = batch_size  # not implemented yet, for RAM offload to disk

        # locks are no longer used for now
        # self.print_lock = RLock()
        # self.data_lock = Lock()

        # google custom search engine creds
        if Gcreds:
            print('CSEcred detected.')
            self.cse_id = Gcreds.CSE_ID
            self.cse_api = Gcreds.CSE_API_KEY
        else:
            print("no CSEcred detected. you'll need it to use the Google Custom Search Engine")

        self.logger = logging.getLogger('BAlogger')
        self.logger.setLevel(logging.DEBUG)

        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s:%(message)s',
                            filename='scrape_log.log',
                            filemode='w',
                            level=logging.DEBUG)

        # create console handler and set level to debug
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

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
                        score: int = None,
                        num_comments: int = None,
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
        rate_limit (int, optional): Target number of requests per minute for rate-averaging, defaults to 60 requests per minute.
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
             (f"sort_type: '{sort_type}' does not support timeframe based scraping. defaulting to {limit} posts"))
            timeframe_mode = False
        else:
            timeframe_mode = _ask()
            if timeframe_mode:
                sort = 'desc'

        url = f'https://api.pullpush.io/reddit/search/submission'
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
                    futures.append(executor.submit(self._make_post_request_timeframe,
                                                   url=url, params=thread_params, thread_id=i))
                for future in as_completed(futures):
                    # futures.as_completed will hold the main thread until complete
                    fu_result, thread_id = future.result()
                    response[thread_id] = fu_result

            response = [post for sl in response for post in sl]  # de-nest the response
            response = {d['id']: d for d in response}  # index based on ID to dict

            self.logger.info(f'fetching posts time: {time.time() - s}sec')

        else:
            response = self._make_request(url, params)
            response = {d['id']: d for d in response}  # index based on ID to dict

        # comment fetching
        if get_comments:
            self.logger.info('\nstarting comment fetching...\n')
            comment_ids = Queue()
            [comment_ids.put(post['id']) for _, post in response.items()]  # create a Queue of post_id
            comment_url = 'https://api.pullpush.io/reddit/search/comment/'
            s = time.time()
            with ThreadPoolExecutor() as executor:
                futures = []
                for i in range(self.comment_t):
                    self.logger.debug(f'started thread no.{i}')
                    futures.append(executor.submit(self._make_comment_request_queue, q=comment_ids,
                                                   url=comment_url, params={}, thread_id=i))
                    time.sleep(.5)

                for future in as_completed(futures):
                    # futures.as_completed will hold the main thread until all threads are complete
                    fu_result, thread_id = future.result()
                    self.logger.debug(f't-{thread_id}: writing comments to data')
                    for id, comments in fu_result.items():
                        if id in response:
                            response[id]['comments'] = comments
            self.logger.info(f'fetching comments time: {time.time() - s}sec')

        # filtering - also includes the 'comments' field in case comments were scraped.e
        response = {post_id: {k: v[k] for k in filters + ['comments'] if k in v} for post_id, v in
                    response.items()} if filters else response

        return response

    def _make_request(self, url, params, thread_id=0, headers={}):
        retries = 0
        while retries < self.max_retries:
            try:
                response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
                if len(response.json()['data']):
                    self.logger.info(
                        f"t-{thread_id}: {response.status_code} {'OK' if response.ok else 'ERR'} - {response.elapsed}")
                time.sleep(self.sleepsec)

                return response.json()['data']

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as err:
                retries += 1
                self.logger.warning(
                    f"t-{thread_id}: {err}\n{'=' * 25}\nRetrying... Attempt {retries}/{self.max_retries}")
                time.sleep(self.backoffsec * retries)  # backoff

            except json.decoder.JSONDecodeError:
                retries += 1
                self.logger.warning(
                    f"t-{thread_id}: JSONDecodeError: Retrying... Attempt {retries}/{self.max_retries}")

            except Exception as err:
                raise Exception(f't-{thread_id}: unexpected error: {err}')

        self.logger.error(f't-{thread_id}: failed request attempt. skipping...')

    ######################################
    # worker functions for multithreading #
    ######################################

    def _make_comment_request_queue(self, q: Queue, url, params, thread_id, headers={}) -> (dict, int):
        # _make_request looper that uses Queue multithreaded
        # returns an indexed dict! {link_id : [data]}
        results = dict()
        while not q.empty():
            self.logger.debug(f't-{thread_id}: q.get()')
            link_id = q.get()
            params['link_id'] = link_id
            self.logger.debug(f't-{thread_id}: making request')
            results[link_id] = self._make_request(url, params, thread_id)
            self.logger.info(f't-{thread_id}: {q.qsize()} comments left')
        return results, thread_id

    def _make_post_request_timeframe(self, url, params, thread_id, headers={}) -> (list, int):
        # _make_request looper (within the timeframe specified) multithread-ok
        results = list()

        while True:
            self.logger.debug(f't-{thread_id}: making request')
            res = self._make_request(url, params, thread_id, headers)
            if not len(res):
                self.logger.info(f't-{thread_id}: finished.')
                return results, thread_id  # when result is empty, finish scraping

            results += res
            try:
                self.logger.debug(f't-{thread_id}: getting new pivot')
                params['before'] = round(float(results[-1]['created_utc']))

            except KeyError as err:
                with open("errfile.json", "w", encoding='utf-8') as f:
                    json.dump(res, f, indent=4)

                raise Exception(f't-{thread_id}: date format problem from submission. (dumped file):\n{err}')


if __name__ == '__main__':
    # example code
    pp = Pushpull(sleepsec=3, threads=4)

    result = pp.get_submissions(after=datetime(2023, 12, 30), before=datetime(2024, 1, 1),
                                subreddit='bluearchive', get_comments=True)

    with open("example.json", "w", encoding='utf-8') as outfile:
        json.dump(result, outfile, indent=4)
