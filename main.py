import os

from typing import TYPE_CHECKING, Optional

import googleapiclient.discovery
from google.oauth2.credentials import Credentials

from client import Client

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

   return creds

def main():
   for p in Client().my_playlists():
      os.makedirs("playlists", exist_ok=True)
      pfile = open(f"playlists/{p.id}.jsonl", "w")
      pfile.write(p.jsonl())

main()
