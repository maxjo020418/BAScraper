BAScraper
=========
A little (~~multithreaded~~ asynchronous) API wrapper for [PullPush.io](https://www.pullpush.io/) - the 3rd party replacement API for Reddit. 
After the [2023 Reddit API controversy](https://en.wikipedia.org/wiki/2023_Reddit_API_controversy), 
PushShift.io(and also wrappers such as PSAW and PMAW) is now only available to reddit admins and Reddit PRAW is 
honestly useless when trying to get a lots of data and data from a specific timeframe.
PullPush.io thankfully solves this issue and this is the wrapper for that said API. For more info on the 
API(TOS, Forum, Docs, etc.) go to [PullPush.io](https://www.pullpush.io/).

BAScraper(Blue Archive Scraper) was initially made and used for the 2023 recap/wrap up of that sub, hence the name.
It's pretty basic but planning to add some more features as it goes.
It uses multithreading to make requests to the PullPush.io endpoint and returns the result as a JSON(dict) object.

**currently it can:**
- get submissions/comments from a certain subreddit in supported order/sorting methods specified in the PullPush.io API docs
- get comments under the retrieved submissions
- can get all the submissions based on the number of submissions or in a certain timeframe you specify
- can recover(if possible) deleted/removed submission/comments from the returned result

Also, please ask the PullPush.io owner before making large amounts or request and also respect cool-down times. 
It stresses the server and can cause inconvenience for everyone.

> [!WARNING] As of Feb. 2024, PullPush API implemented ratelimiting!
> soft limit will occur after 15 req/min and hard limit after 30 req/min. There's also a long-term (hard) limit of 1000 req/hr.<br><br>
> **Recommended request pacing:**
> - to prevent soft-limit: 4 sec sleep per request
> - to prevent hard-limit: 2 sec sleep per request
> - for 1000+ requests: 3.6 ~ 4 sec sleep per request
> 
> rate limiting will automatically pace your reqeust's response time to meet the following hard limits. Hence making the `pace_mode` parameter kinda useless (it was made before proper API sice pacing was made). Following the pacing time above is recommended.

## basic usage & requirements
you can install the package via pip
```shell
pip install BAScraper
```
Also, python 3.11+ is **needed** (`asyncio.TaskGroup` is used)

**Example usage**
```python
from datetime import datetime, timedelta
from BAScraper.BAScraper_async import PullPushAsync
import asyncio

# `log_stream_level` can be one of DEBUG, INFO, WARNING, ERROR, CRITICAL
ppa = PullPushAsync(log_stream_level="INFO")

# basic fetching
result1 = asyncio.run(ppa.get_submissions(subreddit='bluearchive',
                                          after=datetime.timestamp(
                                              datetime(2024, 7, 1)),
                                          before=datetime.timestamp(
                                             datetime(2024, 7, 8)),
                                          file_name='result1'
                                          ))

# basic fetching with comments
result2 = asyncio.run(ppa.get_submissions(subreddit='bluearchive',
                                          after=datetime.timestamp(
                                              datetime.now() - timedelta(hours=6)),
                                          file_name='result2', get_comments=True
                                          ))

# basic comment fetching
result3 = asyncio.run(ppa.get_comments(subreddit='bluearchive',
                                       after=datetime.timestamp(
                                           datetime.now() - timedelta(hours=6)),
                                       file_name='result3'
                                       ))

# all files are auto-saved since the `file_name` field was specified. 
# it'll save all the results in the current directory
```

<details>
  <summary>Legacy multithreaded method (Click)</summary>
  
  **NOTE: Stupid mistake I made before was the typo of writing `Pullpush` as `Pushpull`**
  **I won't fix it for now since it might break stuff for ppl, but I named it properly for the new async stuffs**

  ### Legacy method `Pushpull` usage example
  ```python 
  from BAScraper.BAScraper import Pushpull
  import json
  from datetime import datetime

  pp = Pushpull(sleepsec=2, threads=2)
  result = pp.get_submissions(after=datetime(2023, 12, 1), before=datetime(2024, 1, 1),
                              subreddit='bluearchive', sort='desc')

  # save result as JSON
  with open("example.json", "w", encoding='utf-8') as outfile:
      json.dump(result, outfile, indent=4)
  ```
  parameters are mostly the same, I put it in the [Pushpull_params_old.md](/Pushpull_params_old.md) just in case
</details>

# Parameters
## `PullPushAsync.__init__`
all parameters are optional

| parameter        | type  | description                                                                                                                                            | default value                     |
|------------------|-------|--------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------|
| sleepsec         | `int` | cooldown time between each request                                                                                                                     | 1                                 |
| backoffsec       | `int` | backoff time for each failed request                                                                                                                   | 3                                 |
| max_retries      | `int` | number of retries for failed requests before it gives up                                                                                               | 5                                 |
| timeout          | `int` | time until it's considered as timout err                                                                                                               | 10                                |
| pace_mode        | `str` | one of 'auto-soft', 'auto-hard', 'manual'. sets the pace to mitigate rate-limiting. (mostly meaningless)                                               | 'auto-hard'                       |
| save_dir         | `str` | directory to save the results, defaults to current directory                                                                                           | `os.getcwd()` (current directory) |
| task_num         | `int` | number of async tasks to be made                                                                                                                       | 3                                 |
| log_stream_level | `str` | sets the log level for logs streamed on the terminal                                                                                                   | 'INFO'                            |
| log_level        | `str` | sets the log level for logging (file)                                                                                                                  | 'DEBUG'                           |
| duplicate_action | `str` | one of 'keep_newest', 'keep_oldest', 'remove', 'keep_original', 'keep_removed'. decides what to do with duplicate entries (usually caused by deletion) | 'keep_newest'                     |

## `PullPushAsync.get_submissions` & `PullPushAsync.get_comments`
all parameters are optional

except for `file_name` and `get_comments` all other parameters are keyword-arguments(kwargs)

returns a `dict` object

| parameter    | type                | description                                                                                                                              | deafult value | get_submissions | get_comments |
|--------------|---------------------|------------------------------------------------------------------------------------------------------------------------------------------|---------------|-----------------|--------------|
| file_name    | `str`               | file name to use for the saves json result. If `None`, doesn't save the file.                                                            | `None`        | ✅               | ✅            |
| get_comments | `bool`              | If true, the result will contain the `comments` field  where all the comments for that post will be contained(`List[dict]`)              | `False`       | ✅               |              |
| after        | `datetime.datetime` | Return results after this date (inclusive >=)                                                                                            |               | ✅               | ✅            |
| before       | `datetime.datetime` | Return results before this date (exclusive <)                                                                                            |               | ✅               | ✅            |
| filters      | `List[str]`         | filters result to only get the fields you want                                                                                           |               | ✅               | ✅            |
| sort         | `str`               | Sort results in a specific order accepts: 'desc', 'asc                                                                                   | desc          | ✅               | ✅            |
| sort_type    | `str`               | Sort by a specific attribute. If `after` and `before` is used, defaults to 'created_utc' accepts: 'created_utc', 'score', 'num_comments' | created_utc   | ✅               | ✅            |
| limit        | `int`               | Number of results to return per request. Maximum value of 100, recommended to keep at default                                            | 100           | ✅               | ✅            |
| ids          | `List[str]`         | Get specific submissions via their ids                                                                                                   |               | ✅               | ✅            |
| link_id      | `str`               | Return results from a particular submission                                                                                              |               |                 | ✅            |
| q            | `str`               | Search term. Will search ALL possible fields                                                                                             |               | ✅               | ✅            |
| title        | `str`               | Searches the title field only                                                                                                            |               | ✅               |              |
| selftext     | `str`               | Searches the selftext field only                                                                                                         |               | ✅               |              |
| author       | `str`               | Restrict to a specific author                                                                                                            |               | ✅               | ✅            |
| subreddit    | `str`               | Restrict to a specific subreddit                                                                                                         |               | ✅               | ✅            |
| score        | `int`               | Restrict results based on score                                                                                                          |               | ✅               |              |
| num_comments | `int`               | Restrict results based on number of comments                                                                                             |               | ✅               |              |
| over_18      | `bool`              | Restrict to nsfw or sfw content                                                                                                          |               | ✅               |              |
| is_video     | `bool`              | Restrict to video content <as of writing this parameter is broken (err 500 will be returned)>                                            |               | ✅               |              |
| locked       | `bool`              | Return locked or unlocked threads only                                                                                                   |               | ✅               |              |
| stickied     | `bool`              | Return stickied or un-stickied content only                                                                                              |               | ✅               |              |
| spoiler      | `bool`              | Exclude or include spoilers only                                                                                                         |               | ✅               |              |
| contest_mode | `bool`              | Exclude or include content mode submissions                                                                                              |               | ✅               |              |

## structure of the returned object
the `PullPushAsync.get_submissions` & `PullPushAsync.get_comments` each returns a `dict` object that is indexed based on its unique ID.
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
