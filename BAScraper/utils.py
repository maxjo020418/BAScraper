from dataclasses import dataclass
from typing import List
import re
from typing import Union
import requests
import json
import time


class Params:
    @dataclass
    class PullPush:
        # constants settings
        # rate limit metrics as of feb 9th 2023
        MAX_POOL_SOFT = 15
        MAX_POOL_HARD = 30
        REFILL_SECOND = 60
        SUBMISSION_URI = 'https://api.pullpush.io/reddit/search/submission/'
        COMMENT_URI = 'https://api.pullpush.io/reddit/search/comment/'
        DIAGNOSTIC_URI = "https://api.pullpush.io/ping"

        @staticmethod
        def assert_op(val: str) -> bool:
            pattern = r"^(<|>)\d+$"
            return True if re.match(pattern, val) else False

        # schemes for the parameters
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

    @dataclass
    class Arctic:
        MAX_POOL_SOFT = 0
        MAX_POOL_HARD = 0
        REFILL_SECOND = 0
        SUBMISSION_URI = ''
        COMMENT_URI = ''
        DIAGNOSTIC_URI = ''


def process_params(service: Union["Params.PullPush", "Params.Arctic"],
                   mode, **params) -> str:
    """
    :param service: type of service the processing will be based on
    :param mode: mode as in whether it's for comments or submissions
    :param params: all the params needed
    :return: string that contains the structured URI

    check `URI_params.md` for accepted parameters and more details

    TODO: I forgot what the endpoint did when it had no params...
    """
    def assert_op(val: str) -> bool:
        pattern = r"^(<|>)\d+$"
        return True if re.match(pattern, val) else False

    # setting up the mode (whether it's for comments or submissions)
    if mode == 'comments':
        scheme = service.comment_params
        uri_string = service.COMMENT_URI
    elif mode == 'submissions':
        scheme = service.submission_params
        uri_string = service.SUBMISSION_URI
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


def make_request(service, uri: str) -> list:
    retries = 0
    while retries < service.max_retries:
        try:
            response = requests.get(uri, timeout=service.timeout)
            result = response.json()['data']

            if response.ok:
                service.logger.info(
                    f"pool: {service.pool_amount} | len: {len(result)} | time: {response.elapsed}")
            else:
                service.logger.error(f"{response.status_code} - {response.elapsed}"
                                  f"\n{response.text}\n")

            _request_sleep()
            return result

        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as err:
            retries += 1
            service.logger.warning(
                f"{err}\nRetrying... Attempt {retries}/{service.max_retries}")
            _request_sleep(service.backoff_sec * retries)  # backoff

        except json.decoder.JSONDecodeError:
            retries += 1
            service.logger.warning(
                f"JSONDecodeError: Retrying... Attempt {retries}/{service.max_retries}")
            _request_sleep(service.backoff_sec * retries)  # backoff

        except Exception as err:
            raise Exception(f'unexpected error: \n{err}')

    service.logger.error(f'failed request attempt. skipping...')
    return list()


def _request_sleep(service, sleep_sec=None) -> None:
    # in case of manual override
    sleep_sec = service.sleep_sec if sleep_sec is None else sleep_sec

    if time.time() - service.last_refilled > service.SERVICE.REFILL_SECOND:
        service.pool_amount = service.SERVICE.MAX_POOL_SOFT
        service.last_refilled = time.time()
        service.logger.info(f'pool refilled!')

    match service.pace_mode:
        case 'auto-hard' | 'auto-soft':
            if time.time() - service.last_refilled > service.SERVICE.REFILL_SECOND:

                match service.pace_mode:
                    case 'auto-hard':
                        service.pool_amount = service.SERVICE.MAX_POOL_HARD

                    case 'auto-soft':
                        service.pool_amount = service.SERVICE.MAX_POOL_SOFT

                service.last_refilled = time.time()
                service.logger.info(f'pool refilled!')

            if service.pool_amount > 0:
                time.sleep(sleep_sec)
                service.pool_amount -= 1
                return
            else:
                s = service.SERVICE.REFILL_SECOND - (time.time() - service.last_refilled)
                service.logger.info(f'hard limit reached! throttling for {s}...')
                service.logger.info(f'sleeping for {s}sec')
                time.sleep(s)
                _request_sleep(sleep_sec)

        case 'manual':
            time.sleep(sleep_sec)
            return

        case _:
            raise Exception(f' Wrong variable for `mode`!')


def _preprocess_json(obj):
    pass


def _is_deleted(obj) -> bool:
    """
    Check if a Reddit submission or comment is deleted.
    :param obj: dict object representing the submission or comment
    :return: `bool` indicating if the item is deleted or not

    To be deleted the text needs to:
     - start and end with [ ]
     - be under 100 chars
     - contain deleted or removed
    Examples: '[Deleted By User]' '[removed]' '[Removed by Reddit]'
    """
    if any(obj.get(field) is not None for field in ['removed_by_category', 'removal_reason']):
        return True

    author = obj.get('author')
    if author is None or (author.startswith('[') and author.endswith(']')):
        return True

    text_field = 'selftext' if obj.get('title') is not None else 'body'
    text = obj.get(text_field, "")

    if text == "" and not obj.get('title'):
        return True

    # Deleted or removed posts/comments often have specific text markers
    if re.match(r"\[.*]", text) and len(text) <= 100 and any(
            term in text.lower() for term in ['deleted', 'removed']):
        return True

    return False

@staticmethod
def _split_range(epoch_low: int, epoch_high: int, n: int) -> List[list]:
    segment_size = (epoch_high - epoch_low + 1) // n
    remainder = (epoch_high - epoch_low + 1) % n

    ranges = []
    current_low = epoch_low

    for i in range(n):
        current_high = current_low + segment_size - 1
        if remainder > 0:
            current_high += 1
            remainder -= 1
        ranges.append([current_low, current_high])
        current_low = current_high + 1

    return ranges
