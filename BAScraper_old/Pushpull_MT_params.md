# Parameters
## `Pushpull.__init__`
all parameters are optional

| parameter   | type          | description                                                                                              | default value                     |
|-------------|---------------|----------------------------------------------------------------------------------------------------------|-----------------------------------|
| creds       | `List[Creds]` | not implemented yet                                                                                      |                                   |
| sleepsec    | `int`         | cooldown time between each request                                                                       | 1                                 |
| backoffsec  | `int`         | backoff time for each failed request                                                                     | 3                                 |
| max_retries | `int`         | number of retries for failed requests before it gives up                                                 | 5                                 |
| timeout     | `int`         | time until it's considered as timout err                                                                 | 10                                |
| threads     | `int`         | no. of threads when multithreading is used                                                               | 2                                 |
| comment_t   | `int`         | no. of threads used for comment fetching, defaults to `threads`                                          |                                   |
| batch_size  | `int`         | not implemented yet                                                                                      |                                   |
| log_level   | `str`         | log level in which is displayed on the console, should be a string representation of logging level       | `INFO`                            |
| cwd         | `str`         | dir path where all the log files and JSON file will be stored                                            | `os.getcwd()` (current directory) |
| pace_mode   | `str`         | one of `auto-soft`, `auto-hard`, `manual`. sets the pace to mitigate rate-limiting. (mostly meaningless) | `auto-hard`                       |

## `Pushpull.get_submissions` & `Pushpull.get_comments`
all parameters are optional
returns a `dict` object

| parameter        | type                | description                                                                                                                                                                                                                                 | deafult value | get_submissions | get_comments |
|------------------|---------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------|-----------------|--------------|
| after            | `datetime.datetime` | Return results after this date (inclusive >=)                                                                                                                                                                                               |               | ✅               | ✅            |
| before           | `datetime.datetime` | Return results before this date (exclusive <)                                                                                                                                                                                               |               | ✅               | ✅            |
| get_comments     | `bool`              | If true, the result will contain the `comments` field  where all the comments for that post will be contained(`List[dict]`)                                                                                                                 | `False`       | ✅               |              |
| duplicate_action | `str`               | will determine what to do with duplicate results  (usually caused by edited, deleted submission/comments) accepts: 'newest', 'oldest', 'remove', 'keep_original', 'keep_removed'. Not guaranteed but can recover deleted posts if possible. | newest        | ✅               | ✅            |
| filters          | `List[str]`         | filters result to only get the fields you want                                                                                                                                                                                              |               | ✅               | ✅            |
| sort             | `str`               | Sort results in a specific order accepts: 'desc', 'asc                                                                                                                                                                                      | desc          | ✅               | ✅            |
| sort_type        | `str`               | Sort by a specific attribute. If `after` and `before` is used, defaults to 'created_utc' accepts: 'created_utc', 'score', 'num_comments'                                                                                                    | created_utc   | ✅               | ✅            |
| limit            | `int`               | Number of results to return per request. Maximum value of 100, recommended to keep at default                                                                                                                                               | 100           | ✅               | ✅            |
| ids              | `List[str]`         | Get specific submissions via their ids                                                                                                                                                                                                      |               | ✅               | ✅            |
| link_id          | `str`               | Return results from a particular submission                                                                                                                                                                                                 |               |                 | ✅            |
| q                | `str`               | Search term. Will search ALL possible fields                                                                                                                                                                                                |               | ✅               | ✅            |
| title            | `str`               | Searches the title field only                                                                                                                                                                                                               |               | ✅               |              |
| selftext         | `str`               | Searches the selftext field only                                                                                                                                                                                                            |               | ✅               |              |
| author           | `str`               | Restrict to a specific author                                                                                                                                                                                                               |               | ✅               | ✅            |
| subreddit        | `str`               | Restrict to a specific subreddit                                                                                                                                                                                                            |               | ✅               | ✅            |
| score            | `int`               | Restrict results based on score                                                                                                                                                                                                             |               | ✅               |              |
| num_comments     | `int`               | Restrict results based on number of comments                                                                                                                                                                                                |               | ✅               |              |
| over_18          | `bool`              | Restrict to nsfw or sfw content                                                                                                                                                                                                             |               | ✅               |              |
| is_video         | `bool`              | Restrict to video content <as of writing this parameter is broken (err 500 will be returned)>                                                                                                                                               |               | ✅               |              |
| locked           | `bool`              | Return locked or unlocked threads only                                                                                                                                                                                                      |               | ✅               |              |
| stickied         | `bool`              | Return stickied or un-stickied content only                                                                                                                                                                                                 |               | ✅               |              |
| spoiler          | `bool`              | Exclude or include spoilers only                                                                                                                                                                                                            |               | ✅               |              |
| contest_mode     | `bool`              | Exclude or include content mode submissions                                                                                                                                                                                                 |               | ✅               |              |

## structure of the returned object
the `PushPull.get_submissions` & `PushPull.get_comments` each returns a `dict` object that is indexed based on its unique ID.
it is so that it can be easily saved into a JSON format, also it is sorted in the order you specified when scraping
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