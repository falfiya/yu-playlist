from __future__ import annotations

import os
import typing as t
from functools import cached_property

import googleapiclient.discovery
from google.oauth2.credentials import Credentials

if t.TYPE_CHECKING:
   import googleapiclient._apis.youtube.v3 as YT

import util as u
import log as l
import config

missing_client_secrets = """
You are missing a client secret file.

Go to https://console.cloud.google.com and then navigate:
> [project] > Credentials > [OAuth 2.0 Client ID] > Add Secret
"""

def _secret_filename() -> str:
   for file in os.listdir("secrets"):
      if file.startswith("client_secret") and file.endswith(".json"):
         return f"secrets/{file}"

   raise ValueError(missing_client_secrets)

def _credentials() -> Credentials:
   creds = None
   if os.path.exists(config.TOKEN_PATH):
      creds = Credentials.from_authorized_user_file(
         filename=config.TOKEN_PATH,
         scopes=config.SCOPES,
      )

   if creds and creds.valid:
      return creds

   if creds and creds.expired and creds.refresh_token:
      from google.auth.transport.requests import Request

      creds.refresh(Request())
   else:
      from google_auth_oauthlib.flow import InstalledAppFlow

      flow = InstalledAppFlow.from_client_secrets_file(
         client_secrets_file=_secret_filename(),
         scopes=config.SCOPES,
      )
      creds = flow.run_local_server(port=config.PORT)

   with open(config.TOKEN_PATH, "w") as token:
      token.write(creds.to_json())

   return creds

# > Disable OAuthlib's HTTPS verification when running locally.
# > *DO NOT* leave this option enabled in production.
#
# sybau
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
try:
   yt: YT.YouTubeResource = googleapiclient.discovery.build(
      "youtube",
      "v3",
      credentials=_credentials(),
   )
except Exception as e:
   if f"{e}".find("Unauthorized"):
      print(e)
      print("This can happen when the Client Secret is outdated.")
      exit(1)

class Thumbnails:
   def __init__(self, yt_thumbnails: YT.ThumbnailDetails):
      self.present: list[str] = []
      self.default: t.Optional[YT.Thumbnail]
      self.medium: t.Optional[YT.Thumbnail]
      self.high: t.Optional[YT.Thumbnail]
      self.standard: t.Optional[YT.Thumbnail]
      self.maxres: t.Optional[YT.Thumbnail]

      for attr in ["default", "medium", "high", "standard", "maxres"]:
         opaque: t.Optional[YT.Thumbnail] = yt_thumbnails.get(attr)
         if opaque is None:
            setattr(self, attr, None)
         else:
            self.present.append(attr)
            setattr(self, attr, opaque)

   def __repr__(self):
      return f"Thumbnails{self.present}"

class PlaylistItem:
   def __init__(self, yt_playlistitem: YT.PlaylistItem):
      self.is_private = False

      self.id: str = yt_playlistitem["id"]
      snippet = yt_playlistitem["snippet"]

      self.title: str = snippet["title"]
      self.position: int = snippet["position"]
      self.playlist_id: str = snippet["playlistId"]
      self.video_id: str = snippet["resourceId"]["videoId"]

      try:
         self.channel_title: t.Optional[str] = snippet["videoOwnerChannelTitle"]
      except Exception as e:
         l.debug("An exception occurred during translation from YT.PlaylistItem")
         l.debug(e)
         l.group_start()
         l.debug("YT.PlaylistItem was:")

         l.group_start()
         l.debug(yt_playlistitem)
         l.group_end()

         l.debug("Proceeding under the assumption that the video is private.")
         l.group_end()
         self.channel_title = None

   def set_position(self, position: int):
      req = yt.playlistItems().update(
         part="snippet",
         body={
            "id": self.id,
            "snippet": {
               "playlistId": self.playlist_id,
               "position": position,
               "resourceId": {
                  "kind": "youtube#video",
                  "videoId": self.video_id,
               },
            },
         },
      )
      req.execute()

   def __repr__(self) -> str:
      return f"{self.title} - {self.channel_title}"


class Playlist:
   def __init__(self, yt_playlist: YT.Playlist):
      self.id: str = yt_playlist["id"]
      self.length: int = yt_playlist["contentDetails"]["itemCount"]

      snippet = yt_playlist["snippet"]
      self.published_at: str = snippet["publishedAt"]
      self.channel_id: str = snippet["channelId"]
      self.channel_title: str = snippet["channelTitle"]
      self.title: str = snippet["title"]
      self.desc: str = snippet["description"]

      self.thumbnails: YT.ThumbnailDetails = snippet["thumbnails"]

   @cached_property
   def items(self) -> list[PlaylistItem]:
      page_token = None
      accumulate = {} # stupidass API doesn't return it to us in order...

      l.debug(self.title)
      l.group_start()

      while True:
         req = yt.playlistItems().list(
            playlistId=self.id,
            part="id,snippet",
            maxResults=50,
            pageToken=page_token,
         )
         res = req.execute()
         items = res["items"]
         for item in items:
            position = item["snippet"]["position"]
            accumulate[position] = item
            l.debug(item["snippet"]["title"])
            item_playlist_id = item["snippet"]["playlistId"]
            if item_playlist_id != self.id:
               print(
                  f"ERROR  | Playlist Item belongs to {item_playlist_id} when it should belong to {self.id}"
               )

         before = len(accumulate)
         after = len(accumulate)
         l.debug(f"Playlist Item [{before:>3}, {after:>3}]")
         page_token = res.get("nextPageToken")
         if page_token is None:
            break

      output = [PlaylistItem(accumulate[i]) for i in range(0, len(accumulate))]
      l.group_end()
      return output


def get_playlist(id: str) -> Playlist:
   res = yt.playlists().list(part="snippet,contentDetails", id=id).execute()
   items = res["items"]
   if len(items) == 0:
      raise LookupError(f"Could not find playlist id {u.serialize(id)}!")
   return Playlist(items[0])

def my_playlists() -> list[Playlist]:
   page_token = None
   yt_playlists = []

   l.debug("Fetching Playlists:")
   l.group_start()
   while True:
      req = yt.playlists().list(
         part="snippet,contentDetails",
         maxResults=50,
         mine=True,
         pageToken=page_token,
      )
      res = req.execute()
      before = len(yt_playlists)
      yt_playlists.extend(res["items"])
      after = len(yt_playlists)
      l.debug(f"Playlist [{before:>2}, {after:>2}]")
      page_token = res.get("nextPageToken")
      if page_token is None:
         break

   output = list(map(Playlist, yt_playlists))
   l.group_end()
   return output
