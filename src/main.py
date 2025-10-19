import os
import sys

from pathvalidate import sanitize_filename

from client import Client, Playlist, ShadowPlaylist
from util import smol_hash

PORT = 0
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
TOKEN_PATH = "secrets/token.json"

in_mem_playlists: dict[str, Playlist] = {}


def fetch():
   os.makedirs("playlists/in/full", exist_ok=True)
   os.makedirs("playlists/out", exist_ok=True)
   for p in Client().my_playlists():
      in_mem_playlists[p.id] = p


def save():
   fetch()
   for p in in_mem_playlists.values():
      p_full_file = open(f"playlists/in/full/{p.id}.jsonl", "w", encoding="utf-8")
      p_full_file.write(p.jsonl())
      p_full_file.close()

      friendly_file_name = f"{sanitize_filename(p.title)} - {smol_hash(p.id)}.jsonl"
      p_friendly_file = open(
         f"playlists/in/{friendly_file_name}", "w", encoding="utf-8"
      )
      p_friendly_file.write(p.friendly_jsonl())
      p_friendly_file.close()


def post():
   fetch()
   for jsonlfile in os.listdir("playlists/out"):
      if not jsonlfile.endswith(".jsonl"):
         continue
      pfile = open("playlists/out/" + jsonlfile, "r", encoding="utf-8")
      sp = ShadowPlaylist(Client(), pfile.readlines())
      p = in_mem_playlists[sp.id]
      pfile = open(f"playlists/in/{p.id}.jsonl", "w", encoding="utf-8")
      pfile.write(p.jsonl())
      pfile.close()
      sp.mirror_wrt(p)

if __name__ == "__main__":
   option = sys.argv[1]
   if option == "save":
      save()
   elif option == "post":
      post()
   else:
      raise ValueError("python main.py [save | post]")
