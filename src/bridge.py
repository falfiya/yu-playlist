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

   def close(self):
      if self.full_file:
         self.full_file.close()
      self.friendly_file.close()

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

def my_playlists() -> list[Playlist]:
   return [Playlist(yt_playlist=p) for p in yt.my_playlists()]
