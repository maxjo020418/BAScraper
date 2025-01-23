import asyncio
import json
import os.path
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo
tz = ZoneInfo("UTC")
from time import perf_counter
from typing import TYPE_CHECKING, List, TypeVar

import aiohttp

if TYPE_CHECKING:  # prevent circular imports due to the `typing` module
    # from BAScraper.BAScraper_async import PullPushAsync, ArcticShiftAsync
    from BAScraper_async import BaseAsync, PullPushAsync, ArcticShiftAsync
    AsyncServices = TypeVar('AsyncServices', bound=BaseAsync)


# TODO: give appropriate Exception classes for all the base exceptions
def param_processor(service: 'AsyncServices',
                    mode: str, to_uri: bool = True,
                    **params) -> str | dict:
    """
    :param service: type of service the processing will be based on
    :param mode: specifies what kind of reqeust from the service it would be
    :param to_uri: specifies whether to convert request to uri
    :param params: all the params needed
    :return: string that contains the structured URI

    check `URI_params.md` for accepted parameters and more details
    """
    def param2str(param_k, param_v) -> str:
        # for when the param is 'ids' (List[str])
        if isinstance(param_v, list):
            return f'{param_k}={','.join(param_v)}'
        # if `param` is `bool`, the resulting string would be 'True', 'False' not 'true', 'false' we want
        return f'{param_k}={str(param_v).lower() if isinstance(param_v, bool) else str(param_v)}'

    # setting up the mode (what to fetch, get base uri and parameter scheme)
    scheme, base_uri_string = service.setup(mode)


    # assertion stuffs for all the params
    # TODO: assertions may differ from services - multiple types may be allowed in arctic shift, also, required params!
    #   special fields(assertions required) for arctic include: limit, body,

    # going to remove elems if required param exists
    # if required_params is not empty in the end -> required params are not used, error
    required_params = [k for k, v in scheme.items() if v['required']]

    for k, v in params.items():
        if (requirements := scheme.get(k)) is not None:
            assert isinstance(v, requirements['type']), f'{k} Param "{v}" should be {requirements['type']}'
            if (assertion_func := requirements.get('assert')) is not None:  # custom assertion functions
                assert assertion_func(v), f"Param \"{k}: {v}\" doesn't satisfy the requirements"
            if requirements['required']:  # requirements check
                required_params.remove(k)
            if (mod_func := requirements.get('modifications')) is not None:  # special modifiers
                params[k] = mod_func(v)
            if (reliance_func := requirements.get('reliance')) is not None:
                assert reliance_func(params), f'Param "{k}" has wrong reliance relations'
        else:
            raise Exception(f'"{k}" is not an accepted parameter')

    if len(required_params) > 0:  # if required_params is not empty
        raise Exception(f'{required_params} are required!')

    if to_uri:
        # empty `params` don't need the URI parts after, so just return
        return base_uri_string if len(params) <= 0 \
            else base_uri_string + '?' + '&'.join([param2str(k, v) for k, v in params.items()])
    else:
        return params


