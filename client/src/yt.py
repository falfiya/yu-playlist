# pyright: reportTypedDictNotRequiredAccess=warning

import os
import typing as t

import googleapiclient.discovery
from google.oauth2.credentials import Credentials

if t.TYPE_CHECKING:
   import googleapiclient._apis.youtube.v3 as YT

import util as u
from config import ClientConfig
from log import Logging

import pydantic as p

missing_client_secrets = """
You are missing a client secret file.

Go to https://console.cloud.google.com and then navigate:
> [project] > Credentials > [OAuth 2.0 Client ID] > Add Secret
"""

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


class YouTube:
   def __init__(self, config: ClientConfig, l: Logging):
      self.l = l
      self.config = config
      # > Disable OAuthlib's HTTPS verification when running locally.
      # > *DO NOT* leave this option enabled in production.
      #
      # sybau
      os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
      try:
         self.yt: YT.YouTubeResource = googleapiclient.discovery.build(
            "youtube",
            "v3",
            credentials=self._credentials(),
         )
      except Exception as e:
         if f"{e}".find("Unauthorized"):
            print(e)
            print("This can happen when the Client Secret is outdated.")
            exit(1)

   def _secret_filename(self) -> str:
      for file in os.listdir(self.config.secrets_path):
         if file.startswith("client_secret") and file.endswith(".json"):
            return f"{self.config.secrets_path}/{file}"
      raise FileNotFoundError(missing_client_secrets)

   def _credentials(self):
      auth = None
      token_path = self.config.secrets_path + "/token.json"
      if os.path.exists(token_path):
         auth = Credentials.from_authorized_user_file(
            filename=token_path,
            scopes=SCOPES,
         )

      if auth and auth.valid:
         return auth

      if auth and auth.expired and auth.refresh_token:
         from google.auth.transport.requests import Request

         auth.refresh(Request())
      else:
         from google_auth_oauthlib.flow import InstalledAppFlow

         flow = InstalledAppFlow.from_client_secrets_file(
            client_secrets_file=self._secret_filename(),
            scopes=SCOPES,
         )
         auth = flow.run_local_server(port=self.config.oauth2_callback_port)

      with open(token_path, "w") as token:
         token.write(auth.to_json())

      return auth

   def get_playlistitems(self, pl: Playlist) -> list[PlaylistItem]:
      page_token: t.Optional[str] = None
      # stupidass API doesn't return it to us in order...
      accumulate = {}

      self.l.debug(pl.title)
      self.l.group_start()

      while True:
         req = self.yt.playlistItems().list(
            playlistId=pl.id,
            part="id,snippet",
            maxResults=50,
            pageToken=page_token,  # type: ignore | this can take none and it's fine
         )
         res = req.execute()
         items = res["items"]
         for item in items:
            position = item["snippet"]["position"]
            accumulate[position] = item
            self.l.debug(item["snippet"]["title"])
            item_playlist_id = item["snippet"]["playlistId"]
            if item_playlist_id != pl.id:
               print(
                  f"ERROR  | Playlist Item belongs to {item_playlist_id} when it should belong to {pl.id}"
               )

         before = len(accumulate)
         after = len(accumulate)
         self.l.debug(f"Playlist Item [{before:>3}, {after:>3}]")
         page_token = res.get("nextPageToken")
         if page_token is None:
            break

      output = [
         PlaylistItem.from_yt(accumulate[i], self.l) for i in range(0, len(accumulate))
      ]
      self.l.group_end()
      return output

   def set_playlistitem_position(self, pli: PlaylistItem, position: int):
      req = self.yt.playlistItems().update(
         part="snippet",
         body={
            "id": pli.id,
            "snippet": {
               "playlistId": pli.playlist_id,
               "position": position,
               "resourceId": {
                  "kind": "youtube#video",
                  "videoId": pli.video_id,
               },
            },
         },
      )
      req.execute()

   def get_playlist(self, id: str) -> Playlist:
      res = self.yt.playlists().list(part="snippet,contentDetails", id=id).execute()
      items = res["items"]
      if len(items) == 0:
         raise LookupError(f"Could not find playlist id {u.serialize(id)}!")
      return Playlist.from_yt(items[0])

   def my_playlists(self) -> list[Playlist]:
      page_token: t.Optional[str] = None
      yt_playlists = []

      self.l.debug("Fetching Playlists:")
      self.l.group_start()
      while True:
         req = self.yt.playlists().list(
            part="snippet,contentDetails",
            maxResults=50,
            mine=True,
            pageToken=page_token,  # type: ignore
         )
         res = req.execute()
         before = len(yt_playlists)
         yt_playlists.extend(res["items"])
         after = len(yt_playlists)
         self.l.debug(f"Playlist [{before:>2}, {after:>2}]")
         page_token = res.get("nextPageToken")
         if page_token is None:
            break

      output = list(map(Playlist.from_yt, yt_playlists))
      self.l.group_end()
      return output


class Thumbnails(p.BaseModel):
   present: list[str]
   default: t.Optional[YT.Thumbnail]
   medium: t.Optional[YT.Thumbnail]
   high: t.Optional[YT.Thumbnail]
   standard: t.Optional[YT.Thumbnail]
   maxres: t.Optional[YT.Thumbnail]

   @staticmethod
   def from_yt(yt_thumbnails: YT.ThumbnailDetails) -> Thumbnails:
      present = []
      for attr in ["default", "medium", "high", "standard", "maxres"]:
         opaque: t.Optional[YT.Thumbnail] = yt_thumbnails.get(attr)
         if opaque is not None:
            present.append(attr)
      return Thumbnails(present=present, **yt_thumbnails)

   def __repr__(self):
      return f"Thumbnails{self.present}"


class PlaylistItem(p.BaseModel):
   id: str
   title: str
   position: int
   playlist_id: str
   video_id: str
   channel_id: str
   channel_title: t.Optional[str]

   @staticmethod
   def from_yt(yt_playlistitem: YT.PlaylistItem, l: Logging):
      snippet = yt_playlistitem["snippet"]
      resource_id = snippet["resourceId"]
      return PlaylistItem(
         id=yt_playlistitem["id"],
         title=snippet["title"],
         position=snippet["position"],
         playlist_id=snippet["playlistId"],
         video_id=resource_id["videoId"],
         channel_id=snippet["videoOwnerChannelId"],
         channel_title=snippet["videoOwnerChannelTitle"],
      )

   def __repr__(self) -> str:
      return f"{self.title} - {self.channel_title}"


class Playlist(p.BaseModel):
   id: str
   length: int
   published_at: str
   channel_id: str
   channel_title: str
   title: str
   desc: str
   thumbnails: Thumbnails

   @staticmethod
   def from_yt(yt_playlist: YT.Playlist):
      snippet = yt_playlist["snippet"]
      return Playlist(
         id=yt_playlist["id"],
         length=yt_playlist["contentDetails"]["itemCount"],
         published_at=snippet["publishedAt"],
         channel_id=snippet["channelId"],
         channel_title=snippet["channelTitle"],
         title=snippet["title"],
         desc=snippet["description"],
         thumbnails=snippet["thumbnails"],  # type: ignore coerce
      )
