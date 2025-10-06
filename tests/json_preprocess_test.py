import unittest
from BAScraper_old import utils
import pickle


class TestJSONPreprocessor(unittest.TestCase):
    def setUp(self):
        with open("test_dict.pkl", 'rb+') as f:
            self.res: list = pickle.load(f)
            '''
            test_dupe = list()
            for i in [4, 3, 2]:
                for j in range(i):
                    test_dupe.append((i, j))
            print('test_dupe:', test_dupe)
            for i, j in test_dupe:
                self.res.append({'id': f'dupe-{i}', 'order_test': j})
            '''
            test_dupe = [
                {'id': 'dupe-1', 'order': 1, 'deleted': True},
                {'id': 'dupe-1', 'order': 2, 'deleted': False},

                {'id': 'dupe-2', 'order': 1, 'deleted': False},
                {'id': 'dupe-2', 'order': 2, 'deleted': True},

                {'id': 'dupe-3', 'order': 1, 'deleted': False},
                {'id': 'dupe-3', 'order': 2, 'deleted': False},

                {'id': 'dupe-4', 'order': 1, 'deleted': True},
                {'id': 'dupe-4', 'order': 2, 'deleted': True},

                {'id': 'dupe-5', 'order': 1, 'deleted': False},
                {'id': 'dupe-5', 'order': 2, 'deleted': False},
                {'id': 'dupe-5', 'order': 3, 'deleted': True},
                {'id': 'dupe-5', 'order': 4, 'deleted': False},

                {'id': 'dupe-6', 'order': 1, 'deleted': True},
                {'id': 'dupe-6', 'order': 2, 'deleted': True},
                {'id': 'dupe-6', 'order': 3, 'deleted': True},
                {'id': 'dupe-6', 'order': 4, 'deleted': False},

                {'id': 'dupe-7', 'order': 1, 'deleted': False},
                {'id': 'dupe-7', 'order': 2, 'deleted': True},
                {'id': 'dupe-7', 'order': 3, 'deleted': True},
                {'id': 'dupe-7', 'order': 4, 'deleted': False},

                {'id': 'dupe-8', 'order': 1, 'deleted': False},
                {'id': 'dupe-8', 'order': 2, 'deleted': True},
                {'id': 'dupe-8', 'order': 3, 'deleted': True},
            ]
            self.res.extend(test_dupe)
            self.service = BAScraper_async.PullPushAsync

    def testPreprocess(self):
        action_settings = ['keep_newest', 'keep_oldest', 'remove', 'keep_original', 'keep_removed']
        expected_results = [
            [
                # < keep_newest > used:
                {'id': 'dupe-1', 'order': 2, 'deleted': False},
                {'id': 'dupe-2', 'order': 2, 'deleted': True},
                {'id': 'dupe-3', 'order': 2, 'deleted': False},
                {'id': 'dupe-4', 'order': 2, 'deleted': True},
                {'id': 'dupe-5', 'order': 4, 'deleted': False},
                {'id': 'dupe-6', 'order': 4, 'deleted': False},
                {'id': 'dupe-7', 'order': 4, 'deleted': False},
                {'id': 'dupe-8', 'order': 3, 'deleted': True},
            ],
            [
                # < keep_oldest > used:
                {'id': 'dupe-1', 'order': 1, 'deleted': True},
                {'id': 'dupe-2', 'order': 1, 'deleted': False},
                {'id': 'dupe-3', 'order': 1, 'deleted': False},
                {'id': 'dupe-4', 'order': 1, 'deleted': True},
                {'id': 'dupe-5', 'order': 1, 'deleted': False},
                {'id': 'dupe-6', 'order': 1, 'deleted': True},
                {'id': 'dupe-7', 'order': 1, 'deleted': False},
                {'id': 'dupe-8', 'order': 1, 'deleted': False},
            ],
            [
                # <remove> used:
            ],
            [
                # < keep_original > used:
                {'id': 'dupe-1', 'order': 2, 'deleted': False},
                {'id': 'dupe-2', 'order': 1, 'deleted': False},
                {'id': 'dupe-3', 'order': 2, 'deleted': False},
                {'id': 'dupe-5', 'order': 4, 'deleted': False},
                {'id': 'dupe-6', 'order': 4, 'deleted': False},
                {'id': 'dupe-7', 'order': 4, 'deleted': False},
                {'id': 'dupe-8', 'order': 1, 'deleted': False},
            ],
            [
                # < keep_removed > used:
                {'id': 'dupe-1', 'order': 1, 'deleted': True},
                {'id': 'dupe-2', 'order': 2, 'deleted': True},
                {'id': 'dupe-4', 'order': 2, 'deleted': True},
                {'id': 'dupe-5', 'order': 3, 'deleted': True},
                {'id': 'dupe-6', 'order': 3, 'deleted': True},
                {'id': 'dupe-7', 'order': 3, 'deleted': True},
                {'id': 'dupe-8', 'order': 3, 'deleted': True},
            ],
        ]
        for duplicate_action, expected_result in zip(action_settings, expected_results):
            print(f'<{duplicate_action}> used:')
            service = self.service(duplicate_action=duplicate_action, log_level='DEBUG')
            res = utils.preprocess_json(service, self.res)
            dupes_processed = [v for k, v in res.items() if k.startswith('dupe')]
            [print(v) for v in dupes_processed]

            self.assertEqual(dupes_processed, expected_result)


if __name__ == '__main__':
    unittest.main()