async def make_request(service: 'AsyncServices',
                       mode: str,
                       **params) -> List[dict | None]:
    """
    :param service:
        `PullPushAsync` or other top level class for `BAScraper` (`ArcticAsync` is planned).
        will get all the user parameters(`sleepsec`, `retries`, etc.) from that object.
    :param mode: specifies what kind of reqeust from the service it would be
    :param params: mode as in whether it's for comments or submissions (or perhaps other)
    :return: list of dict containing each submission/comments
    """
    coro_name = asyncio.current_task().get_name()

    uri = param_processor(service.SERVICE, mode, **params)
    service.logger.debug(f'{coro_name} | uri: {uri}')

    retries = 0
    while retries < service.max_retries:
        try:
            service.logger.debug(f'{coro_name} | request sent!')
            tic = perf_counter()
            async with aiohttp.ClientSession() as session:
                async with session.get(uri, timeout=service.timeout) as response:
                    toc = perf_counter()
                    headers = response.headers
                    result = await response.json()

                    try:
                        # sometimes the server experiences internal error,
                        # response itself is ok but contains no data.
                        result = result['data']
                    except KeyError:
                        service.logger.error(f"received wrong response! (missing 'data' field) -> {response}")
                        quit()

                    if response.ok:
                        service.logger.info(
                            f"{coro_name} | pool: {service.pool_amount} | len: {len(result)} | time: {toc - tic:.2f}")
                        await _request_sleep(service, headers=headers)
                        return result
                    else:
                        # in case it doesn't raise an exception but still has errors, (cloudflare errors)
                        # usually caught by the try/except
                        response_text = await response.text()
                        service.logger.error(f"{coro_name} | {response.status}"
                                             f"\n{response_text}\n")
                        retries += 1
                        await _request_sleep(service, service.backoff_sec * retries, headers)  # backoff
                        continue

        except asyncio.TimeoutError as err:
            retries += 1
            service.logger.warning(
                f"{coro_name} | TimeoutError: Retrying... Attempt {retries}/{service.max_retries}")
            await _request_sleep(service, service.backoff_sec * retries, headers)  # backoff

        except (aiohttp.ClientConnectorError, aiohttp.ClientConnectionError) as err:
            retries += 1
            service.logger.warning(
                f"{coro_name} | ClientConnectionError: Retrying... Attempt {retries}/{service.max_retries}")
            await _request_sleep(service, service.backoff_sec * retries, headers)  # backoff

        except (json.decoder.JSONDecodeError, aiohttp.client_exceptions.ContentTypeError) as err:
            retries += 1
            service.logger.warning(
                f"{err}\n{coro_name} | JSON Decode Error: Possible malformed response. Retrying... "
                f"Attempt {retries}/{service.max_retries}")
            await _request_sleep(service, service.backoff_sec * retries, headers)  # backoff

        except Exception as err:
            retries += 1
            service.logger.warning(f'{coro_name} | Unexpected error: \n{err} Retrying... '
                                   f"Attempt {retries}/{service.max_retries}")
            await _request_sleep(service, service.backoff_sec * retries, headers)  # backoff

    service.logger.error(f'{coro_name} | failed request attempt. skipping...')
    return list()


