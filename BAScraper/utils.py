from dataclasses import dataclass
from typing import List
import re
from typing import Union


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

    @staticmethod
    def _process_params(service: Union["PullPush", "Arctic"], mode, **params) -> str:
        """
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


class BAUtils:
    def __init__(self):
        pass

    def _preprocess_json(self, obj):
        pass

    @staticmethod
    def _is_deleted(obj) -> bool:
        pass

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
