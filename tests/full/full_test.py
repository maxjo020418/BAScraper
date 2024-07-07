from datetime import datetime
from BAScraper.BAScraper_async import PullPushAsync
import json
import asyncio

ppa = PullPushAsync(log_stream_level="DEBUG")
result = asyncio.run(ppa.get_submissions(subreddit='bluearchive',
                                         after=datetime.timestamp(
                                             datetime(2024, 7, 1)),
                                         before=datetime.timestamp(
                                             datetime(2024, 7, 7)),
                                         ))

with open('test.json', 'w') as f:
    json.dump(result, f, indent=4)
