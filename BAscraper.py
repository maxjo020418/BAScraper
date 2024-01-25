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
                        contest_mode: bool = None):

        assert isinstance(after, datetime) and isinstance(before, datetime), \
            '`after` and `before` needs to be a `datetime` instance'

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

        with open('dupe_submissions.json', 'w') as f:
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

                with open('dupe_comments_under_submissions.json', 'w') as f:
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
                     link_id=None):

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

        with open('dupe_comments.json', 'w') as f:
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

                if response.ok:
                    self.logger.info(
                        f"t-{thread_id}: {response.status_code} - {response.elapsed}")
                else:
                    self.logger.error(f"t-{thread_id}: {response.status_code} - {response.elapsed}"
                                      f"\n{response.text}\n")

                time.sleep(self.sleepsec)
                result = response.json()['data']
                return result

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
                    responses[len(responses) - 1 - thread_id] = response
                else:  # 'asc'
                    responses.reverse()
                    responses[thread_id] = response

        # de-nest the response
        responses = [post for batch in responses for post in batch]

        self.logger.info(f'{mode} fetching time: {time.time() - s}sec')

        return responses

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

    def _check_params(self, **parameters):
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

        if parameters['after'] and parameters['before']:
            assert parameters['after'] <= parameters['before'], "'after' cannot be bigger than 'before'!"

        return 'timeframe-mode'

    @staticmethod
    def is_deleted(json_obj) -> bool:
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
                with open("errfile.json", "w", encoding='utf-8') as f:
                    json.dump(result, f, indent=4)
                raise Exception(f't-{thread_id}: date format problem from submission. (dumped file):\n{err}')

            results += result


if __name__ == '__main__':
    # example code
    pp = Pushpull(sleepsec=3, threads=4)

    # res = pp.get_submissions(after=datetime(2024, 1, 1), before=datetime(2024, 1, 2),
    #                         subreddit='bluearchive', get_comments=True, duplicate_action='keep_original', sort='desc')
    # ['newest', 'oldest', 'remove', 'keep_original', 'keep_removed']
    res = pp.get_submissions(
        after=datetime(2024, 1, 1), before=datetime(2024, 1, 1, 3),
        subreddit='bluearchive', duplicate_action='keep_original', sort='desc', get_comments=True)


    with open("example.json", "w", encoding='utf-8') as outfile:
        json.dump(res, outfile, indent=4)
