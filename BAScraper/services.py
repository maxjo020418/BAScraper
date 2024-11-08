import re
from dataclasses import dataclass
from urllib.parse import urljoin


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
        # constants settings
        # rate limit metrics as of Jul 20th 2024
        # `X-RateLimit-Remaining` header needs to be checked!
        MAX_POOL_SOFT = 0
        MAX_POOL_HARD = 0
        REFILL_SECOND = 0

        BASE = 'https://arctic-shift.photon-reddit.com/api'
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


