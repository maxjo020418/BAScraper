from BAScraper.BAScraper_async import PullPushAsync, ArcticShiftAsync
import asyncio

ppa = PullPushAsync(log_stream_level="DEBUG")
asa = ArcticShiftAsync(log_stream_level="DEBUG")


if input('test ppa?: ') == 'y':
    print('TEST 1-1 - PullPushAsync basic fetching')
    result1 = asyncio.run(ppa.fetch(mode='submissions',
                                    subreddit='bluearchive',
                                    get_comments=True,
                                    after='2024-07-01',
                                    before='2024-07-01T12:00:00',
                                    file_name='test1'))
    print('test 1 len:', len(result1))

    print('\nTEST 1-2 - PullPushAsync basic comment fetching')
    result2 = asyncio.run(ppa.fetch(mode='comments',
                                    subreddit='bluearchive',
                                    # get_comments=True,
                                    after='2024-07-01',
                                    before='2024-07-01T12:00:00',
                                    file_name='test2'))
    print('test 2 len:', len(result2))


if input('test asa?: ') == 'y':
    print('TEST 2-1 - ArcticShiftAsync basic fetching')
    result1 = asyncio.run(asa.fetch(mode='submissions_search',
                                    subreddit='bluearchive',
                                    get_comments=True,
                                    after='2024-07-01',
                                    before='2024-07-01T03:00:00',
                                    file_name='test1',
                                    limit=100))
    print('test 1 len:', len(result1))

    print('\nTEST 2-2 - ArcticShiftAsync basic comment fetching')
    result2 = asyncio.run(asa.fetch(mode='comments_search',
                                    subreddit='bluearchive',
                                    # get_comments=True,
                                    after='2024-07-01',
                                    before='2024-07-01T12:00:00',
                                    file_name='test2',
                                    limit=100))
    print('test 2 len:', len(result2))