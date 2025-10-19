# Bridge between filesystem, shadow, and YouTube
import typing as t
import shadow
import util as u
import yt
import config

from pathvalidate import sanitize_filename


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
         self.full_file = u.oopen(f"{config.PLAYLISTS_PATH}/full/{yt_playlist.id}.jsonl")
         if friendly_filepath is None:
            self.friendly_file = u.oopen(f"{config.PLAYLISTS_PATH}/{sanitize_filename(yt_playlist.title)} - {u.smol_hash(self.id)}.jsonl")
         self._yt_playlist = yt_playlist

      if friendly_filepath is not None:
         self.friendly_file = u.oopen(friendly_filepath)

      try:
         self.shadow_playlist = shadow.Playlist(self.friendly_file.readlines())
      except Exception:
         # Couldn't parse the shadow file. Let's write another one.
         self.shadow_playlist = shadow.Playlist(self.yt_playlist)
         self.write()

      # these type errors were put here by the Communist Gangster Computer God
      self._shadow_set = None
      self._yt_set = None
      self._shadow_lookup = None
      self._yt_lookup = None
      self._yt_shadow_position_forwards = None
      self._yt_shadow_position_backwards = None

   @property
   def yt_playlist(self) -> yt.Playlist:
      if self._yt_playlist is None:
         self._yt_playlist = yt.get_playlist(self.id)
      return self._yt_playlist

   def write(self):
      self.full_file.seek(0)
      self.full_file.write(self.shadow_playlist.jsonl())
      self.friendly_file.seek(0)
      self.friendly_file.write(self.shadow_playlist.friendly_jsonl())


   def _init_diff(self):
      self._shadow_set: t.Set[str] = set()
      self._yt_set: t.Set[str] = set()
      self._shadow_lookup: dict[str, shadow.PlaylistItem] = {}
      self._yt_lookup: dict[str, yt.PlaylistItem] = {}
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


      for item in self.yt_playlist.items:
         smol = u.smol_hash(item.id)
         shadow_position = smol_to_shadow_position.get(smol)
         if shadow_position is not None:
            self._yt_shadow_position_forwards[item] = shadow_position
            self._yt_shadow_position_backwards[shadow_position] = item
         self._yt_set.add(smol)
         self._yt_lookup[smol] = item

   @property
   def shadow_set(self) -> t.Set[str]:
      if self._shadow_set is None:
         self._init_diff()
      return self._shadow_set

   @property
   def yt_set(self) -> t.Set[str]:
      if self._yt_set is None:
         self._init_diff()
      return self._yt_set

   @property
   def shadow_lookup(self) -> dict[str, shadow.PlaylistItem]:
      if self._shadow_lookup is None:
         self._init_diff()
      return self._shadow_lookup

   @property
   def yt_lookup(self) -> dict[str, yt.PlaylistItem]:
      if self._yt_lookup is None:
         self._init_diff()
      return self._yt_lookup

   @property
   def yt_shadow_position_forwards(self) -> dict[yt.PlaylistItem, int]:
      if self._yt_shadow_position_forwards is None:
         self._init_diff()
      return self._yt_shadow_position_forwards

   @property
   def yt_shadow_position_backwards(self) -> dict[int, yt.PlaylistItem]:
      if self._yt_shadow_position_backwards is None:
         self._init_diff()
      return self._yt_shadow_position_backwards

   @property
   def missing_yt(self) -> list[shadow.PlaylistItem]:
      return [self.shadow_lookup[smol] for smol in self.shadow_set - self.yt_set]

   @property
   def missing_shadow(self) -> list[yt.PlaylistItem]:
      return [self.yt_lookup[smol] for smol in self.yt_set - self.shadow_set]

   @property
   def diff_ok(self) -> bool:
      return len(self.missing_yt) == 0 and len(self.missing_shadow) == 0

   @property
   def ooo(self) -> list[yt.PlaylistItem]:
      if not self.diff_ok:
         raise ValueError("Cannot get out-of-order elements if the diff is not OK!")

      out_of_order_positions = u.shortest_out_of_order_sublist(
         [self.yt_shadow_position_forwards[item] for item in self.yt_playlist.items],
      )

      return [self.yt_shadow_position_backwards[pos] for pos in out_of_order_positions]

   return [Playlist(yt_playlist=p) for p in yt.my_playlists()]
