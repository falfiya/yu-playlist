from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Optional

import googleapiclient.discovery
from google.oauth2.credentials import Credentials

if TYPE_CHECKING:
   import googleapiclient._apis.youtube.v3 as YT

class Thumbnail:
   def __init__(self, dj_thumbnail: YT.Thumbnail):
      self.url: str = dj_thumbnail["url"]
      self.width: str = dj_thumbnail["width"]
      self.height: str = dj_thumbnail["height"]

class Thumbnails:
   def __init__(self, dj_thumbnails: YT.ThumbnailDetails):
      self.present: list[str] = []
      self.default: Optional[Thumbnails.Thumbnail]
      self.medium: Optional[Thumbnails.Thumbnail]
      self.high: Optional[Thumbnails.Thumbnail]
      self.standard: Optional[Thumbnails.Thumbnail]
      self.maxres: Optional[Thumbnails.Thumbnail]

      for attr in ["default", "medium", "high", "standard", "maxres"]:
         opaque: Optional[YT.Thumbnail] = dj_thumbnails.get(attr)
         if opaque is None:
            setattr(self, attr, None)
         else:
            self.present.append(attr)
            setattr(self, attr, Thumbnail(opaque))

   def __repr__(self):
      return f"Thumbnails{self.present}"

class PlaylistItem:
   def __init__(self, client: Client, dj_playlistitem):
      self.client = client

      self.id: str = dj_playlistitem["id"]
      snippet = dj_playlistitem["snippet"]
      self.title: str = snippet["title"]
      self.resource_id: str = snippet["resourceId"]["videoId"]
      self.channel: str = snippet["videoOwnerChannelTitle"]

   def json(self) -> str:
      return json.dumps([self.resource_id, self.title, self.channel])

class Playlist:
   def __init__(self, client: Client, dj_playlist: YT.Playlist):
      self.client = client

      self.id: str = dj_playlist["id"]
      self.length: int = dj_playlist["contentDetails"]["itemCount"]

      snippet = dj_playlist["snippet"]
      self.published_at: str = snippet["publishedAt"]
      self.channel_id: str = snippet["channelId"]
      self.channel_name: str = snippet["channelTitle"]
      self.title: str = snippet["title"]
      self.desc: str = snippet["description"]

      self.thumbnails = Thumbnails(snippet["thumbnails"])

   def items(self) -> list[PlaylistItem]:
      page_token = None
      accumulate = []

      while True:
         req = self.client.yt.playlistItems().list(
            playlistId=self.id,
            part="id,snippet",
            maxResults=50,
            pageToken=page_token,
         )
         print(f'fetching {page_token}')
         res = req.execute()
         accumulate.extend(res["items"])
         page_token = res.get("nextPageToken")
         if page_token is None:
            break

      return [PlaylistItem(self.client, i) for i in accumulate]

   def jsonl(self) -> str:
      accumulator = json.dumps(self.title) + "\n"
      for i in self.items():
         accumulator += i.json() + "\n"
      return accumulator

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
      self.yt = googleapiclient.discovery.build(
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
         yt_playlists.extend(res["items"])
         page_token = res.get("nextPageToken")
         if page_token is None:
            break

      return [Playlist(self, p) for p in yt_playlists]
