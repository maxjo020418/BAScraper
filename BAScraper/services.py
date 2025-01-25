import re
from dataclasses import dataclass
from urllib.parse import urljoin
from datetime import datetime


def define_param(param_type,
                 assertion=None,
                 required=False,
                 modifications=None,
                 reliance=None) -> dict:
    return {
        'type': param_type,
        'assert': assertion,
        'required': required,
        'modifications': modifications,
        'reliance': reliance,
    }

def is_iso8601(s: str) -> bool:
    try:
        datetime.fromisoformat(s)
        return True
    except ValueError:
        return False

def to_epoch(s: str) -> int:
    dt = datetime.fromisoformat(s)
    return int(dt.timestamp())


# ================================================================


class Params:

    @dataclass
    class Base:
        def setup(self):
            raise NotImplementedError


    @dataclass
    class PullPush:
        # constants settings
        # rate limit metrics as of feb 9th 2023
        MAX_POOL_SOFT = 15
        MAX_POOL_HARD = 30
        REFILL_SECOND = 60

        BASE = 'https://api.pullpush.io'
        DIAGNOSTIC = urljoin(BASE, "ping")

        SUBMISSION = urljoin(BASE, 'reddit/search/submission/')
        COMMENT = urljoin(BASE, 'reddit/search/comment/')

        @staticmethod
        def assert_op(val: str) -> bool:
            pattern = r"^(<|>)\d+$"
            return True if re.match(pattern, val) else False

        # ================================================================

        # schemes for the parameters
        # {parameter : {'type': accepted_type, 'assert': assertion_func}} key, val pair
        _common_params = {
            'q': define_param(str),
            'ids': define_param(list),
            'size': define_param(int, lambda x: x <= 100),
            'sort': define_param(str, lambda x: x in ("asc", "desc")),
            'sort_type': define_param(str, lambda x: x in ("score", "num_comments", "created_utc")),
            'author': define_param(str),
            'subreddit': define_param(str),
            'after': define_param(str, is_iso8601, modifications=to_epoch),
            'before': define_param(str, is_iso8601, modifications=to_epoch),
        }

        comment_params = {**_common_params, 'link_id': define_param(str)}

        submission_params = {
            **_common_params,
            'title': define_param(str),
            'selftext': define_param(str),
            'score': define_param(str, assert_op),
            'num_comments': define_param(str, assert_op),
            'over_18': define_param(bool),
            'is_video': define_param(bool),
            'locked': define_param(bool),
            'stickied': define_param(bool),
            'spoiler': define_param(bool),
            'contest_mode': define_param(bool),
        }

        # ================================================================

        def setup(self, mode: str) -> tuple:  # returns (scheme, base_uri_string)
            match mode:
                case 'comments':
                    return self.comment_params, self.COMMENT
                case 'submissions':
                    return self.submission_params, self.SUBMISSION
                case _:
                    raise Exception('wrong `mode` param for `param_processor`')


    @dataclass
    class ArcticShift:
        """
        note that the structure of 'comments_tree_search' is different from usual.
        encapsulated once more:
        {"data":
            [
                {
                "kind":"t1",
                "data": {...}
                },
                ...
            ]
        }
        """

        # constants settings
        # `X-RateLimit-Remaining` is used for ratelimiting
        # POOL related parameters are not used here usually - placeholder values
        MAX_POOL_SOFT = 1000
        MAX_POOL_HARD = 1000
        REFILL_SECOND = 60

        _BASE = 'https://arctic-shift.photon-reddit.com'
        DIAGNOSTIC = 'https://status.arctic-shift.photon-reddit.com'

        # ================================================================

        _SUBMISSION_BASE = urljoin(_BASE, 'api/posts/')
        _COMMENT_BASE = urljoin(_BASE, 'api/comments/')

        SUBMISSION_SEARCH = urljoin(_SUBMISSION_BASE, 'search')
        SUBMISSION_ID = urljoin(_SUBMISSION_BASE, 'ids')
        SUBMISSION_AGG = urljoin(_SUBMISSION_BASE, 'aggregate')

        COMMENT_SEARCH = urljoin(_COMMENT_BASE, 'search')
        COMMENT_ID = urljoin(_COMMENT_BASE, 'ids')
        COMMENT_AGG = urljoin(_COMMENT_BASE, 'aggregate')
        COMMENT_TREE = urljoin(_COMMENT_BASE, 'tree')

        # ================================================================

        _SUBREDDIT_BASE = urljoin(_BASE, 'api/subreddits/')
        _USER_BASE = urljoin(_BASE, 'api/users/')

        SUBREDDIT_ID = urljoin(_SUBREDDIT_BASE, 'ids')
        SUBREDDIT_SEARCH = urljoin(_SUBREDDIT_BASE, 'search')

        USER_ID = urljoin(_USER_BASE, 'ids')
        USER_SEARCH = urljoin(_USER_BASE, 'search')
        USER_AGG_FLAIRS = urljoin(_USER_BASE, 'aggregate_flairs')

        _USER_INTERACTIONS = urljoin(_USER_BASE, 'interactions/')  # sub-base, cannot be used standalone
        USER_INTERACTIONS_USR = urljoin(_USER_INTERACTIONS, 'users')
        USER_INTERACTIONS_USR_LIST = urljoin(USER_INTERACTIONS_USR, 'list')
        USER_INTERACTIONS_SUBREDDIT = urljoin(_USER_INTERACTIONS, 'subreddits')

        # ================================================================

        '''
        Full text search
        For details, see https://www.postgresql.org/docs/current/textsearch-controls.html, 
        specifically the websearch_to_tsquery function.

        But in short:
        Word1 Word2 searches for Word1 and Word2, regardless of order
        "Word1 Word2" searches for Word1 followed by Word2, possibly with other words in between
        Word1 OR Word2 searches for Word1 or Word2
        Word1 -Word2 searches for Word1 but not Word2
        '''

        # ================================================================

        # returned result's fields

        _common_fields = [
            'author',
            'author_fullname',
            'author_flair_text',
            'created_utc',
            'distinguished',
            'id',
            'retrieved_on',
            'subreddit',
            'subreddit_id',
            'score'
        ]

        submission_fields = [
            'crosspost_parent',
            'link_flair_text',
            'num_comments',
            'over_18',
            'post_hint',
            'selftext',
            'spoiler',
            'title',
            'url'
        ] + _common_fields

        comment_fields = [
            'body', 'link_id', 'parent_id'
        ] + _common_fields

        subreddit_fields = [  # doesn't rely on `common_fields`
            'created_utc',
            'description',
            'public_description',
            'display_name',
            'id',
            'over18',
            'retrieved_on',
            'subscribers',
            'title',
            '_meta'
        ]

        # ================================================================

        """
        Schemes for the parameters
        key, val pair:
        {parameter: {'type': accepted_type, 
                    'assert': assertion_func -> return True for OK, False for FAIL, 
                    'required': bool, 
                    'modifications': func_or_none, 
                    'reliance': func_or_none(params) input as all input params}
        }
        """

        # for submissions, comments, subreddits, users
        id_search_params = {
            'ids': define_param(list, lambda x: len(x) <= 500, True),
            'md2html': define_param(bool),
            'fields': define_param(list),
        }

        # regular search for submissions, comments
        _common_search_params = {
            'author': define_param(str),
            'subreddit': define_param(str),
            'author_flair_text': define_param(str),
            'after': define_param(str, is_iso8601),  # ISO 8601
            'before': define_param(str, is_iso8601),  # ISO 8601
            # do recommend 'auto', limit = 0 FOR AUTO!
            'limit': define_param(int, lambda x: 0 <= x <= 100, False, lambda x: 'auto' if x == 0 else x),
            'sort': define_param(str, lambda x: x in ('asc', 'desc')),
            'md2html': define_param(bool),
        }

        submission_search_params = {
            **_common_search_params,
            'crosspost_parent_id': define_param(str),
            'over_18': define_param(bool),
            'spoiler': define_param(bool),
            'title': define_param(str),
            'selftext': define_param(str),
            'link_flair_text': define_param(str),
            'query': define_param(str),  # search for both title and selftext
            'url': define_param(str),  # content url prefix match such as YouTube or imgur
            'url_exact': define_param(bool),  # if exact match of above url field is going to be used
            # IDE spits shit when not specifying full path for some reason
            'fields': define_param(list, lambda x: all([x for x in Params.ArcticShift.submission_fields])),
        }

        comment_search_params = {
            **_common_search_params,
            # may not be supported for very active users -> give warning prompt when used
            'body': define_param(str, reliance=lambda params: any([needed in params
                                                                   for needed in
                                                                   ('author', 'subreddit', 'link_id', 'parent_id')])),
            # this is for comments under a submission
            'link_id': define_param(str),
            'parent_id': define_param(str),
            # IDE spits shit when not specifying full path for some reason
            'fields': define_param(list, lambda x: all([x for x in Params.ArcticShift.comment_fields])),
        }

        # get a comment tree
        comment_tree_params = {
            'link_id': define_param(str, required=True),
            # all comments if not specified
            'parent_id': define_param(str),
            # just use a large number to return all
            'limit': define_param(int, lambda x: 1 <= x),
            # for comment collapse thresh, but doesn't seem to do anything?
            'start_breadth': define_param(int, lambda x: 0 <= x),
            'start_depth': define_param(int, lambda x: 0 <= x),
            'md2html': define_param(bool),
            # IDE spits shit when not specifying full path for some reason
            'fields': define_param(list, lambda x: all([x for x in Params.ArcticShift.submission_fields])),
        }

        # aggregation (group by) for comment and submissions
        # (note: All filtering related parameters from the search endpoints are supported.)
        _common_agg_params = {
            'aggregate': define_param(str, lambda x: x in ('created_utc', 'author', 'subreddit'), True),
            'frequency': define_param(str, required=False,
                                      reliance=lambda params: params['aggregate'] == 'created_utc'),
            'limit': define_param(int, lambda x: x >= 1),
            'min_count': define_param(int, lambda x: x >= 0,
                                      reliance=lambda params: params['aggregate'] != 'created_utc'),
            'sort': define_param(str, lambda x: x in ('asc', 'desc')),
        }

        submission_agg_params = _common_agg_params | submission_search_params

        comment_agg_params = _common_agg_params | comment_search_params

        subreddit_params = {
            'subreddit': define_param(str),
            'subreddit_prefix': define_param(str),
            'after': define_param(str, is_iso8601),
            'before': define_param(str, is_iso8601),
            'min_subscribers': define_param(int, lambda x: x >= 0),
            'max_subscribers': define_param(int, lambda x: x >= 0),
            'over18': define_param(bool),
            'limit': define_param(int, lambda x: 1 <= x <= 1000),
            'sort': define_param(str, lambda x: x in ('asc', 'desc')),
            'sort_type': define_param(str, lambda x: x in ('created_utc', 'subscribers', 'subreddit')),
        }

        # user related params (regular search, interactions and flairs
        user_params = {
            'author': define_param(str),
            'author_prefix': define_param(str),
            'min_num_posts': define_param(int, lambda x: x >= 0),
            'min_num_comments': define_param(int, lambda x: x >= 0),
            'active_since': define_param(str, is_iso8601),
            'min_karma': define_param(int, lambda x: x >= 0),
            'limit': define_param(int, lambda x: 1 <= x <= 1000),
            'sort': define_param(str, lambda x: x in ('asc', 'desc')),
            'sort_type': define_param(str, lambda x: x in ('author', 'total_karma')),
        }

        # works for both `/api/users/interactions/users` and `/api/users/interactions/users/list`
        # `/list` lists all the individual interactions rather than aggregating them
        user_interactions_users_params = {
            'author': define_param(str, required=True),
            'subreddit': define_param(str),
            'after': define_param(str, is_iso8601),
            'before': define_param(str, is_iso8601),
            'min_count': define_param(int, lambda x: x >= 0),
            'limit': define_param(int, lambda x: x >= 1),
        }

        user_interactions_subreddits_params = {
            'author': define_param(str, required=True),
            'weight_posts': define_param(float, lambda x: x >= 0),
            'weight_comments': define_param(float, lambda x: x >= 0),
            'before': define_param(str, is_iso8601),
            'after': define_param(str, is_iso8601),
            'min_count': define_param(int, lambda x: x >= 0),
            'limit': define_param(int, lambda x: x >= 1),
        }

        users_agg_flairs_params = {
            'author': define_param(str, required=True),
        }

        # ================================================================

        def setup(self, mode: str) -> tuple:  # returns (scheme, base_uri_string)
            match mode:
                # id lookup
                case 'submissions_id_lookup':
                    return self.id_search_params, self.SUBMISSION_ID
                case 'comments_id_lookup':
                    return self.id_search_params, self.COMMENT_ID
                case 'subreddits_id_lookup':
                    return self.id_search_params, self.SUBREDDIT_ID
                case 'users_id_lookup':
                    return self.id_search_params, self.USER_ID

                # regular searches
                case 'submissions_search':
                    return self.submission_search_params, self.SUBMISSION_SEARCH
                case 'comments_search':
                    return self.comment_search_params, self.COMMENT_SEARCH
                case 'comments_tree_search':
                    return self.comment_tree_params, self.COMMENT_TREE
                case 'subreddits_search':
                    return self.subreddit_params, self.SUBREDDIT_SEARCH
                case 'users_search':
                    return self.user_params, self.USER_SEARCH

                # aggregations
                case 'submissions_aggregation':
                    return self.submission_agg_params, self.SUBMISSION_AGG
                case 'comments_aggregation':
                    return self.comment_agg_params, self.COMMENT_AGG
                case 'user_flairs_aggregation':
                    return self.users_agg_flairs_params, self.USER_AGG_FLAIRS

                # interactions
                case 'user_interactions':
                    return self.user_interactions_users_params, self.USER_INTERACTIONS_USR
                case 'list_users_interactions':
                    return self.user_interactions_users_params, self.USER_INTERACTIONS_USR_LIST
                case 'subreddits_interactions':
                    return self.user_interactions_subreddits_params, self.USER_INTERACTIONS_USR_LIST

                case _:
                    raise Exception('wrong `mode` param for `param_processor`')
