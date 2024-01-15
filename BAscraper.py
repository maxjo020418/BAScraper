import requests
import time
import logging
import json

from dataclasses import dataclass
from typing import List
from datetime import datetime

from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue

from threading import Lock
import pprint
pretty = pprint.PrettyPrinter(indent=4).pprint

# imports no longer used
# from dotenv import load_dotenv
# import os


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

        # Rlocks are no longer used for now
        # self.print_lock = RLock()
        self.file_lock = Lock()

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
                        contest_mode: bool = None):
        """
        :param after:
        :param before:
        :param get_comments:
        :param duplicate_action:
        :param filters:
        :param sort:
        :param sort_type:
        :param limit:
        :param ids:
        :param q:
        :param title:
        :param selftext:
        :param author:
        :param subreddit:
        :param score:
        :param num_comments:
        :param over_18:
        :param is_video:
        :param locked:
        :param stickied:
        :param spoiler:
        :param contest_mode:
        :return:

        this will only scrape based on date, so 'after' and 'before' is mandatory
        also, 'limit' is the number of posts per request, not the total no.

        if ('after' OR 'before' is None) OR ('sort_type' is NOT 'created_utc')
        it will only scrape up to 'limit' amount of posts.

        might add these params from pmaw
        max_sleep (int, optional): Maximum rate-limit sleep time (in seconds) between requests, defaults to 60s.
        rate_limit (int, optional): Target number of requests per minute for rate-averaging,
                                    defaults to 60 requests per minute.

        dupe detection(removed posts & comments) will work under the premise that the API returns
        2 values which is like: [...{removed submission}, {old cached submission}...]
        I have to check if it'll return more than 2 values - perhaps posts/comments being edited
        """

        # check params
        assert duplicate_action in ['newest', 'oldest', 'remove', 'keep_original', 'keep_removed'], \
            "'duplicates' should be one of ['newest', 'oldest', 'remove', 'keep_original', 'keep_removed']"
        assert sort in ['desc', 'asc'], "'sort' should be one of ['desc', 'asc']"
        assert sort_type in ['created_utc', 'score', 'num_comments'], \
            "'sort_type' should be one of ['created_utc', 'score', 'num_comments', 'created_utc']"
        assert limit <= 100, "'limit' should be <= 100"
        if after and before:
            assert after <= before, "'after' cannot be bigger than 'before'!"

        def _ask():  # TODO: remove this and do automatically, get default config as param
            inp = input('Would you like to enable timeframe based scraping? (Y/n) ').lower()
            if inp in ['y', '']:
                self.logger.info("timeframe based scraping is enabled. 'sort' is fixed to 'desc'")
                return True
            elif inp == 'n':
                return False
            else:
                _ask()

        if not (after or before):  # no date specified, so using default
            timeframe_mode = False
        elif sort_type != 'created_utc':  # unable to paginate in this case
            (self.logger.warning
             (f"sort_type: '{sort_type}' does not support getting more than {limit} posts. "
              f"pagination is not possible."))
            timeframe_mode = False
        else:
            timeframe_mode = _ask()
            if timeframe_mode:
                # in timeframe_mode sort needs to be fixed to descending
                # due to how _make_timeframe_submission_request works
                if sort == 'asc':
                    self.logger.warning("'sort' method will default to 'desc' due to how pagination works.")
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
            submission_response = [None for _ in range(self.threads)]
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
                    comment_response, thread_id = future.result()
                    submission_response[thread_id] = comment_response

            submission_response = [post for batch in submission_response for post in batch]  # de-nest the submission_response

            self.logger.info(f'submission fetching time: {time.time() - s}sec')

        else:
            # if not timeframe_mode, just make a single request. no need for multithreading
            submission_response = self._make_request('submission', params)

        ################################################################################
        # TODO: also, add the logic for this:
        # get the last id from the result
        # overlap the `after` for 1 epoch for the next request
        # if (the last id) > (first id from second request) then start from (the last id)
        ################################################################################

        # indexing based on ID to dict with dupe detection
        self.logger.info(f"indexing submissions...")
        submission_response, submission_dupes = self.preprocess_json(submission_response, duplicate_action)

        with open('dupe_submissions.json', 'w') as f:
            json.dump(submission_dupes, f, indent=4)

        # comment fetching part
        if get_comments:
            self.logger.info('starting comment fetching...')
            post_ids = Queue()
            [post_ids.put(post['id']) for post in submission_response.values()]  # create a Queue of post_id
            s = time.time()
            with ThreadPoolExecutor() as executor:
                futures = list()
                for i in range(self.comment_t):
                    self.logger.debug(f'started thread no.{i}')
                    futures.append(executor.submit(self._make_queued_comment_request, q=post_ids,
                                                   params={}, thread_id=i))
                    time.sleep(.5)

                for submission_id in submission_response:  # create the comments entry and initialize it to empty list
                    submission_response[submission_id]['comments'] = list()

                dupes_list = list()

                for future in as_completed(futures):
                    # futures.as_completed will hold the main thread until all threads are complete
                    comment_response, thread_id = future.result()
                    self.logger.debug(f't-{thread_id}: writing comments to data')
                    comment_response, comment_dupes = self.preprocess_json(comment_response, duplicate_action)
                    for comments in comment_response.values():
                        submission_response[comments['link_id'][3:]]['comments'].append(comments)
                    dupes_list.append(comment_dupes)

                with open('dupe_comments.json', 'w') as f:
                    json.dump(dupes_list, f, indent=4)

            self.logger.info(f'comment fetching time: {time.time() - s}sec')

        # filtering - also includes the 'comments' field in case comments were scraped.e
        submission_response = {post_id: {k: v[k] for k in filters + ['comments'] if k in v} for post_id, v in
                               submission_response.items()} if filters else submission_response

        return submission_response

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
                    f"t-{thread_id}: {err}\nRetrying... Attempt {retries}/{self.max_retries}")
                time.sleep(self.backoffsec * retries)  # backoff

            except json.decoder.JSONDecodeError:
                retries += 1
                self.logger.warning(
                    f"t-{thread_id}: JSONDecodeError: Retrying... Attempt {retries}/{self.max_retries}")
                time.sleep(self.backoffsec * retries)  # backoff

            except Exception as err:
                raise Exception(f't-{thread_id}: unexpected error: {err}')

        self.logger.error(f't-{thread_id}: failed request attempt. skipping...')
        return list()

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

        # TODO: add appropriate duplicate_action here
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
                    raise Exception(f'invalid parameter for `duplicate_action`: {duplicate_action}')

        # delete all the submission/comment that has placeholders remaining
        del_list = list()
        for k, v in indexed.items():
            if type(v) is not dict:
                del_list.append(k)
        for k in del_list:
            if k in del_list:
                logging.warning(f'deleting {k}!!! failed `is_deleted` detection. [Temporary]')
                del indexed[k]

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

    @staticmethod
    def is_deleted(json_obj):
        """
        :param json_obj: dict obj
        :return: `bool` if the submission/comment is deleted or not
        """
        is_topic = json_obj.get('title') is not None
        author = json_obj.get('author')
        if author is None:
            return True
        if author[0] == '[' and author[-1] == ']':
            return True
        if json_obj.get('removed_by_category') is not None:
            return True
        if json_obj.get('removal_reason') is not None:
            return True
        crc = json_obj.get('collapsed_reason_code')
        if crc is not None and crc.lower() == 'deleted':
            return True

        if is_topic:
            text = json_obj.get('selftext')
        else:
            text = json_obj.get('body')

        if text is None:
            return True
        if len(text) == 0:
            if is_topic:
                return False
            else:
                return True

        # To be deleted the text needs to:
        # - start and end with [ ]
        # - be under 100 chars
        # - contain deleted or removed
        # Examples: '[ Deleted By User ]' '[removed]' '[ Removed by Reddit ]'

        if not (text[0] == '[' and text[-1] == ']'):
            return False
        if len(text) > 100:
            return False
        text = text.lower()
        if not ('deleted' in text or 'removed' in text):
            return False
        return True

    #######################################
    # worker functions for multithreading #
    #######################################

    def _make_queued_comment_request(self, q: Queue, params, thread_id, headers=None) -> (list, int):

        headers = dict() if not headers else headers

        results = list()
        while not q.empty():  # if Queue is empty, end thread

            # retrieve an ID from the queue and set that as the link_id reqeust param
            self.logger.info(f't-{thread_id}: {q.qsize()} comments left')
            link_id = q.get()
            params['link_id'] = link_id

            # make a request using the new param
            self.logger.debug(f't-{thread_id}: making request')
            results += self._make_request('comment', params, thread_id, headers)

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

    res = pp.get_submissions(after=datetime(2024, 1, 1), before=datetime(2024, 1, 1, 6),
                             subreddit='bluearchive', get_comments=True, duplicate_action='keep_original')
    # ['newest', 'oldest', 'remove', 'keep_original', 'keep_removed']

    with open("example.json", "w", encoding='utf-8') as outfile:
        json.dump(res, outfile, indent=4)
