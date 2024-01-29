# BAScraper
A little (multi-threaded) API wrapper for [PullPush.io](https://www.pullpush.io/) - the 3rd party replacement API for Reddit. After the [2023 Reddit API controversy](https://en.wikipedia.org/wiki/2023_Reddit_API_controversy), 
PushShift.io(and also wrappers such as PSAW and PMAW) is now only available to reddit admins and Reddit PRAW is honestly useless when trying to get a lots of data and data from a specific timeframe.
PullPush.io thankfully solves this issue and this is the wrapper for that said API. For more info on the API(TOS, Forum, Docs, etc.) go to [PullPush.io](https://www.pullpush.io/).

BAScraper(Blue Archive Scraper) was initially made and used for the 2023 recap/wrap up of r/BlueArchive hence the name.
It's pretty basic but planning to add some more features as it goes. I'm also planning to release this as a python package. (this is my first time making an actual py package so bear with me)
It uses multithreading to make requests to the PullPush.io endpoint and returns the result as a JSON(dict) object.

currently it can:
- get submissions/comments from a certain subreddit in supported order/sorting methods specified in the PullPush.io API docs
- get comments under the retrieved submissions
- can get all the submissions based on the number of submissions or in a certain timeframe you specify
- can recover(if possible) deleted/removed submission/comments from the returned result

I also have a tool that can organize, clean, and analyze reddit submission and comment data, which I am planning to release it with this or separately after some polishing.

Also, please ask the PullPush.io owner before making large amounts or request and also respect cooldown times. It stresses the server and can cause inconvenience for everyone.

## basic usage & requirements
this is not yet a python package so this is the rundown on how to use it and set up.

put the BAscraper.py in your working directory and import it with the following dependencies:
```
requests
time
logging
json
dataclasses -> dataclass
typing -> List
datetime -> datetime, timedelta
concurrent.futures -> ThreadPoolExecutor, as_completed
queue -> Queue
```
The only non-default package is `requests`, any version should be fine. also python 3.10+ is recommended

**Example usage**
```python
from BAScraper import Pushpull

import requests
import time
import logging
import json
from dataclasses import dataclass
from typing import List
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue

pp = Pushpull(sleepsec=2, threads=2)
result = pp.get_submissions(after=datetime(2023, 12, 1), before=datetime(2024, 1, 1),
                            subreddit='bluearchive', sort='desc')

# save result as JSON
with open("example.json", "w", encoding='utf-8') as outfile:
    json.dump(result, outfile, indent=4)
```

# Parameters
## _PushPull_ (`__init__`)
all parameters are optional

| parameter   | type          | description                                                                                        | default value                     |
|-------------|---------------|----------------------------------------------------------------------------------------------------|-----------------------------------|
| creds       | `List[Creds]` | not implemented yet                                                                                |                                   |
| sleepsec    | `int`         | cooldown time between each request                                                                 | 1                                 |
| backoffsec  | `int`         | backoff time for each failed request                                                               | 3                                 |
| max_retries | `int`         | number of retries for failed requests before it gives up                                           | 5                                 |
| timeout     | `int`         | time until it's considered as timout err                                                           | 10                                |
| threads     | `int`         | no. of threads when multithreading is used                                                         | 4                                 |
| comment_t   | `int`         | no. of threads used for comment fetching, defaults to `threads`                                    |                                   |
| batch_size  | `int`         | not implemented yet                                                                                |                                   |
| log_level   | `str`         | log level in which is displayed on the console, should be a string representation of logging level | `INFO`                            |
| cwd         | `str`         | dir path where all the log files and JSON file will be stored                                      | `os.getcwd()` (current directory) |

## PushPull._get_submissions_ & PushPull._get_comments_
all parameters are optional

| parameter        | type                | description                                                                                                                                                                      | deafult value | get_submissions | get_comments |
|------------------|---------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------|-----------------|--------------|
| after            | `datetime.datetime` | Return results after this date (inclusive >=)                                                                                                                                    |               | ✅               | ✅            |
| before           | `datetime.datetime` | Return results before this date (exclusive <)                                                                                                                                    |               | ✅               | ✅            |
| get_comments     | `bool`              | If true, the result will contain the `comments` field  where all the comments for that post will be contained(`List[dict]`)                                                      | `False`       | ✅               |              |
| duplicate_action | `str`               | will determine what to do with duplicate results  (usually caused by edited, deleted submission/comments) accepts: 'newest', 'oldest', 'remove', 'keep_original', 'keep_removed' | newest        | ✅               | ✅            |
| filters          | `List[str]`         | filters result to only get the fields you want                                                                                                                                   |               | ✅               | ✅            |
| sort             | `str`               | Sort results in a specific order accepts: 'desc', 'asc                                                                                                                           | desc          | ✅               | ✅            |
| sort_type        | `str`               | Sort by a specific attribute. If `after` and `before` is used, defaults to 'created_utc' accepts: 'created_utc', 'score', 'num_comments'                                         | created_utc   | ✅               | ✅            |
| limit            | `int`               | Number of results to return per request. Maximum value of 100, recommended to keep at default                                                                                    | 100           | ✅               | ✅            |
| ids              | `List[str]`         | Get specific submissions via their ids                                                                                                                                           |               | ✅               | ✅            |
| link_id          | `str`               | Return results from a particular submission                                                                                                                                      |               |                 | ✅            |
| q                | `str`               | Search term. Will search ALL possible fields                                                                                                                                     |               | ✅               | ✅            |
| title            | `str`               | Searches the title field only                                                                                                                                                    |               | ✅               |              |
| selftext         | `str`               | Searches the selftext field only                                                                                                                                                 |               | ✅               |              |
| author           | `str`               | Restrict to a specific author                                                                                                                                                    |               | ✅               | ✅            |
| subreddit        | `str`               | Restrict to a specific subreddit                                                                                                                                                 |               | ✅               | ✅            |
| score            | `int`               | Restrict results based on score                                                                                                                                                  |               | ✅               |              |
| num_comments     | `int`               | Restrict results based on number of comments                                                                                                                                     |               | ✅               |              |
| over_18          | `bool`              | Restrict to nsfw or sfw content                                                                                                                                                  |               | ✅               |              |
| is_video         | `bool`              | Restrict to video content <as of writing this parameter is broken (err 500 will be returned)>                                                                                    |               | ✅               |              |
| locked           | `bool`              | Return locked or unlocked threads only                                                                                                                                           |               | ✅               |              |
| stickied         | `bool`              | Return stickied or un-stickied content only                                                                                                                                      |               | ✅               |              |
| spoiler          | `bool`              | Exclude or include spoilers only                                                                                                                                                 |               | ✅               |              |
| contest_mode     | `bool`              | Exclude or include content mode submissions                                                                                                                                      |               | ✅               |              |