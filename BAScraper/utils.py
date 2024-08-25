from datetime import datetime, date
import os.path
from dataclasses import dataclass
from typing import TYPE_CHECKING, Union, List, AnyStr
from time import perf_counter
import asyncio
import aiohttp
import json
import time
import re

import BAScraper.BAScraper

if TYPE_CHECKING:  # prevent circular imports due to the `typing` module
    from BAScraper.BAScraper_async import PullPushAsync


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


def _process_params(service: Union["Params.PullPush", "Params.Arctic"],
                    mode: str, **params) -> str:
    """
    :param service: type of service the processing will be based on
    :param mode: mode as in whether it's for comments or submissions
    :param params: all the params needed
    :return: string that contains the structured URI

    check `URI_params.md` for accepted parameters and more details
    """

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
            assert isinstance(v, dat[0]), f'{k} Param "{v}" should be {dat[0]}'
            if dat[1] is not None:
                assert dat[1](v), f"Param \"{k}: {v}\" doesn't meet or satisfy the requirements"
        else:
            raise Exception(f'\"{k}: {v}\" is not accepted as a parameter')

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


async def make_request(service: Union["PullPushAsync", ], mode: str, **params) -> List[Union[dict, None]]:
    """
    :param service:
        `PullPushAsync` or other top level object for `BAScraper` (`ArcticAsync` is planned).
        will get all the user parameters(`sleepsec`, `retries`, etc.) from that object.
    :param mode:
    :param params: mode as in whether it's for comments or submissions (or perhaps other)
    :return: list of dict containing each submission/comments
    """
    coro_name = asyncio.current_task().get_name()

    match service:
        case _ if isinstance(service, BAScraper.BAScraper_async.PullPushAsync):
            svc_type = Params.PullPush()
        case _:
            raise Exception(f'{service} -> No such service is supported')

    uri = _process_params(svc_type, mode, **params)

    retries = 0
    while retries < service.max_retries:
        try:
            service.logger.debug(f'{coro_name} | request sent!')
            tic = perf_counter()
            async with aiohttp.ClientSession() as session:
                async with session.get(uri, timeout=service.timeout) as response:
                    toc = perf_counter()
                    result = await response.json()
                    result = result['data']

                    if response.ok:
                        service.logger.info(
                            f"{coro_name} | pool: {service.pool_amount} | len: {len(result)} | time: {toc - tic:.2f}")
                        await _request_sleep(service)
                        return result
                    else:
                        # in case it doesn't raise an exception but still has errors, (cloudflare errors)
                        # usually caught by the try/except
                        response_text = await response.text()
                        service.logger.error(f"{coro_name} | {response.status}"
                                             f"\n{response_text}\n")
                        retries += 1
                        await _request_sleep(service, service.backoff_sec * retries)  # backoff
                        continue

        except asyncio.TimeoutError as err:
            retries += 1
            service.logger.warning(
                f"{coro_name} | TimeoutError: Retrying... Attempt {retries}/{service.max_retries}")
            await _request_sleep(service, service.backoff_sec * retries)  # backoff

        except (aiohttp.ClientConnectorError, aiohttp.ClientConnectionError) as err:
            retries += 1
            service.logger.warning(
                f"{coro_name} | ClientConnectionError: Retrying... Attempt {retries}/{service.max_retries}")
            await _request_sleep(service, service.backoff_sec * retries)  # backoff

        except json.decoder.JSONDecodeError:
            retries += 1
            service.logger.warning(
                f"{coro_name} | JSONDecodeError: Possible malformed response. Retrying... "
                f"Attempt {retries}/{service.max_retries}")
            await _request_sleep(service, service.backoff_sec * retries)  # backoff

        except Exception as err:
            raise Exception(f'{coro_name} | unexpected error: \n{err}')

    service.logger.error(f'{coro_name} | failed request attempt. skipping...')
    return list()


