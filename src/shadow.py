# Shadow, what the fuck are you talking about?
# You're a beta male, Sonic!

import util as u
import typing as t
import yt
import log as l

from time import time

class PlaylistItem:
   """
   Incomplete PlaylistItem which contains only as much information as is in the
   friendly jsonl file.
   """

   def __init__(self, source: t.Union[str, yt.PlaylistItem], above_comment: list[str] = []):
      self.title: str
      self.channel_title: t.Optional[str]
      self.video_id: str
      self.smol_hash: str
      self.above_comment = above_comment
      self.inline_comment: t.Optional[str] = None

      if isinstance(source, yt.PlaylistItem):
         self.title = source.title
         self.channel_title = source.channel_title
         self.video_id = source.video_id
         self.smol_hash = u.smol_hash(source.id)
         return

      if isinstance(source, str):
         # source is a single line of json
         obj, more_line = u.deserialize_raw(source, tuple[str, str, str, str])
         self.title = obj[0]
         self.channel_title = obj[1]
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
      else:
         raise TypeError(f"Unexpected type {type(source)}!")

   def __repr__(self) -> str:
      return f"{self.title} - {self.channel_title}"

class Playlist:
   def __init__(self, source: t.Union[str, yt.Playlist]):
      # This can't be None because I'm only archiving my own playlists.
      # It can't be set to private!
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
      else:
         raise TypeError(f"Unexpected type {type(source)}!")


   def jsonl(self) -> str:
      cols: tuple[list[str], list[str], list[str], list[str]] = (
         [u.serialize("Video Title")],
         [u.serialize("Channel Title")],
         [u.serialize("Video ID")],
         [u.serialize("Smol Hash~")],
      )

      for i in self.items:
         cols[0].append(u.serialize(i.title))
         cols[1].append(u.serialize(i.channel_title))
         cols[2].append(u.serialize(i.video_id))
         cols[3].append(u.serialize(i.smol_hash))

      for col in cols:
         u.left_align(col)

      jsonl_out = ""
      jsonl_out += u.serialize(self.title) + "\n"
      jsonl_out += u.serialize(self.id) + "\n"
      jsonl_out += u.serialize(self.time) + "\n"

      for i in range(0, len(cols[0])):
         jsonl_out += f"[{cols[0][i]}, {cols[1][i]}, {cols[2][i]}, {cols[3][i]}]\n"

      return jsonl_out

   def friendly_jsonl(self) -> str:
      """
      Does some truncation that would otherwise not happen.
      """
      jsonl_out = ""
      jsonl_out += u.serialize(self.title) + "\n"
      jsonl_out += "".join(line + "\n" for line in self.playlist_comment)
      jsonl_out += u.serialize(self.id) + "\n"
      jsonl_out += u.serialize(self.time) + "\n"

      cols: tuple[list[str], list[str], list[str], list[str]] = ([], [], [], [])
      for i in self.items:
         _title = u.truncate(i.title, max_len=40)
         cols[0].append(u.serialize(_title))

         _channel_title = i.channel_title
         if _channel_title is not None:
            if _channel_title.endswith(" - Topic"):
               _channel_title = _channel_title[: -len(" - Topic")]
            _channel_title = u.truncate(_channel_title, max_len=20)
         cols[1].append(u.serialize(_channel_title))

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
