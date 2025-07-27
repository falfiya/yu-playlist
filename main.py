from typing import *

import os
import json

from google.oauth2.credentials import Credentials
import googleapiclient.discovery
# import googleapiclient.errors

PORT = 0
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
TOKEN_PATH = "secrets/token.json"

def get_client_secret():
   for file in os.listdir("secrets"):
      if file.startswith("client_secret") and file.endswith(".json"):
         return f"secrets/{file}"

def get_credentials():
   creds = None
   if os.path.exists(TOKEN_PATH):
      creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

   if creds and creds.valid:
      return creds

   if creds and creds.expired and creds.refresh_token:
      from google.auth.transport.requests import Request
      creds.refresh(Request())
   else:
      from google_auth_oauthlib.flow import InstalledAppFlow
      flow = InstalledAppFlow.from_client_secrets_file(get_client_secret(), SCOPES)
      creds = flow.run_local_server(port=PORT)

   with open(TOKEN_PATH, "w") as token:
      token.write(creds.to_json())

class Thumbnails:
   class Thumbnail:
      def __init__(self, yt_thumbnail_opaque):
         self.url: str = yt_thumbnail_opaque["url"]
         self.width: str = yt_thumbnail_opaque["width"]
         self.height: str = yt_thumbnail_opaque["height"]

   def __init__(self, yt_thumbnails_opaque):
      self.present: list[str] = []
      self.default:  Optional[Thumbnails.Thumbnail]
      self.medium:   Optional[Thumbnails.Thumbnail]
      self.high:     Optional[Thumbnails.Thumbnail]
      self.standard: Optional[Thumbnails.Thumbnail]
      self.maxres:   Optional[Thumbnails.Thumbnail]

      for attr in ["default", "medium", "high", "standard", "maxres"]:
         opaque = yt_thumbnails_opaque.get(attr)
         if opaque is None:
            setattr(self, attr, None)
         else:
            self.present.append(attr)
            setattr(self, attr, Thumbnails.Thumbnail(opaque))

   def __repr__(self):
      return f"Thumbnails{self.present}"

class Playlist:
   def __init__(self, yt_playlist_opaque):
      self.id: str = yt_playlist_opaque["id"]
      self.length: int = yt_playlist_opaque["contentDetails"]["itemCount"]

      snippet = yt_playlist_opaque["snippet"]
      self.published_at: str = snippet["publishedAt"]
      self.channel_id: str = snippet["channelId"]
      self.channel_name: str = snippet["channelTitle"]
      self.name: str = snippet["title"]
      self.desc: str = snippet["description"]

      self.thumbnails = Thumbnails(snippet["thumbnails"])

   def __repr__(self):
      return f"#{self.id} '{self.name}' len={self.length}"

def get_all_playlists(yt) -> list[Playlist]:
   page_token = None
   opaque_playlists = []
   while True:
      req = yt.playlists().list(
         part="snippet,contentDetails",
         maxResults=50,
         mine=True,
         pageToken=page_token,
      )
      res = req.execute()
      opaque_playlists.extend(res["items"])
      page_token = res.get("nextPageToken")
      if page_token == None:
         break
   return [Playlist(p) for p in opaque_playlists]

def main():
   # Disable OAuthlib's HTTPS verification when running locally.
   # *DO NOT* leave this option enabled in production.
   os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

   creds = get_credentials()

   yt = googleapiclient.discovery.build(
      "youtube",
      "v3",
      credentials=creds,
   )

   for playlist in get_all_playlists(yt):
      print(playlist)
   # req = yt.playlistItems().list(playlistId="PLkO4zZQGMOEjY3x7w3AKWwmUsYCxOb8Iq", part="id,snippet,contentDetails,status")
   # yt.playlistItems().update()
   # print(req.execute())


if __name__ == "__main__":
   main()
