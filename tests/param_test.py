import unittest
from BAScraper import utils


class TestProcessParams(unittest.TestCase):
    def setUp(self):
        self.parser = utils
        self.params = utils.Params

    def test_valid_comment_params(self):
        params = {
            'q': 'example',
            'size': 50,
            'sort': 'asc',
            'sort_type': 'score',
            'author': 'test_author',
            'subreddit': 'test_subreddit',
            'after': '2021-03-31T19:40:00+09:00',
            'before': '2021-04-01T19:40:00+09:00',
            'link_id': 'abc123'
        }
        expected_uri = "https://api.pullpush.io/reddit/search/comment/?q=example&size=50&sort=asc&sort_type=score&author=test_author&subreddit=test_subreddit&after=1617187200&before=1617273600&link_id=abc123"
        result = self.parser.param_processor(self.params.PullPush(), 'comments', **params)
        self.assertEqual(expected_uri, result)

    def test_valid_submission_params(self):
        params = {
            'ids': ['abc123', 'def456'],
            'q': 'example',
            'title': 'test_title',
            'selftext': 'test_selftext',
            'size': 50,
            'sort': 'asc',
            'sort_type': 'score',
            'author': 'test_author',
            'subreddit': 'test_subreddit',
            'after': '2021-03-31T19:40:00+09:00',
            'before': '2021-04-01T19:40:00+09:00',
            'score': '<100',
            'num_comments': '>10',
            'over_18': True,
            'is_video': False,
            'locked': False,
            'stickied': True,
            'spoiler': False,
            'contest_mode': True
        }
        expected_uri = "https://api.pullpush.io/reddit/search/submission/?ids=abc123,def456&q=example&title=test_title&selftext=test_selftext&size=50&sort=asc&sort_type=score&author=test_author&subreddit=test_subreddit&after=1617187200&before=1617273600&score=<100&num_comments=>10&over_18=true&is_video=false&locked=false&stickied=true&spoiler=false&contest_mode=true"
        result = self.parser.param_processor(self.params.PullPush(), 'submissions', **params)
        self.assertEqual(expected_uri, result)

    def test_invalid_param_name(self):
        params = {
            'invalid_param': 'example'
        }
        with self.assertRaises(Exception) as context:
            self.parser.param_processor(self.params.PullPush(), 'comments', **params)
            self.assertTrue('is not accepted as a parameter' in str(context.exception))

    def test_invalid_param_type(self):
        params = {
            'q': 123  # should be a string
        }
        with self.assertRaises(AssertionError) as context:
            self.parser.param_processor(self.params.PullPush(), 'comments', **params)
            self.assertTrue('should be <class \'str\'>' in str(context.exception))

    def test_invalid_param_value(self):
        params = {
            'sort': 'invalid_sort'  # should be either 'asc' or 'desc'
        }
        with self.assertRaises(AssertionError) as context:
            self.parser.param_processor(self.params.PullPush(), 'comments', **params)
            self.assertTrue("doesn't meet or satisfy the requirements" in str(context.exception))


if __name__ == '__main__':
    unittest.main()
