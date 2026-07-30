import argparse
import datetime
import os
import shutil
import sys
import typing as t
from pathlib import Path
from time import time

import colorama as c
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.shortcuts import choice, message_dialog, yes_no_dialog
from relative_datetime import DateTimeUtils

from common import ChannelId, PlaylistId, PlaylistItemId, VideoId
from config import ClientConfig
from db import ClientDatabaseOnDisk, FetchablePlaylistItemId
from log import Logging
from textual import TextPlaylist
from util import shortest_out_of_order_sublist
from yt import Playlist, PlaylistItem, YouTube

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
   The TUI is stateful and caches as much information as possible.

   That means that there's a sort of incremental computation-like thing going on
   here. Unfortunately, we are not smart enough to track dependencies, so if you
   end up invalidating something, you should also invalidate everything else
   that depends on that thing.

   ¯∖‿(ツ)‿/¯
   """

   seen_playlist_titles: dict[PlaylistId, str] = {}
   local_playlists: dict[PlaylistId, TextPlaylist] = {}
   local_playlist_items: dict[PlaylistId, list[PlaylistItemId]] = {}

   _yt: t.Optional[YouTube] = None

   def __init__(self):
      for p in os.listdir("."):
         if not p.endswith(".jsonl"):
            continue
         # Could add some logic for verify the playlist filename matches the id but that runs into
         f = open(p, "r")
         text_playlist = TextPlaylist.from_str(f.readlines(), l)
         self.seen_playlist_titles[text_playlist.id] = text_playlist.title
         self.local_playlists[text_playlist.id] = text_playlist
         self.local_playlist_items[text_playlist.id] = db.get_playlist_item_ids(
            [
               FetchablePlaylistItemId(
                  video_id=item.video_id, smol_hash=item.smol_hash_playlist_item_id
               )
               for item in text_playlist.items
            ]
         )
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
               ("diff", "diff: Displays the difference between local and remote"),
               ("pull", "pull: Pulls new additions and deletions from remote"),
               ("push", "push: Enforces the local order on the remote"),
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
         message="Choose a playlist to fetch\n"
         "Use ... for playlists not known locally\n",
         options=[
            ("cancel", "Cancel"),
            ("...", "..."),
            *self.seen_playlist_titles.items(),
         ],
      )
      if pid == "...":
         _ = (
            self.remote_playlists()
         )  # fetch all remote playlists and add them to seen_playlist_titles
         pid = choice(
            message="Choose a playlist to fetch\n"
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

   def friendly_playlist_title(self, id: PlaylistId) -> str:
      return self.seen_playlist_titles.get(id, f"Playlist#{id}")

   _diff_epoch: dict[PlaylistId, float]
   _diff_cache: dict[PlaylistId, PlaylistDiff]

   def diff(self, id: PlaylistId) -> PlaylistDiff:
      """
      Determine items deleted from the remote, new items incoming from the
      remote and their new locations.
      """
      _usr_description = f"diff for {self.friendly_playlist_title(id)}"
      if self._outdated(
         _usr_description, self._diff_cache.get(id), self._diff_epoch.get(id)
      ):
         local_items = self.local_playlist_items[id]
         remote_items = [item.id for item in self.remote_playlist_items(id)]
         s_local_items = frozenset(local_items)
         s_remote_items = frozenset(remote_items)
         local_items_not_on_remote = s_local_items - s_remote_items
         remote_items_not_on_local = s_remote_items - s_local_items
         in_common_local_items = [
            item for item in local_items if item in s_remote_items
         ]
         in_common_remote_items = [
            item for item in remote_items if item in s_local_items
         ]
         assert frozenset(in_common_local_items) == frozenset(in_common_remote_items), (
            ""
         )
         "SANITY: in_common_local_items must have the same entries as in_common_remote_items!"
         out_of_order_items_according_to_remote = shortest_out_of_order_sublist(
            canonical_order=in_common_remote_items,
            unsorted=in_common_local_items,
         )
         out_of_order_items_according_to_local = shortest_out_of_order_sublist(
            canonical_order=in_common_local_items,
            unsorted=in_common_remote_items,
         )
         if (
            out_of_order_items_according_to_remote
            != out_of_order_items_according_to_local
         ):
            raise AssertionError(
               "SANITY: The server and client should agree on the same out of order items!"
            )
            # TODO: Write a log file if it fails

         # If an item is new, we'd like to know where it's after.
         new_items = []
         for item_id in remote_items_not_on_local:
            remote_order = in_common_remote_items.index(item_id)
            after: t.Optional[PlaylistItemId]
            if remote_order == 0:
               after = None
            else:
               after = in_common_remote_items[remote_order - 1]
            new_items.append(NewPlaylistItem(id=item_id, after=after))

         self._diff_cache[id] = PlaylistDiff(
            local_items_not_on_remote=local_items_not_on_remote,
            remote_items_not_on_local=frozenset(new_items),
            out_of_order=out_of_order_items_according_to_remote,
         )
         self._diff_epoch[id] = time()
      return self._diff_cache[id]

   _remote_playlists_epoch: float = 0
   _remote_playlists_cache: t.Optional[list[Playlist]] = None

   def remote_playlists(self) -> list[Playlist]:
      if self._outdated(
         "remote playlists", self._remote_playlists_cache, self._remote_playlists_epoch
      ):
         self._remote_playlists_cache = self.yt().my_playlists()
         self._remote_playlists_epoch = time()
         for p in self._remote_playlists_cache:
            self.seen_playlist_titles[p.id] = p.title
      return self._remote_playlists_cache  # type: ignore

   _remote_playlist_items_epoch: dict[PlaylistId, float]
   _remote_playlist_items: dict[PlaylistId, list[PlaylistItem]]
   def remote_playlist_items(self, id: PlaylistId) -> list[PlaylistItem]:
      outdated = self._outdated(
         f"{self.friendly_playlist_title(id)}'s items",
         self._remote_playlist_items.get(id),
         self._remote_playlist_items_epoch.get(id),
      )
      if outdated:
         # TODO: Fetch and cache these
         ...

   def _outdated(self, friendly_name: str, value, epoch: t.Optional[float]):
      """
      Determine whether a certain cached value is outdated.
      Ask the user if she wants to fetch when not sure.
      """
      if value or epoch is None:
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
   local_items_not_on_remote: frozenset[PlaylistItemId]
   """
   From the perspective of the remote, you should delete these things.
   """
   remote_items_not_on_local: frozenset[NewPlaylistItem]
   out_of_order: frozenset[PlaylistItemId]


class NewPlaylistItem(t.NamedTuple):
   id: PlaylistItemId
   after: t.Optional[PlaylistItemId]
   """
   None means that it's the first.
   """


try:
   YuPlaylistTUI()
except KeyboardInterrupt:
   l.error("Interrupt")
   exit()
