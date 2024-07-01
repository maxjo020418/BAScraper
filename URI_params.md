## params for comments

| Parameter | Description                                 | Default       | Accepted Values                        |
|-----------|---------------------------------------------|---------------|----------------------------------------|
| q         | Search term.                                | N/A           | String / Quoted String for phrases     |
| ids       | Get specific comments via their ids         | N/A           | Comma-delimited base36 ids             |
| size      | Number of results to return                 | 100           | Integer <= 100                         |
| sort      | Sort results in a specific order            | "desc"        | "asc", "desc"                          |
| sort_type | Sort by a specific attribute                | "created_utc" | "score", "num_comments", "created_utc" |
| author    | Restrict to a specific author               | N/A           | String                                 |
| subreddit | Restrict to a specific subreddit            | N/A           | String                                 |
| after     | Return results after this date              | N/A           | Epoch value                            |
| before    | Return results before this date             | N/A           | Epoch value                            |
| link_id   | Return results from a particular submission | N/A           | base36 id                              |

## params for submissions

| Parameter    | Description                                  | Default       | Accepted Values                                      |
|--------------|----------------------------------------------|---------------|------------------------------------------------------|
| ids          | Get specific submissions via their ids       | N/A           | Comma-delimited base36 ids                           |
| q            | Search term. Will search ALL possible fields | N/A           | String / Quoted String for phrases                   |
| title        | Searches the title field only                | N/A           | String / Quoted String for phrases                   |
| selftext     | Searches the selftext field only             | N/A           | String / Quoted String for phrases                   |
| size         | Number of results to return                  | 100           | Integer <= 100                                       |
| sort         | Sort results in a specific order             | "desc"        | "asc", "desc"                                        |
| sort_type    | Sort by a specific attribute                 | "created_utc" | "score", "num_comments", "created_utc"               |
| author       | Restrict to a specific author                | N/A           | String                                               |
| subreddit    | Restrict to a specific subreddit             | N/A           | String                                               |
| after        | Return results after this date               | N/A           | Epoch value                                          |
| before       | Return results before this date              | N/A           | Epoch value                                          |
| score        | Restrict results based on score              | N/A           | Integer or > x or < x (i.e. score=>100 or score=<25) |
| num_comments | Restrict results based on number of comments | N/A           | Integer or > x or < x (i.e. num_comments=>100)       |
| over_18      | Restrict to nsfw or sfw content              | both allowed  | "true" or "false"                                    |
| is_video     | Restrict to video content                    | both allowed  | "true" or "false"                                    |
| locked       | Return locked or unlocked threads only       | both allowed  | "true" or "false"                                    |
| stickied     | Return stickied or unstickied content only   | both allowed  | "true" or "false"                                    |
| spoiler      | Exclude or include spoilers only             | both allowed  | "true" or "false"                                    |
| contest_mode | Exclude or include content mode submissions  | both allowed  | "true" or "false"                                    |