async def make_request_time_pagination(service: 'AsyncServices',
                                       mode: str,
                                       **params) -> List[dict | None]:
    """
    params desc. are the same as `make_request`, check there for explanations.
    this function is just a wrapper for `make_request` to do auto-pagination based on after/before time.
    :param service:
    :param mode:
    :param params:
    :return:
    """
    coro_name = asyncio.current_task().get_name()

    def temp_save(data):
        # saving individual returned results
        temp_fp = os.path.join(service.temp_dir.name,
                               f'{params['after']}__'
                               f'{params['before']}.json')
        with open(temp_fp, 'w+', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            service.logger.debug(f'Saved temp file at {temp_fp}')

    def epoch_to_iso(epoch: str | int) -> str:
        if isinstance(epoch, int):
            return datetime.fromtimestamp(epoch, tz=tz).replace(tzinfo=None).isoformat()
        else:
            return epoch

    assert 'after' in params and 'before' in params, \
        'for `make_request_loop` to work, it needs to have both `after` and `before` in the params'

    res = await make_request(service, mode, **params)
    temp_save(res)
    final_res = list() + res

    """
    For PullPush, the latest `created_utc` result is returned first
    due to this, the `after` parameter acts as an anchor point
    and the `before` param reverses along headed to the `after`
    example: 
    ← read from right to left as list by system
        [xxxxxxxxxxxxxxxxxxxxxx]
         ↑ after              ↑ before
        [xxxxxxxxxxxxxxxxxxxooo]
         ↑ after            ↑ before
        [xxxxxxxxxxxxxxxxoooooo]
         ↑ after         ↑ before
        ...
    """
    while len(res) > 0 and params['after'] < params['before']:
        params['before'] = int(res[-1]['created_utc']) - 1
        params['after'], params['before'] = epoch_to_iso(params['after']), epoch_to_iso(params['before'])
        service.logger.debug(f'{coro_name} | param info: {params['after']} -> {params['before']}')
        res = await make_request(service, mode, **params)
        temp_save(res)
        final_res += res

    service.logger.debug(f'{coro_name} | finished!')

    return final_res


# ======== supporting utility functions ========


async def _request_sleep(service: 'AsyncServices',
                         sleep_sec: float = None,
                         headers = None) -> None:
    # in case of manual override
    sleep_sec = service.sleep_sec if sleep_sec is None else sleep_sec

    if time.time() - service.last_refilled > service.SERVICE.REFILL_SECOND:
        service.pool_amount = service.SERVICE.MAX_POOL_SOFT
        service.last_refilled = time.time()
        service.logger.info(f'pool refilled!')

    match service.pace_mode:
        case 'auto-hard' | 'auto-soft':  # no difference in throttling method for now

            # if pool refill is possible, refilling job
            if time.time() - service.last_refilled > service.SERVICE.REFILL_SECOND:
                match service.pace_mode:
                    case 'auto-hard':
                        service.pool_amount = service.SERVICE.MAX_POOL_HARD

                    case 'auto-soft':
                        service.pool_amount = service.SERVICE.MAX_POOL_SOFT

                service.last_refilled = time.time()
                service.logger.info(f'pool refilled!')

            # normal operation
            if service.pool_amount > 0:
                service.pool_amount -= 1
                await asyncio.sleep(sleep_sec)
                return
            # empty pool
            else:
                s = service.SERVICE.REFILL_SECOND - (time.time() - service.last_refilled)
                service.logger.info(f'limit reached! throttling for {round(s)} seconds...')
                time.sleep(s)
                await _request_sleep(service, sleep_sec, headers)

        case 'auto-header':
            # checks if the response has a header
            if headers and \
                    (rl_remaining := headers.get('x-ratelimit-remaining')) and \
                    (rl_reset := headers.get('x-ratelimit-reset')):
                rl_remaining = int(rl_remaining)
                rl_reset = int(rl_reset)

                service.logger.debug(f'until pool refill: {rl_reset}s')
                service.pool_amount = rl_remaining

                # if pool empty, wait for rl_reset + 1 seconds
                if rl_remaining <= 1:
                    service.logger.info(f'limit reached! throttling for {rl_reset + 1} seconds...')
                    time.sleep(rl_reset + 1)
                    await _request_sleep(service, sleep_sec, headers)

            else:
                raise Exception('`auto-header` is used but ratelimit related header does not exist.')

        case 'manual':
            await asyncio.sleep(sleep_sec)
            return

        case _:
            raise Exception(f'Wrong value for `pace_mode`!')


def preprocess_json(service: 'AsyncServices',
                    obj: List[dict],
                    index: str = 'id') -> dict:
    """
    :param service:
    :param obj:
    :param index: what parameter should the indexing be based on
    :return: JSON(dict) indexed by the submission/comment ID
    """

    indexed = dict()
    for elem in obj:
        # for ArcticShift's /api/comments/tree endpoint, there is another layer of 'data'
        # the dict encapsulated in 'data' needs to be removed.
        if index not in elem:
            elem = elem['data']

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

    TODO: ArcticShift has a field called `_meta` containing info about edits (and maybe deletion?)
        might have to look into that.
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


def split_range(iso_low: str, iso_high: str, n: int) -> List[list]:
    epoch_low = int(datetime.fromisoformat(iso_low).timestamp())
    epoch_high = int(datetime.fromisoformat(iso_high).timestamp())

    segment_size = (epoch_high - epoch_low + 1) // n
    remainder = (epoch_high - epoch_low + 1) % n

    ranges = []
    current_low = epoch_low

    for i in range(n):
        current_high = current_low + segment_size - 1
        if remainder > 0:
            current_high += 1
            remainder -= 1
        ranges.append([
            datetime.fromtimestamp(current_low).isoformat(),
            datetime.fromtimestamp(current_high).isoformat()
        ])
        current_low = current_high + 1

    return ranges



def save_json(service: 'AsyncServices',
              file_name: str,
              data: dict) -> None:
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
