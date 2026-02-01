# Bridge between filesystem, textual, and YouTube
# Diffing etc.
import typing as t
import textual
import util as u
import yt
import config
import os
import log as l

from pathvalidate import sanitize_filename
from functools import cached_property

videos_file = u.oopen(f"{config.PLAYLISTS_PATH}/.videos.jsonl")
videos_file_object = textual.Videos(videos_file.read())
def write_videos():
   videos_file.write(videos_file_object.jsonl())

class Playlist:
   def __init__(self, *,
                yt_playlist: t.Optional[yt.Playlist] = None,
                playlist_filepath: t.Optional[str] = None,
               ):
      self.id: str
      self._yt_playlist: t.Optional[yt.Playlist] = None
      self.shadow_file_object: textual.Playlist

      if yt_playlist is None and playlist_filepath is None:
         raise ValueError("Must provide one of yt_playlist or playlist_filepath")

      if yt_playlist is not None:
         self.id = yt_playlist.id
         if playlist_filepath is None:
            self.shadow_file = u.oopen(f"{config.PLAYLISTS_PATH}/{sanitize_filename(yt_playlist.title)} - {u.smol_hash(self.id)}.jsonl")
         self._yt_playlist = yt_playlist

      if playlist_filepath is not None:
         self.shadow_file = u.oopen(playlist_filepath)

      try:
         # TODO
         self.shadow_file_object = textual.Playlist(self.shadow_file.read())
      except Exception as e:
         l.warn(e)
         # Couldn't parse the shadow file. Let's write another one.
         # Of course, this means that the diff will come up empty but the code here is so fudged that I'm fine with it doing extra work.
         self.shadow_file_object = textual.Playlist(self.yt_playlist)
         self.write()

      # these type errors were put here by the MAD DEADLY WORLDWIDE COMMUNIST GANGSTER COMPUTER GOD
      self._should_diff = True
      self._shadow_set = None
      self._yt_set = None
      self._shadow_lookup = None
      self._yt_lookup = None
      """
      smol -> yt.PlaylistItem
      """
      self._smol_yt_position = None
      self._yt_shadow_position_forwards = None
      self._yt_shadow_position_backwards = None

   @cached_property
   def yt_playlist(self) -> yt.Playlist:
      if self._yt_playlist is None:
         self._yt_playlist = yt.get_playlist(self.shadow_file_object.id)
      videos_file_object.add(self._yt_playlist.items)
      write_videos()
      return self._yt_playlist

   def reset_to_yt(self):
      """
      Ingests any new tracks and resets existing tracks to YouTube's ordering.
      Returns a list of PlaylistItems that were affected.
      Removes tracks that weren't on YouTube.
      Also resets the titles and channel name.
      """
      items_to_process = self.shadow_file_object.items
      for yt_item in self.missing_from_shadow:
         items_to_process.append(textual.PlaylistItem(yt_item))

      self.shadow_file_object.items = [None] * len(self.yt_playlist.items)

      for item in items_to_process:
         yt_pos = self.smol_yt_position.get(item.smol_hash) # get the youtube position
         if yt_pos is not None:
            # This is a good item, but lets re-make it
            item_again = textual.PlaylistItem(self.yt_lookup[item.smol_hash])
            item_again.preserve_comments_from(item)
            self.shadow_file_object.items[yt_pos] = item_again

      self.write()
      self._should_diff = True

   def ingest_new_yt(self):
      while True:
         missing = sorted(self.missing_from_shadow, key=self.yt_playlist.items.index)
         if len(missing) == 0:
            break

         for item in missing:
            missingno = self.yt_playlist.items.index(item)
            if missingno == 0:
               self.shadow_file_object.items.insert(0, textual.PlaylistItem(item))
               l.info(f"$ <- {item}")
               break
            else:
               # let's see if we can find the playlist item before this one
               before = self.yt_playlist.items[missingno - 1]
               # and match it with one in the shadow
               before_position = self.yt_shadow_position_forwards.get(before)
               if before_position is not None:
                  self.shadow_file_object.items.insert(before_position + 1, textual.PlaylistItem(item))
                  l.info(f"{before} <- {item}")
                  break
         else:
            # guess not? let's just grab the first one and put it at the end
            self.shadow_file_object.items.append(textual.PlaylistItem(missing[0]))
            l.info(f"{self.shadow_file_object.items[-1]} <- {missing[0]}")

         self._should_diff = True
      self.write()

   def write(self):
      u.overwrite(self.shadow_file, self.shadow_file_object.jsonl())

   def push(self):
      if not self.diff_ok:
         raise ValueError("Cannot push to YouTube when the diff is not OK!")

      for ooo in self.ooo:
         ooo.set_position(self._yt_shadow_position_forwards[ooo])

   def close(self):
      self.shadow_file.close()

   def _init_diff(self):
      if not self._should_diff:
         return

      self._shadow_set: t.Set[str] = set()
      self._yt_set: t.Set[str] = set()
      self._shadow_lookup: dict[str, textual.PlaylistItem] = {}
      self._yt_lookup: dict[str, yt.PlaylistItem] = {}
      self._smol_yt_position: dict[str, int] = {}
      # Right now, we're trying to build a path from yt.PlaylistItem <-> indexof shadow_playlist.items
      #
      # What we get back from shortest_out_of_order_sublist is a bunch of indexof shadow_playlist.items
      # that are out of order and need to be sorted. In order to sort, we need the yt.PlaylistItem!
      self._yt_shadow_position_forwards: dict[yt.PlaylistItem, int] = {}
      self._yt_shadow_position_backwards: dict[int, yt.PlaylistItem] = {}

      # shadow_playlist.items.smol_hash -> indexof shadow_playlist.items
      smol_to_shadow_position: dict[str, int] = {}
      for i, item in enumerate(self.shadow_file_object.items):
         smol_to_shadow_position[item.smol_hash] = i
         self._shadow_set.add(item.smol_hash)
         self._shadow_lookup[item.smol_hash] = item


      for i, item in enumerate(self.yt_playlist.items):
         smol = u.smol_hash(item.id)
         self._smol_yt_position[smol] = i
         shadow_position = smol_to_shadow_position.get(smol)
         if shadow_position is not None:
            self._yt_shadow_position_forwards[item] = shadow_position
            self._yt_shadow_position_backwards[shadow_position] = item
         self._yt_set.add(smol)
         self._yt_lookup[smol] = item

      self._should_diff = False

   @property
   def shadow_set(self) -> t.Set[str]:
      self._init_diff()
      return self._shadow_set

   @property
   def yt_set(self) -> t.Set[str]:
      self._init_diff()
      return self._yt_set

   @property
   def shadow_lookup(self) -> dict[str, textual.PlaylistItem]:
      self._init_diff()
      return self._shadow_lookup

   @property
   def yt_lookup(self) -> dict[str, yt.PlaylistItem]:
      self._init_diff()
      return self._yt_lookup

   @property
   def smol_yt_position(self) -> dict[str, int]:
      self._init_diff()
      return self._smol_yt_position

   @property
   def yt_shadow_position_forwards(self) -> dict[yt.PlaylistItem, int]:
      self._init_diff()
      return self._yt_shadow_position_forwards

   @property
   def yt_shadow_position_backwards(self) -> dict[int, yt.PlaylistItem]:
      self._init_diff()
      return self._yt_shadow_position_backwards

   @property
   def missing_from_yt(self) -> list[textual.PlaylistItem]:
      return [self.shadow_lookup[smol] for smol in self.shadow_set - self.yt_set]

   @property
   def missing_from_shadow(self) -> list[yt.PlaylistItem]:
      return [self.yt_lookup[smol] for smol in self.yt_set - self.shadow_set]

   @property
   def diff_ok(self) -> bool:
      return len(self.missing_from_yt) == 0 and len(self.missing_from_shadow) == 0

   @property
   def ooo(self) -> list[yt.PlaylistItem]:
      if not self.diff_ok:
         raise ValueError("Cannot get out-of-order elements if the diff is not OK!")

      out_of_order_positions = u.shortest_out_of_order_sublist(
         [self.yt_shadow_position_forwards[item] for item in self.yt_playlist.items],
      )

      return [self.yt_shadow_position_backwards[pos] for pos in out_of_order_positions]

def my_playlists_online() -> list[Playlist]:
   return [Playlist(yt_playlist=p) for p in yt.my_playlists()]

def my_playlist_files() -> list[str]:
   return [filename[:-6] for filename in os.listdir(config.PLAYLISTS_PATH) if filename.endswith(".jsonl")]

def get_playlist_offline(filename: str) -> Playlist:
   return Playlist(playlist_filepath=f"{config.PLAYLISTS_PATH}/{filename}.jsonl")

def my_playlists_offline() -> list[Playlist]:
   return [
      Playlist(playlist_filepath=f"{config.PLAYLISTS_PATH}/{filename}")
      for filename in my_playlist_files()
   ]
