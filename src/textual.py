# Textual Representations of playlist data.
# Unfortunately it also knows the internal structure of yt, but it at least does
# not know about the filesystem.
from __future__ import annotations
import util as u
import typing as t
import yt
import log as l

from time import time

class Video:
   def __init__(self, source: t.Union[str, yt.PlaylistItem]):
      self.id: str
      self.title: str
      self.channel_title: t.Optional[str]

      if isinstance(source, yt.PlaylistItem):
         self.id = source.video_id
         self.title = source.title
         self.channel_title = source.channel_title
         return

      if isinstance(source, str):
         try:
            obj, more_line = u.deserialize_raw(source, tuple[str, str, str, str])
         except u.JSONDecodeError as e:
            l.error("Failed to decode video jsonl!")
            l.group_start()
            l.info(source)
            l.group_end()
            raise e

         self.id = obj[0]
         self.title = obj[1]
         self.channel_title = obj[2]

         if more_line != "":
            raise ValueError(f"Uninterpreted text near {u.serialize(source)}!")

         return

      raise TypeError(f"SANITY: Unexpected {type(source)}")

   def update(self, new: Video):
      self.title = new.title
      self.channel_title = new.channel_title

   def jsonl(self) -> str:
      return u.serialize([self.id, self.title, self.channel_title])

class Videos:
   def __init__(self, source: t.Union[str, list[yt.PlaylistItem]] = []):
      """
      Either the jsonl of the .videos.jsonl, or a list of all PlaylistItems.
      """
      self._order: list[Video] = []
      self._lookup: t.Dict[str, Video] = {}

      if isinstance(source, list):
         self._add(map(Video, source))
         return

      if isinstance(source, str):
         self._add(map(Video, source.splitlines()))
         return

      raise TypeError(f"SANITY: Unexpected {type(source)}")

   def _add(self, videos: t.Iterator[Video]):
      for video in videos:
         if video.id in self._lookup:
            self._lookup[video.id].update(video)
         self._lookup[video.id] = video
         self._order.append(video)

   def add(self, source: list[yt.PlaylistItem]):
      self._add(map(Video, source))

   def __getitem__(self, key: int | str):
      if isinstance(key, int):
         return self._order[key]

      if isinstance(key, str):
         return self._lookup[key]

      raise TypeError(f"SANITY: Unexpected {type(key)}")

   def __delitem__(self, key: int | str) -> None:
      if isinstance(key, int):
         del self._lookup[self._order[key].id]
         del self._order[key]
         return

      if isinstance(key, str):
         self._order.remove(self._lookup[key])
         del self._lookup[key]
         return

      raise TypeError(f"SANITY: Unexpected {type(key)}")

   def jsonl(self) -> str:
      return "\n".join(v.jsonl() for v in self._order) + "\n"

class PlaylistItem:
   """
   Incomplete PlaylistItem which contains only as much information as is in the
   friendly jsonl file.
   """

   def __init__(self, source: t.Union[str, yt.PlaylistItem], above_comment: list[str] = []):
      # Depending on how the object is made, these strings may not be known.
      # Instead, a friendly title and friendly channel_title will be known, and do not require truncation.
      self.title: t.Optional[str] = None
      self.channel_title: t.Optional[str] = None

      # The friendly strings can be created from the normal strings, but not the other way around.
      self.friendly_title: str
      self.friendly_channel_title: t.Optional[str] = None
      """
      Annoyingly, sometimes the channel_title proper is None, so it poisons the friendly_channel_title.
      """

      self.video_id: str
      self.smol_hash: str
      self.above_comment = above_comment

      self.inline_comment: t.Optional[str] = None
      """
      If a friendly playlist source file was passed in, then there was a potential comment here, in which case the comment will be "".
      Otherwise, it will be left as None, signifying that it's unknown if there was a comment.
      """

      if isinstance(source, yt.PlaylistItem):
         self.title = source.title
         self.channel_title = source.channel_title
         self.friendly_title = u.truncate(source.title, max_len=40)

         self.friendly_channel_title = self.channel_title
         if self.friendly_channel_title is not None:
            if self.friendly_channel_title.endswith(" - Topic"):
               self.friendly_channel_title = self.friendly_channel_title[: -len(" - Topic")]
            self.friendly_channel_title = u.truncate(self.friendly_channel_title, max_len=20)

         self.video_id = source.video_id
         self.smol_hash = u.smol_hash(source.id)

         return

      if isinstance(source, str):
         # source is a single line of json
         try:
            obj, more_line = u.deserialize_raw(source, tuple[str, str, str, str])
         except u.JSONDecodeError as e:
            l.error("Failed to decode shadow playlist line!")
            l.group_start()
            l.info(source)
            l.group_end()
            raise e
         self.friendly_title = obj[0]
         self.friendly_channel_title = obj[1]
         self.video_id = obj[2]
         self.smol_hash = obj[3]

         more_line2 = more_line.strip()
         if len(more_line2) == 0:
            # it was all whitespace
            self.inline_comment = ""
         elif more_line2.startswith("//"):
            self.inline_comment = more_line
         else:
            raise ValueError(f"Unexpected text {u.serialize(more_line2)} after {self.title}!")

         return

      raise TypeError(f"SANITY: Unexpected {type(source)}")


   def preserve_comments_from(self, prev: PlaylistItem):
      self.above_comment = prev.above_comment
      self.inline_comment = prev.inline_comment

   def __repr__(self) -> str:
      return f"{self.title} - {self.channel_title}"

