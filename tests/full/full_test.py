import unittest
from datetime import datetime, timedelta
from BAScraper.BAScraper_async import PullPushAsync
import asyncio

ppa = PullPushAsync(log_stream_level="DEBUG")

print('TEST 1 - basic fetching')
result1 = asyncio.run(ppa.get_submissions(subreddit='bluearchive',
                                          after=datetime.timestamp(
                                              datetime(2024, 7, 1)),
                                          before=datetime.timestamp(
                                             datetime(2024, 7, 8)),
                                          file_name='result1'
                                          ))
print('result1 len:', len(result1))

print('\nTEST 2 - basic fetching with comments')
result2 = asyncio.run(ppa.get_submissions(subreddit='bluearchive',
                                          after=datetime.timestamp(
                                              datetime.now() - timedelta(hours=6)),
                                          file_name='result2', get_comments=True
                                          ))
print('result2 len:', len(result2))

print('\nTEST 3 - basic comment fetching')
result3 = asyncio.run(ppa.get_comments(subreddit='bluearchive',
                                       after=datetime.timestamp(
                                           datetime.now() - timedelta(hours=6)),
                                       file_name='result3'
                                       ))
print('result3 len:', len(result3))
