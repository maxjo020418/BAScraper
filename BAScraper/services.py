import re
from dataclasses import dataclass
from urllib.parse import urljoin
from datetime import datetime
# from typing import List


class Params:
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

        @staticmethod
        def define_param(param_type, assertion=None):
            return {'type': param_type, 'assert': assertion}

        # schemes for the parameters
        # {parameter : {'type': accepted_type, 'assert': assertion_func}} key, val pair
        common_params = {
            'q': define_param(str),
            'ids': define_param(list),
            'size': define_param(int, lambda x: x <= 100),
            'sort': define_param(str, lambda x: x in ("asc", "desc")),
            'sort_type': define_param(str, lambda x: x in ("score", "num_comments", "created_utc")),
            'author': define_param(str),
            'subreddit': define_param(str),
            'after': define_param(int),
            'before': define_param(int),
        }

        comment_params = {**common_params, 'link_id': define_param(str)}

        submission_params = {
            **common_params,
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

    @dataclass
    class ArcticShift:
        # constants settings
        # rate limit metrics as of Jul 20th 2024
        # `X-RateLimit-Remaining` header needs to be checked!
        # POOL related parameters are not used here
        MAX_POOL_SOFT = 0
        MAX_POOL_HARD = 0
        REFILL_SECOND = 0

        BASE = 'https://arctic-shift.photon-reddit.com'
        DIAGNOSTIC = 'https://status.arctic-shift.photon-reddit.com'

        # ================================================================

        SUBMISSION_BASE = urljoin(BASE, 'api/posts')
        COMMENT_BASE = urljoin(BASE, 'api/comments')

        SUBMISSION_SEARCH = urljoin(SUBMISSION_BASE, 'search')
        SUBMISSION_ID = urljoin(SUBMISSION_BASE, 'ids')
        SUBMISSION_AGG = urljoin(SUBMISSION_BASE, 'aggregate')

        COMMENT_SEARCH = urljoin(COMMENT_BASE, 'search')
        COMMENT_ID = urljoin(COMMENT_BASE, 'ids')
        COMMENT_AGG = urljoin(COMMENT_BASE, 'aggregate')
        COMMENT_TREE = urljoin(COMMENT_BASE, 'tree')

        # ================================================================

        SUBREDDIT_BASE = urljoin(BASE, 'api/subreddits')
        USER_BASE = urljoin(BASE, 'api/users')

        SUBREDDIT_ID = urljoin(SUBREDDIT_BASE, 'ids')
        SUBREDDIT_SEARCH = urljoin(SUBREDDIT_BASE, 'search')

        USER_ID = urljoin(USER_BASE, 'ids')
        USER_SEARCH = urljoin(USER_BASE, 'search')
        USER_AGG_FLAIRS = urljoin(USER_BASE, 'aggregate_flairs')

        USER_INTERACTIONS = urljoin(USER_BASE, 'interactions')  # sub-base, cannot be used standalone
        USER_INTERACTIONS_USR = urljoin(USER_INTERACTIONS, 'users')
        USER_INTERACTIONS_USR_LIST = urljoin(USER_INTERACTIONS_USR, 'list')
        USER_INTERACTIONS_SUBREDDIT = urljoin(USER_INTERACTIONS, 'subreddits')

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

        common_fields = [
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

        post_fields = [
            'crosspost_parent',
            'link_flair_text',
            'num_comments',
            'over_18',
            'post_hint',
            'selftext',
            'spoiler',
            'title',
            'url'
        ] + common_fields

        comment_fields = [
            'body', 'link_id', 'parent_id'
        ] + common_fields

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

        # ================================================================\

        @staticmethod
        def is_iso8601(s: str) -> bool:
            try:
                datetime.fromisoformat(s)
                return True
            except ValueError:
                return False

        @staticmethod
        def define_param(param_type, assertion=None, required=False, modifications=None, reliance=None):
            return {
                'type': param_type,
                'assert': assertion,
                'required': required,
                'modifications': modifications,
                'reliance': reliance,
            }

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

        # for posts, comments, subreddits, users
        id_search_params = {
            'ids': define_param(list, lambda x: len(x) <= 500, True),
            'md2html': define_param(bool),
            'fields': define_param(list),
        }

        # regular search for posts, comments
        search_common_params = {
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

        post_search_params = {
            **search_common_params,
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
            'fields': define_param(list, lambda x: all([x for x in Params.ArcticShift.post_fields])),
        }

        comment_search_params = {
            **search_common_params,
            # may not be supported for very active users -> give warning prompt
            'body': define_param(str, reliance=lambda params: any([needed in params
                                                                   for needed in
                                                                   ('author', 'subreddit', 'link_id', 'parent_id')])),
            # this is for comments under a post
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
            'fields': define_param(list, lambda x: all([x for x in Params.ArcticShift.post_fields])),
        }

        # aggregation (group by) for comment and posts
        agg_params = {
            
        }

        subreddits_params = {

        }

        # user related params (regular search, interactions and flairs
        users_params = {

        }

        # works for both `/api/users/interactions/users` and `/api/users/interactions/users/list`
        # `/list` lists all the individual interactions rather than aggregating them
        users_interactions_users = {

        }

        users_interactions_subreddits = {

        }

        users_agg_flairs = {

        }