class Playlist:
   def __init__(self, source: t.Union[str, yt.Playlist]):
      """
      If you're initializing this with a yt.Playlist, you're probably only looking for the .jsonl
      functionality so that you can immediately write out to disk.
      """
      self.title: str
      self.playlist_comment: list[str] = []
      self.id: str
      self.time: float

      self.items: list[PlaylistItem] = []
      if isinstance(source, yt.Playlist):
         self.time = time()
         self.title = source.title
         self.id = source.id
         self.items = [PlaylistItem(item) for item in source.items]
         return

      if isinstance(source, str):
         jsonl = [line.strip() for line in source.splitlines()]

         title = u.deserialize(jsonl.pop(0))
         if not isinstance(title, str):
            raise ValueError("Title must be a string!")
         self.title: str = title

         # I will allow a playlist comment on the second line.
         while jsonl[0].startswith("//"):
            self.playlist_comment.append(jsonl.pop(0))

         id_ = u.deserialize(jsonl.pop(0))
         if not isinstance(id_, str):
            raise ValueError("id must be a string!")
         self.id: str = id_

         time_ = u.deserialize(jsonl.pop(0))
         if not isinstance(time_, float):
            raise ValueError("time must be a float!")
         self.time: float = time_

         lines_and_comments: list[tuple[str, list[str]]] = []
         comment_above = []
         for line in jsonl:
            line = line.strip()

            if line == "":
               continue

            if line.startswith("//"):
               comment_above.append(line)
               continue

            lines_and_comments.append((line, comment_above))
            comment_above = []

         self.items = [PlaylistItem(line, comment_above) for line, comment_above in lines_and_comments]
         return

      raise TypeError(f"SANITY: Unexpected type {type(source)}")

   def jsonl(self) -> str:
      jsonl_out = ""
      jsonl_out += u.serialize(self.title) + "\n"
      jsonl_out += "".join(line + "\n" for line in self.playlist_comment)
      jsonl_out += u.serialize(self.id) + "\n"
      jsonl_out += u.serialize(self.time) + "\n"

      cols: tuple[list[str], list[str], list[str], list[str]] = ([], [], [], [])
      for i in self.items:
         cols[0].append(u.serialize(i.friendly_title))
         cols[1].append(u.serialize(i.friendly_channel_title))
         cols[2].append(u.serialize(i.video_id))
         cols[3].append(u.serialize(i.smol_hash))

      for col in cols:
         u.left_align(col)

      for i, item in enumerate(self.items):
         jsonl_out += "".join(line + "\n" for line in item.above_comment)
         jsonl_out += f"[{cols[0][i]}, {cols[1][i]}, {cols[2][i]}, {cols[3][i]}]"
         if item.inline_comment:
            jsonl_out += item.inline_comment
         jsonl_out += "\n"

      return jsonl_out
