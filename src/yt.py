from __future__ import annotations

import os
import time
from functools import cached_property
from typing import TYPE_CHECKING, Optional

import googleapiclient.discovery
from google.oauth2.credentials import Credentials

if TYPE_CHECKING:
   import googleapiclient._apis.youtube.v3 as YT

from util import (
   debug,
   left_align,
   serialize,
   smol_hash,
   truncate,
)

class Thumbnails:
   def __init__(self, yt_thumbnails: YT.ThumbnailDetails):
      self.present: list[str] = []
      self.default: Optional[YT.Thumbnail]
      self.medium: Optional[YT.Thumbnail]
      self.high: Optional[YT.Thumbnail]
      self.standard: Optional[YT.Thumbnail]
      self.maxres: Optional[YT.Thumbnail]

      for attr in ["default", "medium", "high", "standard", "maxres"]:
         opaque: Optional[YT.Thumbnail] = yt_thumbnails.get(attr)
         if opaque is None:
            setattr(self, attr, None)
         else:
            self.present.append(attr)
            setattr(self, attr, opaque)

   def __repr__(self):
      return f"Thumbnails{self.present}"

class PlaylistItem:
   def __init__(self, yt: YT.YouTubeResource, yt_playlistitem: YT.PlaylistItem):
      self.yt = yt
      self.is_private = False

      self.id: str = yt_playlistitem["id"]
      snippet = yt_playlistitem["snippet"]

      self.title: str = snippet["title"]
      self.position: int = snippet["position"]
      self.playlist_id: str = snippet["playlistId"]
      self.video_id: str = snippet["resourceId"]["videoId"]

      try:
         self.channel_title: Optional[str] = snippet["videoOwnerChannelTitle"]
      except Exception as e:
         debug(
            "An exception occurred when trying to translate from yt_playlistitem into PlaylistItem",
            start="EXCEPT | ",
         )
         debug(e, start="EXCEPT > ")
         debug("yt_playlistitem was:", start="EXCEPT | ")
         debug(serialize(yt_playlistitem), start="EXCEPT > ")
         debug(
            "I am assuming that's because the video is private, so I'll set channel to 'Private'",
            start="EXCEPT | ",
         )
         self.channel_title = "Private"

   def set_position(self, position: int):
      req = self.yt.playlistItems().update(
         part="snippet",
         body={
            "id": self.id,
            "snippet": {
               "playlistId": self.id,
               "position": position,
               "resourceId": {
                  "kind": "youtube#video",
                  "videoId": self.video_id,
               },
            },
         },
      )
      req.execute()


class Playlist:
   def __init__(self, yt: YT.YouTubeResource, yt_playlist: YT.Playlist):
      self.yt = yt

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
      accumulate = []

      print(f"FETCH  | {self.title}")

      while True:
         req = self.yt.playlistItems().list(
            playlistId=self.id,
            part="id,snippet",
            maxResults=50,
            pageToken=page_token,
         )
         res = req.execute()
         items = res["items"]
         for item in items:
            item_playlist_id = item["snippet"]["playlistId"]
            if item_playlist_id != self.id:
               print(
                  f"ERROR  | Playlist Item belongs to {item_playlist_id} when it should belong to {self.id}"
               )

         before = len(accumulate)
         accumulate.extend(items)
         after = len(accumulate)
         print(f"FETCH  | Playlist Item {before}-{after}")
         page_token = res.get("nextPageToken")
         if page_token is None:
            break

      return [PlaylistItem(self.yt, i) for i in accumulate]

   def jsonl(self) -> str:
      cols: tuple[list[str], list[str], list[str], list[str]] = (
         [serialize("Video Title")],
         [serialize("Channel Name")],
         [serialize("Video ID")],
         [serialize("Playlist Item ID")],
      )
      items = self.items
      epoch = time.time()
      for i in items:
         cols[0].append(serialize(i.title))
         cols[1].append(serialize(i.channel_title))
         cols[2].append(serialize(i.video_id))
         cols[3].append(serialize(i.id))
      for col in cols:
         left_align(col)

      info = {
         "playlist_id": self.id,
         "last_updated_unix": epoch,
      }

      jsonl_out = ""
      jsonl_out += serialize(self.title) + "\n"
      jsonl_out += serialize(info) + "\n"
      for i in range(0, len(self.items)):
         jsonl_out += f"[{cols[0][i]}, {cols[1][i]}, {cols[2][i]}, {cols[3][i]}]\n"

      return jsonl_out

   def friendly_jsonl(self) -> str:
      cols: tuple[list[str], list[str], list[str], list[str]] = (
         [serialize("Title")],
         [serialize("Channel")],
         [serialize("Video ID")],
         [serialize("Smol Hash~")],
      )
      for i in self.items:
         _title = truncate(i.title, max_len=40)
         cols[0].append(serialize(_title))

         _channel_title = i.channel_title
         if _channel_title is not None:
            if _channel_title.endswith(" - Topic"):
               _channel_title = _channel_title[: -len(" - Topic")]
            _channel_title = truncate(_channel_title, max_len=20)
         cols[1].append(serialize(_channel_title))

         cols[2].append(serialize(i.video_id))

         cols[3].append(serialize(smol_hash(i.id)))

      for col in cols:
         left_align(col)

      jsonl_out = ""
      jsonl_out += serialize(self.title) + "\n"
      jsonl_out += serialize(self.id) + "\n"
      for i in range(0, len(cols[0])):
         jsonl_out += f"[{cols[0][i]}, {cols[1][i]}, {cols[2][i]}, {cols[3][i]}]\n"

      return jsonl_out

class Client:
   from config import PORT, SCOPES, TOKEN_PATH

   @staticmethod
   def secret_filename() -> str:
      for file in os.listdir("secrets"):
         if file.startswith("client_secret") and file.endswith(".json"):
            return f"secrets/{file}"

   @staticmethod
   def credentials() -> Credentials:
      creds = None
      if os.path.exists(Client.TOKEN_PATH):
         creds = Credentials.from_authorized_user_file(
            filename=Client.TOKEN_PATH,
            scopes=Client.SCOPES,
         )

      if creds and creds.valid:
         return creds

      if creds and creds.expired and creds.refresh_token:
         from google.auth.transport.requests import Request

         creds.refresh(Request())
      else:
         from google_auth_oauthlib.flow import InstalledAppFlow

         flow = InstalledAppFlow.from_client_secrets_file(
            client_secrets_file=Client.secret_filename(),
            scopes=Client.SCOPES,
         )
         creds = flow.run_local_server(port=Client.PORT)

      with open(Client.TOKEN_PATH, "w") as token:
         token.write(creds.to_json())

      return creds

   def __init__(self):
      # > Disable OAuthlib's HTTPS verification when running locally.
      # > *DO NOT* leave this option enabled in production.
      #
      # sybau
      os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
      self.yt: YT.YouTubeResource = googleapiclient.discovery.build(
         "youtube",
         "v3",
         credentials=self.credentials(),
      )

   def my_playlists(self) -> list[Playlist]:
      page_token = None
      yt_playlists = []

      while True:
         req = self.yt.playlists().list(
            part="snippet,contentDetails",
            maxResults=50,
            mine=True,
            pageToken=page_token,
         )
         res = req.execute()
         before = len(yt_playlists)
         yt_playlists.extend(res["items"])
         after = len(yt_playlists)
         print(f"FETCH  | Playlist {before} - {after}")
         page_token = res.get("nextPageToken")
         if page_token is None:
            break

      return [Playlist(self.yt, p) for p in yt_playlists]
