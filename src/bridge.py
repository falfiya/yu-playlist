# Bridge between filesystem, shadow, and YouTube
import typing as t
import shadow
import util as u
import yt

from time import time
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
      self.shadow_playlist: t.Optional[shadow.Playlist] = None

      if yt_playlist is None and friendly_filepath is None:
         raise ValueError("Both cannot be None!")

      if yt_playlist is not None:
         self.id = yt_playlist.id
         self.full_file = u.oopen(f"playlists/full/{yt_playlist.id}.jsonl")
         if friendly_filepath is None:
            self.friendly_file = u.oopen(f"playlists/{sanitize_filename(yt_playlist.title)} - {u.smol_hash(self.id)}.jsonl")
         self._yt_playlist = yt_playlist

      if friendly_filepath is not None:
         self.friendly_file = u.oopen(friendly_filepath)

      try:
         self.shadow_playlist = shadow.Playlist(self.friendly_file.readlines())
      except Exception:
         # Couldn't parse the shadow file. Let's write another one.
         self.friendly_file.write(self.friendly_jsonl())

   def close(self):
      if self.full_file:
         self.full_file.close()
      self.friendly_file.close()

   @property
   def yt_playlist(self) -> yt.Playlist:
      if self._yt_playlist is None:
         self._yt_playlist = yt.get_playlist(self.id)
      return self._yt_playlist

   def jsonl(self) -> str:
      cols: tuple[list[str], list[str], list[str], list[str]] = (
         [u.serialize("Video Title")],
         [u.serialize("Channel Name")],
         [u.serialize("Video ID")],
         [u.serialize("Playlist Item ID")],
      )
      items = self.yt_playlist.items
      epoch = time()
      for i in items:
         cols[0].append(u.serialize(i.title))
         cols[1].append(u.serialize(i.channel_title))
         cols[2].append(u.serialize(i.video_id))
         cols[3].append(u.serialize(i.id))
      for col in cols:
         u.left_align(col)

      info = {
         "playlist_id": self.id,
         "last_updated_unix": epoch,
      }

      jsonl_out = ""
      jsonl_out += u.serialize(self.yt_playlist.title) + "\n"
      jsonl_out += u.serialize(info) + "\n"
      for i in range(0, len(items)):
         jsonl_out += f"[{cols[0][i]}, {cols[1][i]}, {cols[2][i]}, {cols[3][i]}]\n"

      return jsonl_out

   def friendly_jsonl(self) -> str:
      cols: tuple[list[str], list[str], list[str], list[str]] = (
         [u.serialize("Title")],
         [u.serialize("Channel")],
         [u.serialize("Video ID")],
         [u.serialize("Smol Hash~")],
      )
      for i in self.yt_playlist.items:
         _title = u.truncate(i.title, max_len=40)
         cols[0].append(u.serialize(_title))

         _channel_title = i.channel_title
         if _channel_title is not None:
            if _channel_title.endswith(" - Topic"):
               _channel_title = _channel_title[: -len(" - Topic")]
            _channel_title = u.truncate(_channel_title, max_len=20)
         cols[1].append(u.serialize(_channel_title))

         cols[2].append(u.serialize(i.video_id))

         cols[3].append(u.serialize(u.smol_hash(i.id)))

      for col in cols:
         u.left_align(col)

      jsonl_out = ""
      jsonl_out += u.serialize(self.yt_playlist.title) + "\n"
      jsonl_out += u.serialize(self.id) + "\n"
      for i in range(0, len(cols[0])):
         jsonl_out += f"[{cols[0][i]}, {cols[1][i]}, {cols[2][i]}, {cols[3][i]}]\n"

      return jsonl_out

def my_playlists() -> list[Playlist]:
   return [Playlist(yt_playlist=p) for p in yt.my_playlists()]