async def make_request_loop(service: Union["PullPushAsync", ], mode: str, **params) -> List[Union[dict, None]]:
    coro_name = asyncio.current_task().get_name()

    def temp_save(data):
        # saving individual returned results
        temp_fp = os.path.join(service.temp_dir.name,
                               f'{datetime.fromtimestamp(params['after']).strftime("%Y-%m-%d_%H-%M-%S")}__'
                               f'{datetime.fromtimestamp(params['before']).strftime("%Y-%m-%d_%H-%M-%S")}.json')
        with open(temp_fp, 'w+', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            service.logger.debug(f'Saved temp file at {temp_fp}')

    match service:
        case _ if isinstance(service, BAScraper.BAScraper_async.PullPushAsync):
            svc_type = Params.PullPush()
        case _:
            raise Exception(f'{type(service)} no such service is supported')

    assert 'after' in params and 'before' in params, \
        'for `make_request_loop` to work, it needs to have both `after` and `before` in the params'

    res = await make_request(service, mode, **params)
    temp_save(res)
    final_res = list() + res

    # at least for PullPush the newest result is returned first
    # due to this, the `after` parameter acts as an anchor point
    # and the `before` param reverses along headed to the `after`
    while len(res) > 0 and params['after'] < params['before']:
        params['before'] = int(res[-1]['created_utc']) - 1
        service.logger.debug(f'{coro_name} | param info: {params['after']} -> {params['before']}')
        res = await make_request(service, mode, **params)
        temp_save(res)
        final_res += res

    service.logger.debug(f'{coro_name} | finished!')

    return final_res


# ======== supporting utility functions ========


async def _request_sleep(service: Union["PullPushAsync", ], sleep_sec: float = None) -> None:
    # in case of manual override
    sleep_sec = service.sleep_sec if sleep_sec is None else sleep_sec

    if time.time() - service.last_refilled > service.SERVICE.REFILL_SECOND:
        service.pool_amount = service.SERVICE.MAX_POOL_SOFT
        service.last_refilled = time.time()
        service.logger.info(f'pool refilled!')

    match service.pace_mode:
        case 'auto-hard' | 'auto-soft':  # no difference in throttling for now
            if time.time() - service.last_refilled > service.SERVICE.REFILL_SECOND:

                match service.pace_mode:
                    case 'auto-hard':
                        service.pool_amount = service.SERVICE.MAX_POOL_HARD

                    case 'auto-soft':
                        service.pool_amount = service.SERVICE.MAX_POOL_SOFT

                service.last_refilled = time.time()
                service.logger.info(f'pool refilled!')

            if service.pool_amount > 0:
                service.pool_amount -= 1
                await asyncio.sleep(sleep_sec)
                return
            else:  # empty pool
                s = service.SERVICE.REFILL_SECOND - (time.time() - service.last_refilled)
                service.logger.info(f'hard limit reached! throttling for {round(s)} seconds...')
                time.sleep(s)
                await _request_sleep(service, sleep_sec)

        case 'manual':
            await asyncio.sleep(sleep_sec)
            return

        case _:
            raise Exception(f'Wrong variable for `mode`!')


def preprocess_json(service: Union["PullPushAsync", ], obj: List[dict], index: str = 'id') -> dict:
    """
    :param service:
    :param obj:
    :param index: what parameter should the indexing be based on
    :return: JSON(dict) indexed by the submission/comment ID
    """

    indexed = dict()
    for elem in obj:
        elem_id = elem[index]
        if elem_id not in indexed:  # new entry
            indexed[elem_id] = elem
        else:  # possible duplicate
            match service.duplicate_action:
                case 'keep_newest':
                    indexed[elem_id] = elem  # keep the last entry

                case 'keep_oldest':
                    pass  # keep the first entry

                case 'remove':
                    # putting a 'remove' flag for later removal
                    indexed[elem_id] = 'remove'

                case 'keep_original':
                    # essentially indexed_deleted is same as 'was the previous duplicate element a deleted one?'
                    indexed_deleted = _is_deleted(indexed[elem_id]) if indexed[elem_id] != 'remove' else True
                    curr_deleted = _is_deleted(elem)

                    if indexed_deleted and curr_deleted:
                        indexed[elem_id] = 'remove'
                    elif indexed_deleted and not curr_deleted:
                        indexed[elem_id] = elem
                    elif not indexed_deleted and curr_deleted:
                        pass
                    else:  # both not deleted
                        # service.logger.warning('multiple non-deleted duplicate versions exist! '
                        #                        'preserving newest non-deleted version.')
                        indexed[elem_id] = elem

                case 'keep_removed':
                    # essentially indexed_deleted is same as 'was the previous duplicate element a deleted one?'
                    indexed_deleted = _is_deleted(indexed[elem_id]) if indexed[elem_id] != 'remove' else False
                    curr_deleted = _is_deleted(elem)

                    if indexed_deleted and curr_deleted:
                        # service.logger.warning('multiple deleted duplicate versions exist! '
                        #                        'preserving newest deleted version.')
                        indexed[elem_id] = elem
                    elif indexed_deleted and not curr_deleted:
                        pass
                    elif not indexed_deleted and curr_deleted:
                        indexed[elem_id] = elem
                    else:  # both not deleted
                        indexed[elem_id] = 'remove'

                case _:
                    service.logger.warning('wrong `duplicate_action` reverting to default `keep_newest`')
                    indexed[elem_id] = elem  # keep the last entry

    if service.duplicate_action in ['keep_removed', 'keep_original', 'remove']:
        original_count = len(indexed)
        indexed = {k: v for k, v in indexed.items() if v != 'remove'}
        del_count = original_count - len(indexed)

        match service.duplicate_action:
            case 'keep_removed' | 'keep_original':
                service.logger.warning(f'{del_count} entry/entries have been removed due to '
                                       f'deletion check failure.') \
                    if del_count > 0 else None
            case 'removed':
                service.logger.info(f'{del_count} dupe entries removed.')

    return indexed


def _is_deleted(obj: dict) -> bool:
    """
    Check if a Reddit submission or comment is deleted.
    :param obj: dict object representing the submission or comment
    :return: `bool` indicating if the item is deleted or not

    To be deleted the text needs to:
     - start and end with [ ]
     - be under 100 chars
     - contain deleted or removed text marker
        Examples: '[Deleted By User]' '[removed]' '[Removed by Reddit]'
    """
    # parameter for debug/testing
    debug_delete = obj.get('deleted')
    if debug_delete is True:
        return True
    elif debug_delete is False:
        return False

    if any(obj.get(field) is not None for field in ['removed_by_category', 'removal_reason']):
        return True

    author = obj.get('author')
    if author is None or (author.startswith('[') and author.endswith(']')):
        return True

    text_field = 'selftext' if obj.get('title') is not None else 'body'
    text = obj.get(text_field, "")

    if text == "" and not obj.get('title'):
        return True

    # Deleted or removed posts/comments often have specific text markers: eg) [Removed by Reddit], [deleted]
    if re.match(r"\[.*]", text) and len(text) <= 100 and any(
            term in text.lower() for term in ['deleted', 'removed']):
        return True

    return False


def split_range(epoch_low: int, epoch_high: int, n: int) -> List[list]:
    segment_size = (epoch_high - epoch_low + 1) // n
    remainder = (epoch_high - epoch_low + 1) % n

    ranges = []
    current_low = epoch_low

    for i in range(n):
        current_high = current_low + segment_size - 1
        if remainder > 0:
            current_high += 1
            remainder -= 1
        ranges.append([int(current_low), int(current_high)])
        current_low = current_high + 1

    return ranges

def save_json(service: Union["PullPushAsync", ], file_name: str, data: dict):
    service.logger.info('Saving result...')

    # Ensure the file has the correct extension
    if not file_name.endswith('.json'):
        file_name += '.json'

    # Construct full path for the file
    file_path = os.path.join(service.save_dir, file_name)

    # Check if the file already exists
    if os.path.exists(file_path):
        service.logger.warning(f"File {file_path} already exists. Saving with a unique name.")
        base_name, ext = os.path.splitext(file_name)
        counter = 1
        while os.path.exists(file_path):
            new_file_name = f"{base_name}_{counter}{ext}"
            file_path = os.path.join(service.save_dir, new_file_name)
            counter += 1

    # Save the result to the file
    with open(file_path, 'w+') as f:
        json.dump(data, f, indent=4)
    service.logger.info(f"Result saved successfully as {file_path}")
