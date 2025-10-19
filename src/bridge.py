# Bridge between filesystem, shadow, and YouTube
import typing as t
import shadow
import util as u
import yt
import config
import os
import log as l

from pathvalidate import sanitize_filename
from functools import cached_property

class Playlist:
   def __init__(self, *,
                yt_playlist: t.Optional[yt.Playlist] = None,
                friendly_filepath: t.Optional[str] = None):
      """
      There are three ways to make this object:
      - yt_playlist only
      - friendly_filepath only
      - both
      """
      self.id: str
      self._yt_playlist: t.Optional[yt.Playlist] = None
      self.shadow_playlist: shadow.Playlist

      if yt_playlist is None and friendly_filepath is None:
         raise ValueError("Both cannot be None!")

      if yt_playlist is not None:
         self.id = yt_playlist.id
         if friendly_filepath is None:
            self.friendly_file = u.oopen(f"{config.PLAYLISTS_PATH}/{sanitize_filename(yt_playlist.title)} - {u.smol_hash(self.id)}.jsonl")
         self._yt_playlist = yt_playlist

      if friendly_filepath is not None:
         self.friendly_file = u.oopen(friendly_filepath)

      try:
         self.shadow_playlist = shadow.Playlist(self.friendly_file.read())
      except Exception as e:
         l.warn(e)
         # Couldn't parse the shadow file. Let's write another one.
         self.shadow_playlist = shadow.Playlist(self.yt_playlist)
         self.write()

      # these type errors were put here by the Communist Gangster Computer God
      self._should_diff = True
      self._shadow_set = None
      self._yt_set = None
      self._shadow_lookup = None
      self._yt_lookup = None
      self._smol_yt_position = None
      self._yt_shadow_position_forwards = None
      self._yt_shadow_position_backwards = None

   @cached_property
   def yt_playlist(self) -> yt.Playlist:
      if self._yt_playlist is None:
         self._yt_playlist = yt.get_playlist(self.shadow_playlist.id)
      return self._yt_playlist

   def reset_to_yt(self):
      """
      Ingests any new tracks and resets existing tracks to YouTube's ordering.
      Returns a list of PlaylistItems that were affected.
      Removes tracks that weren't on YouTube
      """
      items_to_process = self.shadow_playlist.items
      for yt_item in self.missing_from_shadow:
         items_to_process.append(shadow.PlaylistItem(yt_item))

      self.shadow_playlist.items = [None] * len(self.yt_playlist.items)

      for item in items_to_process:
         yt_pos = self.smol_yt_position.get(item.smol_hash)
         if yt_pos is not None:
            self.shadow_playlist.items[yt_pos] = item

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
               self.shadow_playlist.items.insert(0, shadow.PlaylistItem(item))
               l.info(f"$ <- {item}")
               break
            else:
               # let's see if we can find the playlist item before this one
               before = self.yt_playlist.items[missingno - 1]
               # and match it with one in the shadow
               before_position = self.yt_shadow_position_forwards.get(before)
               if before_position is not None:
                  self.shadow_playlist.items.insert(before_position + 1, shadow.PlaylistItem(item))
                  l.info(f"{before} <- {item}")
                  break
         else:
            # guess not? let's just grab the first one and put it at the end
            self.shadow_playlist.items.append(shadow.PlaylistItem(missing[0]))
            l.info(f"{self.shadow_playlist.items[-1]} <- {missing[0]}")

         self._should_diff = True
      self.write()

   def write(self):
      full_file = u.oopen(f"{config.PLAYLISTS_PATH}/full/{self.shadow_playlist.id}.jsonl")
      full_file.seek(0)
      full_file.write(self.shadow_playlist.jsonl())
      full_file.close()
      self.friendly_file.seek(0)
      self.friendly_file.write(self.shadow_playlist.friendly_jsonl())

   def close(self):
      self.friendly_file.close()

   def _init_diff(self):
      if not self._should_diff:
         return

      self._shadow_set: t.Set[str] = set()
      self._yt_set: t.Set[str] = set()
      self._shadow_lookup: dict[str, shadow.PlaylistItem] = {}
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
      for i, item in enumerate(self.shadow_playlist.items):
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
   def shadow_lookup(self) -> dict[str, shadow.PlaylistItem]:
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
   def missing_from_yt(self) -> list[shadow.PlaylistItem]:
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
   return Playlist(friendly_filepath=f"{config.PLAYLISTS_PATH}/{filename}.jsonl")

def my_playlists_offline() -> list[Playlist]:
   return [
      Playlist(friendly_filepath=f"{config.PLAYLISTS_PATH}/{filename}")
      for filename in my_playlist_files()
   ]
