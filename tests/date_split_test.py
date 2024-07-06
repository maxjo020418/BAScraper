import unittest
from datetime import datetime, timedelta
from BAScraper import utils


def datetime_to_epoch(dt):
    return int(dt.timestamp())


def epoch_to_datetime(epoch):
    return datetime.fromtimestamp(epoch)


class TestSplitRange(unittest.TestCase):

    def test_split_range_dates(self):
        # Define the date range
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 12)

        # Convert dates to epoch
        low = datetime_to_epoch(start_date)
        high = datetime_to_epoch(end_date)

        # Split the range into 3 parts
        n = 3
        result = utils.split_range(low, high, n)

        # Convert epoch ranges back to datetime and print them
        date_ranges = [[epoch_to_datetime(r[0]), epoch_to_datetime(r[1])] for r in result]

        # Expected ranges (approximately, as epochs are seconds and dates are days)
        expected_ranges = [
            [datetime(2023, 1, 1), datetime(2023, 1, 4, 23, 59, 59)],
            [datetime(2023, 1, 5), datetime(2023, 1, 8, 23, 59, 59)],
            [datetime(2023, 1, 9), datetime(2023, 1, 12, 23, 59, 59)],
        ]

        print(f'{start_date} ~ {end_date} : {n} split')
        [print(date_range, '\t', date_range[1] - date_range[0]) for date_range in date_ranges]
        print(result)

        # Validate the results
        a = date_ranges[0][1] - date_ranges[0][0]
        b = date_ranges[1][1] - date_ranges[1][0]
        c = date_ranges[2][1] - date_ranges[2][0]
        self.assertAlmostEqual(a, b, delta=timedelta(seconds=2))
        self.assertAlmostEqual(b, c, delta=timedelta(seconds=2))
        self.assertAlmostEqual(c, a, delta=timedelta(seconds=2))

        '''
        for i in range(n):
            self.assertAlmostEqual(date_ranges[i][0], expected_ranges[i][0], delta=timedelta(seconds=2))
            self.assertAlmostEqual(date_ranges[i][1], expected_ranges[i][1], delta=timedelta(seconds=2))
        '''


if __name__ == "__main__":
    unittest.main()
