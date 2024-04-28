import requests
import time
import logging
import json
import re

from dataclasses import dataclass
from typing import List
from datetime import datetime

from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue

import os
from threading import Lock, RLock
import pprint
pretty = pprint.PrettyPrinter(indent=4).pprint

# imports no longer used
# from dotenv import load_dotenv


# for Google custom search engine key - not implemented yet
# might add support for multiple accounts if needed
@dataclass
class Creds:
    CSE_ID: str
    CSE_API_KEY: str


class Pushpull:
    def __init__(self,
                 creds: List[Creds] = None,
                 sleepsec=1,
                 backoffsec=3,
                 max_retries=5,
                 timeout=10,
                 threads=2,
                 comment_t=None,
                 batch_size=0,
                 log_level='INFO',
                 cwd=os.getcwd(),
                 pace_mode='auto-hard'):

        """
        might add these params from pmaw
        mem_safe (boolean, optional): If True, stores responses in cache during operation, defaults to False
        safe_exit (boolean, optional): If True, will safely exit if interrupted by storing current responses
        and requests in the cache. Will also load previous requests / responses if found in cache, defaults to False

        ! new ratelimit -> 30 requests per 60 seconds = 3 requests per second ->
        soft limit starting from 15 requests per second (1.5 requests per second)
        hard limit starting from 30 requests per second (3 requests per second)
        hard limit starting from 1k requests per hour (1 request every 4 second)
        """

        # variables for managing rate limits
        # rate limit as of feb 9th 2023
        assert pace_mode in ['auto-soft', 'auto-hard', 'manual']
        self.max_pool_amount_soft = 15
        self.max_pool_amount_hard = 30
        self.refill_second = 60
        self.last_refilled = time.time()
        self.pace_mode = pace_mode  # auto by default
        if pace_mode == 'auto-soft':
            self.max_pool_amount = self.max_pool_amount_soft
        elif pace_mode == 'auto-hard':
            self.max_pool_amount = self.max_pool_amount_hard
        self.pool_amount = self.max_pool_amount
        self.throttling = False  # needed this since the threads can't get out of throttled state
        # (needs shared throttled/not-throttled state)
        self.pool_lock = RLock()
        self.throttle_lock = RLock()

        self.sleepsec = sleepsec  # cooldown per request
        self.backoffsec = backoffsec  # backoff amount after error happens in request
        self.threads = threads  # no. of threads if multithreading is used
        self.max_retries = max_retries  # maximum retry times
        self.timeout = timeout  # time until it's considered as timout err
        self.comment_t = comment_t if comment_t else threads  # no. of threads used for comment fetching, defaults to 'threads'
        self.batch_size = batch_size  # not implemented yet, for RAM offload to disk

        self.submission_url = 'https://api.pullpush.io/reddit/search/submission/'
        self.comment_url = 'https://api.pullpush.io/reddit/search/comment/'

        self.cwd = cwd

        # google custom search engine creds
        try:
            self.cse_id = creds.CSE_ID
            self.cse_api = creds.CSE_API_KEY
            print('CSE credentials detected.')

        except (NameError, AttributeError):
            print("no CSE credentials detected. you'll need it to use the Google Custom Search Engine")

        self.logger = logging.getLogger('BAlogger')
        self.logger.setLevel(logging.DEBUG)

        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s:%(message)s',
                            filename=os.path.join(self.cwd, 'scrape_log.log'),
                            filemode='w',
                            level=logging.DEBUG)

        assert log_level in ['NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], \
            '`log_level` should be a string representation of logging level such as `INFO`'

        # create console handler and set level
        ch = logging.StreamHandler()
        ch.setLevel(log_level)  # CHANGE HERE TO CONTROL DISPLAYED LOG MESSAGE LEVEL
        ch.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
        self.logger.addHandler(ch)

    def request_sleep(self, thread_no=None, sleepsec=None):
        sleepsec = self.sleepsec if sleepsec is None else sleepsec

        match self.pace_mode:
            case 'auto-soft' | 'auto-hard':
                self.pool_lock.acquire()
                if time.time() - self.last_refilled > self.refill_second:
                    self.pool_amount = self.max_pool_amount
                    self.last_refilled = time.time()
                    self.logger.info(f't-{thread_no}: pool refilled!')

                if self.pool_amount > 0:
                    time.sleep(sleepsec)
                    self.pool_amount -= 1
                    self.pool_lock.release()
                    return

                else:
                    self.pool_lock.release()
                    with self.throttle_lock:
                        self.throttling = True
                        s = self.refill_second - (time.time() - self.last_refilled)
                        self.logger.info(f't-{thread_no}: soft/hard limit reached! throttling for {s}...')
                        self.logger.info(f'sleeping for {s}sec')
                        time.sleep(s)
                        '''
                        while True:
                            if (time.time() - self.last_refilled > self.refill_second) or not self.throttling:
                                self.throttling = False
                                break
                            time.sleep(1)
                        '''
                    self.request_sleep(thread_no)

            case 'manual':
                time.sleep(sleepsec)
                return

            case _:
                raise Exception(f'{thread_no}: Wrong variable for `mode`!')

    # TODO: make it so that when `ids` field is used,
    #  try to use `_make_request_from_queued_id` function for large batches
    def get_submissions(self,
                        after: datetime = None,
                        before: datetime = None,
                        get_comments: bool = False,
                        duplicate_action: str = 'newest',
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
                        contest_mode: bool = None) -> dict:

        if after and before:
            assert isinstance(after, datetime) and isinstance(before, datetime), \
                '`after` and `before` needs to be a `datetime` instance'

        pb = lambda x: x if x is None else ('true' if x else 'false')
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
            'over_18': pb(over_18),
            'is_video': pb(is_video),
            'locked': pb(locked),
            'stickied': pb(stickied),
            'spoiler': pb(spoiler),
            'contest_mode': pb(contest_mode),
        }
        # remove empty param values
        params = {k: v for k, v in params.items() if v}

        # check params
        check_result = self._check_params(**params)

        if check_result == 'timeframe-mode':
            submission_responses = self._timeframe_multithreader('submission', after, before, sort, params)

        elif check_result == 'single-mode' or check_result == 'size-mode':
            # TODO: later make it able to handle 100+ sizes - E: can't be done with MT perhaps
            # just make a single request. no need for multithreading
            submission_responses = self._make_request('submission', params)

        else:
            raise Exception("`check_result`: that's not supposed to happen")

        # indexing based on ID to dict with dupe detection
        submission_responses, submission_dupes = self.preprocess_json(submission_responses, duplicate_action)

        with open(os.path.join(self.cwd, 'dupe_submissions.json'), 'w') as f:
            json.dump(submission_dupes, f, indent=4)

        # comment fetching part
        if get_comments:
            self.logger.info('starting comment fetching...')
            post_ids = Queue()
            [post_ids.put(post['id']) for post in submission_responses.values()]  # create a Queue of post_id
            s = time.time()
            with ThreadPoolExecutor() as executor:
                futures = list()
                for i in range(self.comment_t):
                    self.logger.debug(f'started thread no.{i}')
                    futures.append(executor.submit(self._make_request_from_queued_id, q=post_ids,
                                                   params={}, thread_id=i, mode='comment', q_type='link_id'))
                    time.sleep(.5)

                for submission_id in submission_responses:  # create the comments entry and initialize it to empty list
                    submission_responses[submission_id]['comments'] = list()

                dupes_list = list()

                for future in as_completed(futures):
                    # futures.as_completed will hold the main thread until all threads are complete
                    comment_response, thread_id = future.result()
                    self.logger.debug(f't-{thread_id}: writing comments to data')
                    comment_response, comment_dupes = self.preprocess_json(comment_response, duplicate_action)
                    for comments in comment_response.values():
                        submission_responses[comments['link_id'][3:]]['comments'].append(comments)
                    dupes_list.append(comment_dupes)

                with open(os.path.join(self.cwd, 'dupe_comments_under_submissions.json'), 'w') as f:
                    json.dump(dupes_list, f, indent=4)

            self.logger.info(f'comment fetching time: {time.time() - s}sec')

        # filtering - also includes the 'comments' field in case comments were scraped.
        submission_responses = {post_id: {k: v[k] for k in filters + ['comments'] if k in v} for post_id, v in
                                submission_responses.items()} if filters else submission_responses

        return submission_responses

    def get_comments(self,
                     duplicate_action='newest',
                     after=None,
                     before=None,
                     filters: List[str] = None,
                     q=None,
                     ids=None,
                     limit=100,
                     sort='desc',
                     sort_type='created_utc',
                     author=None,
                     subreddit=None,
                     link_id=None) -> dict:

        if after and before:
            assert isinstance(after, datetime) and isinstance(before, datetime), \
                '`after` and `before` needs to be a `datetime` instance'

        params = {
            'sort': sort,
            'sort_type': sort_type,
            'size': limit,
            'ids': ','.join(ids) if ids else None,
            'q': q,
            'author': author,
            'subreddit': subreddit,
            'after': round(after.timestamp()) if after else None,
            'before': round(before.timestamp()) if before else None,
            'link_id': link_id,
        }

        # check params
        check_result = self._check_params(**params)

        if check_result == 'timeframe-mode':
            comment_responses = self._timeframe_multithreader('comment', after, before, sort, params)

        elif check_result == 'single-mode' or check_result == 'size-mode':
            # also make it so that it can handle 100+ size later on
            # just make a single request. no need for multithreading
            comment_responses = self._make_request('comment', params)

        else:
            raise Exception(f"`check_result`: <{check_result}> that's not supposed to happen")

        # indexing based on ID to dict with dupe detection
        comment_responses, comment_dupes = self.preprocess_json(comment_responses, duplicate_action)

        with open(os.path.join(self.cwd, 'dupe_comments.json'), 'w') as f:
            json.dump(comment_dupes, f, indent=4)

        # filtering
        comment_responses = {post_id: {k: v[k] for k in filters if k in v} for post_id, v in
                             comment_responses.items()} if filters else comment_responses

        return comment_responses

    def _make_request(self, mode, params, thread_id=0, headers=None) -> list:
        # `after` is inclusive, `before` is exclusive here

        assert mode in ['submission', 'comment'], "`mode` should be one of ['submission', 'comment']"
        url = self.submission_url if mode == 'submission' else self.comment_url

        headers = dict() if not headers else headers

        retries = 0
        while retries < self.max_retries:
            try:
                if 'after' in params:
                    params['after'] = params['after']-1

                response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
                result = response.json()['data']

                if response.ok:
                    with self.pool_lock:
                        self.logger.info(
                            f"t-{thread_id}: pool: {self.pool_amount} | len: {len(result)} | time: {response.elapsed}")
                else:
                    self.logger.error(f"t-{thread_id}: {response.status_code} - {response.elapsed}"
                                      f"\n{response.text}\n")

                self.request_sleep(thread_id)
                return result

            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.HTTPError) as err:
                retries += 1
                self.logger.warning(
                    f"t-{thread_id}: {err}\nRetrying... Attempt {retries}/{self.max_retries}")
                self.request_sleep(thread_id, self.backoffsec * retries)  # backoff

            except json.decoder.JSONDecodeError:
                retries += 1
                self.logger.warning(
                    f"t-{thread_id}: JSONDecodeError: Retrying... Attempt {retries}/{self.max_retries}")
                self.request_sleep(thread_id, self.backoffsec * retries)  # backoff

            except Exception as err:
                raise Exception(f't-{thread_id}: unexpected error: {err}')

        self.logger.error(f't-{thread_id}: failed request attempt. skipping...')
        return list()

    def _timeframe_multithreader(self, mode, after, before, sort, params):
        params['sort'] = 'desc'  # needs to be fixed to `desc` due to pivoting, going to reverse it later if `asc`
        # splitting up the timeframe for multithreading
        interval = (before - after) / self.threads
        splitpoints = [interval * i + after for i in range(self.threads + 1)]
        responses = [None for _ in range(self.threads)]
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
                futures.append(executor.submit(self._make_request_from_timeframe,
                                               mode=mode, params=thread_params, thread_id=i))

            for future in as_completed(futures):
                # futures.as_completed will hold the main thread until complete
                response, thread_id = future.result()
                if sort == 'desc':
                    responses[self.threads - 1 - thread_id] = response
                elif sort == 'asc':
                    response.reverse()
                    responses[thread_id] = response
                else:
                    raise Exception(f'Unexpected value for `sort`: {sort}')

        # de-nest the response
        denested_responses = list()
        for i, batch in enumerate(responses):
            if batch is None:
                self.logger.error(f'empty response for batch no.{i}! - possible omitted JSON data')
            else:
                denested_responses.extend(batch)

        # denested_responses = [post for batch in responses for post in batch]

        self.logger.info(f'{mode} fetching time: {time.time() - s}sec')

        return denested_responses

    #########
    # Utils #
    #########

    def preprocess_json(self, inp: List[dict], duplicate_action: str) -> (dict, dict):
        """
        :param inp: input data in a List[JSON/dict] type
        :param duplicate_action: what to do when dupes are detected - defaults to `get_submissions` value
        :return: a dict obj of indexed submissions/comments `{id: {...}, id: {...}, ...}` and a dict of dupes

        indexes the input `data` part of the response and also detects dupes
        """
        assert type(inp) is list

        dupes = dict()
        indexed = dict()
        for ent in inp:
            if ent['id'] in indexed:
                self.logger.info(f"dupe detected for {ent['id']}")

                if ent['id'] in dupes:  # when there's more than 3 duplicates
                    self.logger.debug(f"{ent['id']} multiple entry for dupe")
                    dupes[ent['id']].append(ent)
                else:  # making new entry for dupe
                    dupes[ent['id']] = [indexed[ent['id']]] + [ent]

                # placeholder 'dupe' to keep the position (dicts already sorted by date, can't be mixed up)
                # duplicate_action handler below will replace it later
                indexed[ent['id']] = 'dupe'
            else:
                indexed[ent['id']] = ent

        # duplicate_action: ['newest', 'oldest', 'remove', 'keep_original', 'keep_removed']
        for link_id, v in dupes.items():
            match duplicate_action:
                case 'newest':
                    indexed[link_id] = v[0]
                case 'oldest':
                    indexed[link_id] = v[-1]
                case 'remove':
                    del indexed[link_id]
                case 'keep_original':
                    for post in v:
                        if not self.is_deleted(post):
                            indexed[link_id] = post  # default keeping the newest undeleted version for now
                case 'keep_removed':
                    for post in v:
                        if self.is_deleted(post):
                            indexed[link_id] = post  # default keeping the newest deleted version for no
                case _:
                    raise Exception(f'invalid parameter for `duplicate_action`: '
                                    f"should be one of ['newest', 'oldest', 'remove', 'keep_original', 'keep_removed']")

        # delete all the submission/comment that has placeholders remaining
        def alert_dupe(item):
            key, value = item
            if value == 'dupe':
                self.logger.warning(f'failed `is_deleted` detection. deleting {key} from results!')
                return False
            return True
        indexed = {k: v for k, v in indexed.items() if alert_dupe((k, v))}

        """
        so the is_deleted function sometimes return all the dupes as either all False or True. 
        (False positives/ False negatives and so on)
        Which will prevent the 'dupe' placeholder from getting replaced, later causing errors.
        
        for now I made it so that it'll just delete the submission/comment that has placeholders remaining
        
        TODO: improve the is_deleted function or make it so that it'll detect and choose whatever appropriate.
        """

        for v in indexed.values():  # check if I didn't leave placeholders behind
            assert type(v) is dict, (f'indexed value came out as <{type(v)}: {v}> and is not `dict`,'
                                     f' perhaps placeholder is not removed?')

        return indexed, dupes

    def _check_params(self, **parameters) -> str:
        for k, v in parameters.items():
            if not v:  # ignore for None values
                continue

            match k:
                case 'duplicate_action':
                    assert v in ['newest', 'oldest', 'remove', 'keep_original', 'keep_removed'], \
                        "'duplicates' should be one of ['newest', 'oldest', 'remove', 'keep_original', 'keep_removed']"
                case 'sort':
                    assert v in ['desc', 'asc'], "'sort' should be one of ['desc', 'asc']"
                case 'sort_type':
                    assert v in ['created_utc', 'score', 'num_comments'], \
                        "'sort_type' should be one of ['created_utc', 'score', 'num_comments', 'created_utc']"
                case 'size':
                    if v > 100:
                        self.logger.warning('size based fetching is not yet supported')
                        return 'size-mode'

        if (st := parameters['sort_type']) and st != 'created_utc' and parameters['size'] > 100:
            self.logger.warning(f"the sort type: `{st}` doesn't support fetching more than 100 results. "
                                f"if needed, filter/sort the result from a specified timeframe "
                                f"with sort_type: `created_utc`")

            return 'single-mode'

        if ('after' in parameters) and ('before' in parameters):
            assert parameters['after'] <= parameters['before'], "'after' cannot be bigger than 'before'!"
            if (p := parameters['sort_type']) != 'created_utc':
                self.logger.warning(
                    f'sort_type: <{p}> is not supported while using the `after` and `before` parameters')
                parameters['sort_type'] = 'created_utc'

            return 'timeframe-mode'

        return 'single-mode'

    @staticmethod
    def is_deleted(json_obj) -> bool:
        """
        Check if a Reddit submission or comment is deleted.
        :param json_obj: dict object representing the submission or comment
        :return: `bool` indicating if the item is deleted or not

        To be deleted the text needs to:
         - start and end with [ ]
         - be under 100 chars
         - contain deleted or removed
        Examples: '[Deleted By User]' '[removed]' '[Removed by Reddit]'
        """
        if any(json_obj.get(field) is not None for field in ['removed_by_category', 'removal_reason']):
            return True

        author = json_obj.get('author')
        if author is None or (author.startswith('[') and author.endswith(']')):
            return True

        text_field = 'selftext' if json_obj.get('title') is not None else 'body'
        text = json_obj.get(text_field, "")

        if text == "" and not json_obj.get('title'):
            return True

        # Deleted or removed posts/comments often have specific text markers
        if re.match(r"\[.*\]", text) and len(text) <= 100 and any(
                term in text.lower() for term in ['deleted', 'removed']):
            return True

        return False

    #######################################
    # worker functions for multithreading #
    #######################################

    def _make_request_from_queued_id(self, mode: str, q: Queue, params, thread_id,
                                     q_type: str = 'ids', headers=None) -> (list, int):

        assert q_type in ['ids', 'link_id'], "q_type should be one of ['ids', 'link_id']"
        if mode == 'submission':
            assert q_type == 'ids', "`q_type` can't be anything other than `ids` when `mode` is in `submission`"
        headers = dict() if not headers else headers

        results = list()
        while not q.empty():  # if Queue is empty, end thread

            # retrieve an ID from the queue and set that as the link_id reqeust param
            self.logger.info(f't-{thread_id}: {q.qsize()} {mode}s{" groups" if q_type == "link_id" else ""} left')
            params[q_type] = q.get()

            # make a request using the new param
            self.logger.debug(f't-{thread_id}: making request')
            results += self._make_request(mode, params, thread_id, headers)

        return results, thread_id

    def _make_request_from_timeframe(self, mode: str, params, thread_id, headers=None) -> (list, int):
        assert (type(params['before']), type(params['after'])) == (int, int), \
            "params for _make_timeframe_submission_request needs to have 'before' and 'after' as epoch"

        headers = dict() if not headers else headers

        results = list()
        while True:
            self.logger.debug(f't-{thread_id}: making request')
            result = self._make_request(mode, params, thread_id, headers)

            if not len(result):  # when result is empty, finish scraping
                self.logger.info(f't-{thread_id}: finished.')
                return results, thread_id

            try:
                # set new pivot, result always returns starting from most-recent
                self.logger.debug(f't-{thread_id}: getting new pivot')
                params['before'] = round(float(result[-1]['created_utc']))

                if len(results):  # if results not empty, start 'omissions within same epoch' detection
                    pass
                    # TODO: add 'omissions within same epoch' detection part here
                    # get the last id from the result
                    # overlap the `after` for 1 epoch for the next request
                    # if (the last id) > (first id from second request) then start from (the last id)

            except KeyError as err:
                with open(os.path.join(self.cwd, "err_dump.json"), "w", encoding='utf-8') as f:
                    json.dump(result, f, indent=4)
                raise Exception(f't-{thread_id}: date format problem from submission. (dumped file):\n{err}')

            results += result


if __name__ == '__main__':
    # example code
    pp = Pushpull(sleepsec=3, threads=4, cwd='../results')

    res = pp.get_submissions(after=datetime(2024, 1, 1), before=datetime(2024, 1, 2),
                             subreddit='bluearchive', get_comments=True, duplicate_action='keep_original')

    with open("../results/data.json", "w", encoding='utf-8') as outfile:
        json.dump(res, outfile, indent=4)
