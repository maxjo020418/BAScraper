# BAScraper

### Table of Contents
1. [Introduction](#bascraper)
2. [Features](#features)
3. [Installation and Basic Usage](#installation-and-basic-usage)
   - [Usage Example](#usage-example)
4. [Parameters](#parameters)
   - [Initialization Parameters](#initialization-parameters)
   - [Fetch Parameters](#fetch-parameters-fetch)
     - [PullPushAsync Fetch Parameters](#pullpushasyncfetch-common-parameters)
       - [Common Parameters](#pullpushasyncfetch-common-parameters)
       - [Mode-Specific Parameters](#parameters-by-mode-for-pullpushasyncfetch)
     - [ArcticShiftAsync Fetch Parameters](#arcticshiftasyncfetch-common-parameters)
       - [Common Parameters](#arcticshiftasyncfetch-common-parameters)
       - [Mode-Specific Parameters](#parameters-by-mode-for-arcticshiftasyncfetch)
5. [Rate Limits and Performance](#rate-limits-and-performance)
   - [PullPush.io](#pullpushio)
   - [Arctic-Shift](#arctic-shift)
6. [Returned JSON Object Structure](#returned-json-object-structure)

---

> [!WARNING]
> Usage (Classes and Functions) method has drastically changed and also the following README doc.
> The old docs are in `./BAScraper_old/README_old.md`.
> 
> This new v0.2.x-a is only tested to the extent that I personally use, so full coverage testing has not been done.
> It also hasn't been published to PyPi (PyPi on v0.1.2), manually download for the newest v0.2-a
> please report unexpected issues that may occur.

An API wrapper for PullPush.io and Arctic-Shift - the 3rd party replacement APIs for Reddit. Nothing special.

After the [2023 Reddit API controversy](https://en.wikipedia.org/wiki/2023_Reddit_API_controversy), 
PushShift.io(and also wrappers such as PSAW and PMAW) is now only available to reddit admins and Reddit PRAW is 
honestly useless when trying to get a lots of data and data from a specific timeframe.
This aims to help with that since these 3rd party services didn't have any official/unofficial python wrappers.

### Features
- Asynchronous operations for better performance. (updated from the old multithreaded approach)
- Support for PullPush.io and Arctic Shift APIs.
- Parameter customization for subreddit, comment, and submission searches.
- Integrated rate-limit management.
- Parameter schemes for data selection.

Also, please respect cool-down times and refrain from requesting very large amount of data. 
It stresses the server and can cause inconvenience for everyone.

For large amounts of data, head to [ArcticShift's academic torrent zst dumps](https://github.com/ArthurHeitmann/arctic_shift)

**Links to the services:**
- [PullPush.io](https://pullpush.io/)
- [Arctic-Shift](https://arctic-shift.photon-reddit.com/)

## Installation and basic usage
you can install the package via pip
```bash
pip install BAScraper
```
Python 3.11+ is **required** (`asyncio.TaskGroup` is used)

### Usage Example
```python
from BAScraper.BAScraper_async import PullPushAsync, ArcticShiftAsync
import asyncio

ppa = PullPushAsync(log_stream_level="DEBUG", task_num=2)
asa = ArcticShiftAsync(log_stream_level="DEBUG", task_num=10)


async def test1():
    print('TEST 1-1 - PullPushAsync basic fetching')
    result1 = await ppa.fetch(
        mode='submissions',
        subreddit='cars',
        get_comments=True,
        after='2024-07-01',
        before='2024-07-01T06:00:00',
        file_name='test1-1'
    )
    print('test 1 len:', len(result1))

    print('\nTEST 1-2 - PullPushAsync basic comment fetching')
    result2 = await ppa.fetch(
        mode='comments',
        subreddit='cars',
        after='2024-07-01',
        before='2024-07-01T06:00:00',
        file_name='test1-2'
    )
    print('test 2 len:', len(result2))


async def test2():
    print('TEST 2-1 - ArcticShiftAsync basic fetching')
    result1 = await asa.fetch(
        mode='submissions_search',
        subreddit='cars',
        # get_comments=True,  # can be uncommented to the comment
        after='2024-07-01',
        before='2024-07-05T03:00:00',
        file_name='test2-1',
        fields=['created_utc', 'title', 'url', 'id'],
        limit=0  # auto
    )
    print('test 1 len:', len(result1))

    print('\nTEST 2-2 - ArcticShiftAsync basic comment fetching')
    result2 = await asa.fetch(
        mode='comments_search',
        subreddit='cars',
        body='bmw honda benz',
        after='2024-07-01',
        before='2024-07-01T12:00:00',
        file_name='test2-2',
        limit=100,
        fields=['created_utc', 'body', 'id'],
    )
    print('test 2 len:', len(result2))

    print('\nTEST 2-3 - ArcticShiftAsync subreddits_search')
    result3 = await asa.fetch(
        mode='subreddits_search',
        subreddit_prefix='what',
        file_name='test2-3',
        limit=1000
    )
    print('test 3 len:', len(result3))

if __name__ == '__main__':
    if input('test pullpush?: ') == 'y':
        asyncio.run(test1())
    if input('test arcticshift?: ') == 'y':
        asyncio.run(test2())

# all results are saved to 'resultX.json' since the `file_name` field was specified. 
# it'll save all the results in the current directory since `save_dir` wasn't specified
```

> [!NOTE]
> When using multiple requests, (as in multiple functions under `PullPushAsync`)
> it is highly recommended to use all the functions under the same class 
> because all the request pool related variables would be shared in that case.
> 
> Also, when re-running scripts using this, pools recording the request status is reset every time. 
> So keep in mind that unexpected soft/hard rate limits may occur when frequently (re-)running scripts.
> Consider waiting a few minutes or seconds before running scripts if needed.

## Parameters
For more info on each of the parameters as well as additional info (TOS, extra tools, etc) visit the following links:
- [PullPush.io](https://pullpush.io/)
- [Arctic-Shift](https://arctic-shift.photon-reddit.com/)
### Initialization Parameters
**for `PullPushAsync.__init__` & `ArcticShiftAsync.__init__`**

| Parameter          | Type  | Restrictions                                                                             | Required | Default Value                     | Notes                                                     |
|--------------------|-------|------------------------------------------------------------------------------------------|----------|-----------------------------------|-----------------------------------------------------------|
| `sleep_sec`        | `int` | Positive int                                                                             | No       | `1`                               | Cooldown time between each request.                       |
| `backoff_sec`      | `int` | Positive int                                                                             | No       | `3`                               | Backoff time for each failed request.                     |
| `max_retries`      | `int` | Positive int                                                                             | No       | `5`                               | Number of retries for failed requests before it gives up. |
| `timeout`          | `int` | Positive int                                                                             | No       | `10`                              | Time until it's considered as timeout error.              |
| `pace_mode`        | `str` | One of `'auto-soft'`, `'auto-hard'`, `'manual'`                                          | No       | `'auto-hard'`                     | Sets the pace to mitigate rate-limiting.                  |
| `save_dir`         | `str` | Valid path                                                                               | No       | `os.getcwd()` (current directory) | Directory to save the results.                            |
| `task_num`         | `int` | Positive int                                                                             | No       | `3`                               | Number of async tasks to be made.                         |
| `log_stream_level` | `str` | One of `['NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']`                     | No       | `'INFO'`                          | Sets the log level for logs streamed on the terminal.     |
| `log_level`        | `str` | Same as `log_stream_level`                                                               | No       | `'DEBUG'`                         | Sets the log level for logging (file).                    |
| `duplicate_action` | `str` | One of `'keep_newest'`, `'keep_oldest'`, `'remove'`, `'keep_original'`, `'keep_removed'` | No       | `'keep_newest'`                   | Decides handling of duplicates.                           |

### Fetch Parameters (`fetch`)

#### `PullPushAsync.fetch` common parameters
| Parameter   | Type   | Restrictions                                                | Required | Notes                                     |
|-------------|--------|-------------------------------------------------------------|----------|-------------------------------------------|
| `q`         | `str`  | Quoted string for phrases                                   | No       | Search query for comments or submissions. |
| `ids`       | `list` | Maximum length: 100                                         | No       | List of IDs to fetch.                     |
| `size`      | `int`  | Must be <= 100                                              | No       | Number of results to return.              |
| `sort`      | `str`  | Must be one of `"asc"`, `"desc"`                            | No       | Sorting order.                            |
| `sort_type` | `str`  | Must be one of `"score"`, `"num_comments"`, `"created_utc"` | No       | Sorting criteria.                         |
| `author`    | `str`  | None                                                        | No       | Filter by author.                         |
| `subreddit` | `str`  | None                                                        | No       | Filter by subreddit.                      |
| `after`     | `str`  | Must be in ISO8601 format, converted to epoch               | No       | Include results after this date.          |
| `before`    | `str`  | Must be in ISO8601 format, converted to epoch               | No       | Include results before this date.         |


##### Parameters by `mode` for `PullPushAsync.fetch`
- **`'comments'`**:

    | Parameter | Type  | Restrictions | Required | Notes                                 |
    |-----------|-------|--------------|----------|---------------------------------------|
    | `link_id` | `str` | None         | No       | Fetch comments under a specific post. |

- **`'submissions'`**:

    | Parameter      | Type   | Restrictions                                    | Required | Notes                                          |
    |----------------|--------|-------------------------------------------------|----------|------------------------------------------------|
    | `title`        | `str`  | None                                            | No       | Search query for titles.                       |
    | `selftext`     | `str`  | None                                            | No       | Search query for selftext fields.              |
    | `score`        | `str`  | Must satisfy a comparison operation (`>, <, =`) | No       | Filter by score.                               |
    | `num_comments` | `str`  | Must satisfy a comparison operation (`>, <, =`) | No       | Filter by number of comments.                  |
    | `over_18`      | `bool` | `True` or `False`                               | No       | Include or exclude NSFW content.               |
    | `is_video`     | `bool` | `True` or `False`                               | No       | Include or exclude video submissions.          |
    | `locked`       | `bool` | `True` or `False`                               | No       | Include or exclude locked submissions.         |
    | `stickied`     | `bool` | `True` or `False`                               | No       | Include or exclude stickied submissions.       |
    | `spoiler`      | `bool` | `True` or `False`                               | No       | Include or exclude spoiler-tagged submissions. |
    | `contest_mode` | `bool` | `True` or `False`                               | No       | Include or exclude contest-mode submissions.   |

#### `ArcticShiftAsync.fetch` common parameters
| Parameter      | Type   | Restrictions                  | Required | Notes                                                                                                    |
|----------------|--------|-------------------------------|----------|----------------------------------------------------------------------------------------------------------|
| `mode`         | `str`  | Varies based on endpoint      | Yes      | Specifies the type of data to fetch. Options include `submissions_id_lookup`, `comments_id_lookup`, etc. |
| `get_comments` | `bool` | `True` or `False`             | No       | If `True`, fetch comments associated with submissions.                                                   |
| `file_name`    | `str`  | Valid filename or `None`      | No       | Saves the results to a specified file.                                                                   |
| `**params`     | `dict` | See mode-specific parameters. | Yes      | Additional parameters dependent on the `mode`.                                                           |

##### Parameters by `mode` for `ArcticShiftAsync.fetch`

1. **ID Lookup**
   - Modes: `submissions_id_lookup`, `comments_id_lookup`, `subreddits_id_lookup`, `users_id_lookup`.
   - Parameters:

        | Parameter | Type   | Restrictions                 | Required | Notes                                  |
        |-----------|--------|------------------------------|----------|----------------------------------------|
        | `ids`     | `list` | Maximum length: 500          | Yes      | List of IDs to fetch.                  |
        | `md2html` | `bool` | `True` or `False`            | No       | If `True`, converts markdown to HTML.  |
        | `fields`  | `list` | Valid field names for entity | No       | Specific fields to include in results. |

2. **Search**
   - Modes: `submissions_search`, `comments_search`.

     - **Common Parameters**

       | Parameter           | Type   | Restrictions                | Required | Notes                                                                              |
       |---------------------|--------|-----------------------------|----------|------------------------------------------------------------------------------------|
       | `author`            | `str`  | None                        | No       | Filter results by author.                                                          |
       | `subreddit`         | `str`  | None                        | No       | Filter results by subreddit.                                                       |
       | `author_flair_text` | `str`  | None                        | No       | Filter by author's flair text.                                                     |
       | `after`             | `str`  | ISO8601                     | No       | Include results after this date.                                                   |
       | `before`            | `str`  | ISO8601                     | No       | Include results before this date.                                                  |
       | `limit`             | `int`  | 0 <= x <= 100; `0` -> auto  | No       | Number of results per request; `0` automatically adjusts based on server capacity. |
       | `sort`              | `str`  | Must be `'asc'` or `'desc'` | No       | Order results by the specified criteria.                                           |
       | `md2html`           | `bool` | `True` or `False`           | No       | If `True`, converts markdown to HTML.                                              |

     - **Submissions**

       | Parameter   | Type  | Restrictions        | Required | Notes                              |
       |-------------|-------|---------------------|----------|------------------------------------|
       | `author`    | `str` | None                | No       | Filter by author.                  |
       | `subreddit` | `str` | None                | No       | Filter by subreddit.               |
       | `query`     | `str` | None                | No       | Search query (title and selftext). |
       | `limit`     | `int` | 1-100               | No       | Number of results per request.     |
       | `sort`      | `str` | `'asc'` or `'desc'` | No       | Sorting order.                     |

     - **Comments**

       | Parameter | Type  | Restrictions | Required | Notes                                 |
       |-----------|-------|--------------|----------|---------------------------------------|
       | `body`    | `str` | None         | No       | Filter by comment body text.          |
       | `link_id` | `str` | None         | No       | Fetch comments under a specific post. |
       | `author`  | `str` | None         | No       | Filter by comment author.             |

   - **`subreddits_search`**

        | Parameter          | Type   | Restrictions                                                   | Required | Notes                                          |
        |--------------------|--------|----------------------------------------------------------------|----------|------------------------------------------------|
        | `subreddit`        | `str`  | None                                                           | No       | Filter results by a specific subreddit.        |
        | `subreddit_prefix` | `str`  | None                                                           | No       | Search for subreddits starting with a prefix.  |
        | `after`            | `str`  | Must be in ISO8601 format                                      | No       | Include results after this date.               |
        | `before`           | `str`  | Must be in ISO8601 format                                      | No       | Include results before this date.              |
        | `min_subscribers`  | `int`  | Must be >= 0                                                   | No       | Minimum number of subscribers.                 |
        | `max_subscribers`  | `int`  | Must be >= 0                                                   | No       | Maximum number of subscribers.                 |
        | `over18`           | `bool` | `True` or `False`                                              | No       | Include or exclude NSFW subreddits.            |
        | `limit`            | `int`  | 1 <= x <= 1000                                                 | No       | Limit the number of results returned.          |
        | `sort`             | `str`  | Must be `'asc'` or `'desc'`                                    | No       | Sort results in ascending or descending order. |
        | `sort_type`        | `str`  | Must be one of `'created_utc'`, `'subscribers'`, `'subreddit'` | No       | Sorting criteria.                              |

   - **`users_search`**

		| Parameter          | Type  | Restrictions                               | Required | Notes                                          |
		|--------------------|-------|--------------------------------------------|----------|------------------------------------------------|
		| `author`           | `str` | None                                       | No       | Filter results by a specific user.             |
		| `author_prefix`    | `str` | None                                       | No       | Search for users starting with a prefix.       |
		| `min_num_posts`    | `int` | Must be >= 0                               | No       | Minimum number of posts by the user.           |
		| `min_num_comments` | `int` | Must be >= 0                               | No       | Minimum number of comments by the user.        |
		| `active_since`     | `str` | Must be in ISO8601 format                  | No       | Include users active since this date.          |
		| `min_karma`        | `int` | Must be >= 0                               | No       | Minimum karma required for users.              |
		| `limit`            | `int` | 1 <= x <= 1000                             | No       | Limit the number of results returned.          |
		| `sort`             | `str` | Must be `'asc'` or `'desc'`                | No       | Sort results in ascending or descending order. |
		| `sort_type`        | `str` | Must be one of `'author'`, `'total_karma'` | No       | Sorting criteria for users.                    |

   - **`comments_tree_search`**

        | Parameter       | Type   | Restrictions                      | Required | Notes                                                |
        |-----------------|--------|-----------------------------------|----------|------------------------------------------------------|
        | `link_id`       | `str`  | None                              | Yes      | Fetch comments under the specified post ID.          |
        | `parent_id`     | `str`  | None                              | No       | Fetch replies under a specific parent comment.       |
        | `limit`         | `int`  | Must be >= 1                      | No       | Maximum number of comments to return.                |
        | `start_breadth` | `int`  | Must be >= 0                      | No       | Threshold for collapsing comments based on breadth.  |
        | `start_depth`   | `int`  | Must be >= 0                      | No       | Threshold for collapsing comments based on depth.    |
        | `md2html`       | `bool` | `True` or `False`                 | No       | If `True`, converts markdown to HTML in the results. |
        | `fields`        | `list` | Valid field names for submissions | No       | Include specific fields in the returned data.        |

3. **Aggregations**
   - Modes: `submissions_aggregation`, `comments_aggregation`.
     - **Common Parameters**

		| Parameter   | Type  | Restrictions                                              | Required | Notes                                                                                      |
		|-------------|-------|-----------------------------------------------------------|----------|--------------------------------------------------------------------------------------------|
		| `aggregate` | `str` | Must be one of `'created_utc'`, `'author'`, `'subreddit'` | Yes      | Specifies the field to group by.                                                           |
		| `frequency` | `str` | None                                                      | No       | Required only when `aggregate` is `'created_utc'`. Defines time intervals for aggregation. |
		| `limit`     | `int` | Must be >= 1                                              | No       | Limits the number of grouped results returned.                                             |
		| `min_count` | `int` | Must be >= 0                                              | No       | Minimum number of entries in a group; not applicable when `aggregate` is `'created_utc'`.  |
		| `sort`      | `str` | Must be `'asc'` or `'desc'`                               | No       | Sorts the aggregation results.                                                             |

     - **Submissions**

		| Parameter             | Type   | Restrictions                      | Required | Notes                                            |
		|-----------------------|--------|-----------------------------------|----------|--------------------------------------------------|
		| `crosspost_parent_id` | `str`  | None                              | No       | Filters by crosspost parent ID.                  |
		| `over_18`             | `bool` | `True` or `False`                 | No       | Includes or excludes NSFW content.               |
		| `spoiler`             | `bool` | `True` or `False`                 | No       | Includes or excludes spoiler-tagged submissions. |
		| `title`               | `str`  | None                              | No       | Filters by title.                                |
		| `selftext`            | `str`  | None                              | No       | Filters by selftext field.                       |
		| `link_flair_text`     | `str`  | None                              | No       | Filters by link flair text.                      |
		| `query`               | `str`  | None                              | No       | Searches across title and selftext.              |
		| `url`                 | `str`  | None                              | No       | Filters by URL prefix (e.g., YouTube).           |
		| `url_exact`           | `bool` | `True` or `False`                 | No       | If `True`, requires exact URL match.             |
		| `fields`              | `list` | Valid field names for submissions | No       | Filters the fields included in results.          |

     - **Comments**

		| Parameter   | Type   | Restrictions                      | Required | Notes                                   |
		|-------------|--------|-----------------------------------|----------|-----------------------------------------|
		| `body`      | `str`  | None                              | No       | Filters by comment body text.           |
		| `link_id`   | `str`  | None                              | No       | Filters by submission ID.               |
		| `parent_id` | `str`  | None                              | No       | Filters by parent comment ID.           |
		| `fields`    | `list` | Valid field names for comments    | No       | Filters the fields included in results. |

   - **`user_flairs_aggregation`**

      | Parameter | Type  | Restrictions | Required | Notes                                                              |
      |-----------|-------|--------------|----------|--------------------------------------------------------------------|
      | `author`  | `str` | None         | Yes      | Specifies the user for whom to aggregate flairs across subreddits. |

4. **Interactions**
   - **`user_interactions`, `list_users_interactions`**

		| Parameter   | Type  | Restrictions | Required | Notes                                                 |
		|-------------|-------|--------------|----------|-------------------------------------------------------|
		| `author`    | `str` | None         | Yes      | Specifies the user for whom interactions are queried. |
		| `subreddit` | `str` | None         | No       | Filter interactions by a specific subreddit.          |
		| `after`     | `str` | ISO8601      | No       | Include interactions after this date.                 |
		| `before`    | `str` | ISO8601      | No       | Include interactions before this date.                |
		| `min_count` | `int` | Must be >= 0 | No       | Minimum number of interactions to include.            |
		| `limit`     | `int` | Must be >= 1 | No       | Maximum number of results to return.                  |

   - **`subreddits_interactions`**

		| Parameter         | Type    | Restrictions | Required | Notes                                                    |
		|-------------------|---------|--------------|----------|----------------------------------------------------------|
		| `author`          | `str`   | None         | Yes      | Specifies the user for whom interactions are queried.    |
		| `weight_posts`    | `float` | Must be >= 0 | No       | Weight assigned to posts in interaction calculations.    |
		| `weight_comments` | `float` | Must be >= 0 | No       | Weight assigned to comments in interaction calculations. |
		| `before`          | `str`   | ISO8601      | No       | Include interactions before this date.                   |
		| `after`           | `str`   | ISO8601      | No       | Include interactions after this date.                    |
		| `min_count`       | `int`   | Must be >= 0 | No       | Minimum number of interactions to include.               |
		| `limit`           | `int`   | Must be >= 1 | No       | Maximum number of results to return.                     |

## Rate Limits and Performance
_both services are free and don't have any SLO or SLA "as good as it is now"_

### PullPush.io

PullPush API implemented ratelimiting as of Feb. 2024.

soft limit will occur after 15 req/min and hard limit after 30 req/min. There's also a long-term (hard) limit of 1000 req/hr.

Recommended request pacing:
- to prevent soft-limit: 4 sec sleep per request
- to prevent hard-limit: 2 sec sleep per request
- for 1000+ requests: 3.6 ~ 4 sec sleep per request

due to lowered performance recently, using a single worker(`task_num`) is recommended unless it's for a short burst.

rate limiting will automatically pace your request's response time to meet the following hard limits.
But `pace_mode` would still do throttling just in case. Following the pacing time above is recommended.

> [!WARNING]
> The long-term hard ratelimit of 1000 req/hr is not implemented in the auto throttling.
> You should manually set sleep second using the `sleepsec` param for  `PullPushAsync.__init__` to 3.6 ~ 4 sec as mentioned above

### Arctic-Shift

Dynamically returns `x-ratelimit` related headers in the response data.
BAScraper will read this and throttle if needed.

As of writing it has better performance and ratelimit rates compared to PullPush 
- hard limit is usually 2000 requests per 1 minute, though it may vary. 
- If `auto` is used for the `limit` it may return more than 100 results per requests (though that would also vary)
- up to 10 ~ 20 workers(ex: `task_num=10`) still seem to hold up well 
- response time usually around a second with complex large queries over 5 seconds

## Returned JSON object structure
the `fetch` function each returns a `dict` object that is indexed based on its unique reddit submission/comment/user/subreddit ID.
It is sorted in the order you specified when scraping
(the `sort` parameter).
So the general structure looks like this (regardless of it being a submission or a comment):
```json
{
  "21jh54" : {
    "approved_at_utc": null,
    "subreddit": "Cars",
    "selftext": "",
    "author_fullname": "t2_culcgvve",
    "saved": false,
    "mod_reason_title": null,
    "gilded": 0,
    "clicked": false,
    "title": "something something",
    ...
  },
  "54jp5i" : {
    "approved_at_utc": null,
    "subreddit": "Cars",
    "selftext": "",
    "author_fullname": "t2_kdbbiwo",
    "saved": false,
    "mod_reason_title": null,
    "gilded": 0,
    "clicked": false,
    "title": "something something",
    ...
  }, 
  ...
}
```

if the `get_comments` parameter is set to `True` the returned result would look like this (for submissions)

```json
{
  "21jh54": {
    "approved_at_utc": null,
    "subreddit": "Cars",
    "selftext": "",
    "author_fullname": "t2_culcgvve",
    "saved": false,
    "mod_reason_title": null,
    "gilded": 0,
    "clicked": false,
    "title": "something something",
    "comments": [
      {
        ...
        info related to comments
        ...      
      },
      ...
    ],
    ...
  },
  ...
}
```
