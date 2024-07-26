from datetime import datetime
from BAScraper.BAScraper_async import PullPushAsync
import json
import asyncio

ppa = PullPushAsync(log_stream_level="DEBUG")

print('TEST 1')
result1 = asyncio.run(ppa.get_submissions(subreddit='bluearchive',
                                          after=datetime.timestamp(
                                              datetime(2024, 7, 1)),
                                          before=datetime.timestamp(
                                             datetime(2024, 7, 8)),
                                          file_name='result1'
                                          ))

print('\nTEST 2')
result2 = asyncio.run(ppa.get_submissions(subreddit='bluearchive',
                                          after=datetime.timestamp(
                                              datetime(2024, 7, 1)),
                                          file_name='result2'
                                          ))

print('result1 len:', len(result1))
print('result2 len:', len(result2))
