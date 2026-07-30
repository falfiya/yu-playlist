import argparse
import os
import shutil
import sys
from pathlib import Path
import typing as t

import colorama as c
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.shortcuts import choice, message_dialog, yes_no_dialog

from common import ChannelId, PlaylistId, PlaylistItemId, VideoId
from config import ClientConfig
from db import ClientDatabaseOnDisk, FetchablePlaylistItemId
from log import Logging
from textual import TextPlaylist
from yt import YouTube, Playlist
from time import time
import datetime
from relative_datetime import DateTimeUtils

assert __name__ == "__main__", "You must invoke this as a script"

################################################################################
## Command Line Parsing
class ClientArguments:
   directory: str

parser = argparse.ArgumentParser(
   prog="yu-playlist",
   description="CLI and TUI for managing YouTube Playlists",
   epilog="and thats how you use the program. thank you for coming to my ted talk",
)
parser.add_argument("directory", help="The directory where playlists are stored")
if len(sys.argv) < 2:
   parser.print_help()
   exit()
options = ClientArguments()
parser.parse_args(namespace=options)

base = Path(options.directory)

################################################################################
## Loading the config file
config_path = base / "yu-playlist.toml"
try:
   config_file = open(config_path, "r")
except FileNotFoundError:
   copy_default_config_file = yes_no_dialog(
      title="Config file missing!",
      text=(
         f"I looked for a config file at {config_path.absolute()} but I couldn't find one. "
         "Do you want me to make one for you?"
      ),
   ).run()
   if copy_default_config_file:
      default_config_path = Path(__file__).parent / "config.default.toml"
      shutil.copyfile(default_config_path, config_path)
      message_dialog(
         title="All done :3",
         text="I created the config file. Please be sure to edit it.",
      )
      quit(0)
   else:
      exit(1)
config = ClientConfig.from_file(config_file)

################################################################################
## The Meat
os.chdir(base)
l = Logging(config)
db = ClientDatabaseOnDisk("yu-playlist.sqlite3", config)

class YuPlaylistTUI:
   """
   The TUI is stateful and caches as much information as possible
   """
   seen_playlist_titles: dict[PlaylistId, str] = {}
   local_playlists: dict[PlaylistId, TextPlaylist] = {}
   local_playlist_items: dict[PlaylistId, list[PlaylistItemId]] = {}

   _yt: t.Optional[YouTube] = None

   def __init__(self):
      for p in os.listdir("."):
         if not p.endswith(".jsonl"):
            continue
         # Could add some logic for verify the playlist filename matches the id but...
         f = open(p, "r")
         text_playlist = TextPlaylist.from_str(f.readlines(), l)
         self.seen_playlist_titles[text_playlist.id] = text_playlist.title
         self.local_playlists[text_playlist.id] = text_playlist
         self.local_playlist_items[text_playlist.id] = db.get_playlist_item_ids([
            FetchablePlaylistItemId(video_id=item.video_id, smol_hash=item.smol_hash_playlist_item_id)
            for item in text_playlist.items
         ])
      self.main_loop()

   def main_loop(self):
      """
      All functions prefixed with main interact directly with the user through TUI.
      """

      print(
         f"{c.ansi.CSI}2J{c.ansi.CSI}H Welcome to the textual user interface for yu-playlist!"
      )
      message = "How do you want to start?"
      while True:
         what_to_do = choice(
            message=message,
            options=[
               ("diff" , "diff: Displays the difference between local and remote"),
               ("pull" , "pull: Pulls new additions and deletions from remote"),
               ("push" , "push: Enforces the local order on the remote"),
               ("reset", "reset: Discards all local changes and resets to the remote"),
            ],
            default="diff",
         )
         message = "Please pick an option."
         match what_to_do:
            case "diff":
               self.main_diff()
            case "pull":
               self.main_pull()
               ...
            case "push":
               self.main_push()
            case "reset":
               self.main_reset()
            case _:
               raise ValueError("SANITY: The choice was invalid!")

   def main_diff(self):
      pid = choice(
         message=
            "Choose a playlist to fetch\n"
            "Use ... for playlists not known locally\n",
         options=[
            ("cancel", "Cancel"),
            ("...", "..."),
            *self.seen_playlist_titles.items(),
         ],
      )
      if pid == "...":
         _ = self.remote_playlists() # fetch all remote playlists and add them to seen_playlist_titles
         pid = choice(
            message=
               "Choose a playlist to fetch\n"
               "Use ... for playlists not known locally\n",
            options=[
               ("cancel", "Cancel"),
               *self.seen_playlist_titles.items(),
            ],
         )
      if pid == "cancel":
         return

      diff = self.diff(pid)
      # TODO:
      # Display the results of the diff

   def main_pull(self):
      # TODO:
      # Use the above diffing code somehow.
      # When an item is removed on the remote, comment it out in the textual playlist.
      ...

   def main_push(self):
      # Requires pulling and therefore diffing and therefore the least moves algo
      ...

   def main_reset(self):
      # Ask a confirmation from the user.
      # Do you really want to hard reset? Any playlist items and comments you had will be lost.
      ...

   def main_doctor(self):
      # If the database is missing or corrupted there's no way to handle the smol_hashes!
      raise NotImplementedError()

   def yt(self) -> YouTube:
      if self._yt is None:
         self._yt = YouTube(config, l)
      return self._yt

   _diff_epoch: dict[PlaylistId, int]
   _diff_cache: dict[PlaylistId, PlaylistDiff]
   def diff(self, id: PlaylistId) -> PlaylistDiff:
      # From the local perspective
      # New items from the remote should be marked as + with green.
      # Items that were removed on the remote should be marked as - with red.
      # To achieve this, first read the textual playlist.
      # Using the database, immediately convert back from smol_hash to playlist item ids.
      # In fact, reading the textual playlist requires that the database be present.

      # Continuing:
      # Perform a left set difference and right set difference between the local
      # playlist items and the remote playlist items.
      raise NotImplementedError()

   _remote_playlists_epoch: float = 0
   _remote_playlists: t.Optional[list[Playlist]] = None
   def remote_playlists(self) -> list[Playlist]:
      if self._outdated("remote playlists", self._remote_playlists, self._remote_playlists_epoch):
         self._remote_playlists = self.yt().my_playlists()
         self._remote_playlists_epoch = time()
         for p in self._remote_playlists:
            self.seen_playlist_titles[p.id] = p.title
      return self._remote_playlists # type: ignore

   def _outdated(self, friendly_name: str, value, epoch):
      """
      Determine whether a certain cached value is outdated.
      Ask the user if she wants to fetch when not sure.
      """
      if value is None:
         return True
      else:
         fetched_at = datetime.datetime.fromtimestamp(epoch, tz=datetime.timezone.utc)
         relative_time, direction = DateTimeUtils.relative_datetime(fetched_at)
         assert direction == "future", "SANITY: Cache was from the future!"

         age = time() - epoch
         if age > 30 * 60:
            # more than 30 minutes old, fetch always
            return True
         if age > 3 * 60:
            # more than 3 minutes old, ask the user if she wants to fetch
            return yes_no_dialog(
               title=f"{friendly_name} cache outdated",
               text=f"Cached {friendly_name} was last fetched {relative_time} ago.\n Update it?",
            )
         return False

class PlaylistDiff(t.NamedTuple):
   ...

try:
   YuPlaylistTUI()
except KeyboardInterrupt:
   l.error("Interrupt")
   exit()
