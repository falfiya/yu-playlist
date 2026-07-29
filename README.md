# уμ-Ыαyꙇist

![](./misc/icon.png)

*Edit a YouTube playlist like it was text:*

```js
"Playlist Title"
// Optional Comment
// It can be 0 or more lines
"playlist.id"
00000.0000
// Comments can be added on top of each track
  ["Rich Man"  , "aespa"       , "WAQ5_7YFAVo", "73PNDXNHGL"] // or inline if you want
  ["Aris Rage" , "BasedMonster", "zbsbcKfqtSQ", "PTZI4WR47P"]
```

1. Follow [these instructions](https://developers.google.com/youtube/v3/getting-started) to obtain a `client_secret_xxxxxxx.json`.
2. Authenticate using the stupid OAuth2 Flow
3. `uv sync`
4. Look in `src/config.py` to see if that's what you want
5. `uv run src/main.py`

The output will be in a `jsonl` like format. You can add a comment after the playlist title, directly before each track, or inline. They will stick to the track they are attached to even when ingesting and resetting.

## Dependencies

Both the client and the server require the fantastic `uv` package manager.

I believe this code to be cross platform.

## Server

Keeps track of YouTube video metadata across time. In the future, it may also archive the video.

