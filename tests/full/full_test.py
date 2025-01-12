import unittest
from datetime import datetime, timedelta
from BAScraper.BAScraper_async import PullPushAsync
from BAScraper.BAScraper_async_new import PullPushAsync as PullPushAsync_new
import asyncio

ppa = PullPushAsync(log_stream_level="DEBUG")
ppa_new = PullPushAsync_new(log_stream_level="DEBUG")

# print('TEST 1 - basic fetching')
# result1 = asyncio.run(ppa.fetch(mode='submissions',
#                                 subreddit='bluearchive',
#                                 get_comments=True,

#                                 after='2024-07-01',
#                                 before='2024-07-02',
#                                 file_name='result1'))
# print('result1 len:', len(result1))

print('TEST 1 - basic fetching')
result1 = asyncio.run(ppa_new.fetch(mode='submissions',
                                subreddit='bluearchive',
                                get_comments=True,
                                after='2024-07-01',
                                before='2024-07-02',
                                file_name='result1'))
print('result1 len:', len(result1))

# print('\nTEST 2 - basic fetching with comments')
# result2 = asyncio.run(ppa.get_submissions(subreddit='bluearchive',
#                                           after=datetime.timestamp(
#                                               datetime.now() - timedelta(hours=6)),
#                                           file_name='result2', get_comments=True
#                                           ))
# print('result2 len:', len(result2))
#
# print('\nTEST 3 - basic comment fetching')
# result3 = asyncio.run(ppa.get_comments(subreddit='bluearchive',
#                                        after=datetime.timestamp(
#                                            datetime.now() - timedelta(hours=6)),
#                                        file_name='result3'
#                                        ))
# print('result3 len:', len(result3))
