# Textual Representations of playlist data.
# Unfortunately it also knows the internal structure of yt, but it at least does
# not know about the filesystem.
from __future__ import annotations
import util as u
import typing as t
import log as l

from time import time


class TextPlaylistItem:
   @staticmethod
   def from_line(line: str):
      # source is a single line of json
      try:
         obj, more_line = u.deserialize_raw(line, tuple[str, t.Optional[str], str, str])
      except u.JSONDecodeError as e:
         l.error("Failed to decode shadow playlist line!")
         l.group_start()
         l.info(line)
         l.group_end()
         raise e
      [title, channel_title, video_id, smol_hash] = obj

      more_line2 = more_line.strip()
      if len(more_line2) == 0:
         # it was all whitespace
         inline_comment = ""
      elif more_line2.startswith("//"):
         inline_comment = more_line
      else:
         raise ValueError(f"Unexpected text {u.serialize(more_line2)} after {title}!")

      return TextPlaylistItem(
         title=title,
         channel_title=channel_title,
         video_id=video_id,
         smol_hash_playlist_item_id=smol_hash,
         above_comment=[],
         inline_comment=inline_comment,
      )

   def __init__(
      self,
      *,
      title: str,
      channel_title: t.Optional[str],
      video_id: str,
      smol_hash_playlist_item_id: str,
      above_comment: list[str],
      inline_comment: str,
   ):
      self.title = title
      self.channel_title = channel_title
      self.video_id = video_id
      self.smol_hash = smol_hash_playlist_item_id
      self.above_comment = above_comment
      self.inline_comment = inline_comment

   def __repr__(self) -> str:
      return f"{self.title} - {self.channel_title}"


class TextPlaylist:
   def __init__(self, *,
                title: str,
                source: t.Union[str, yt.Playlist]):
      """
      If you're initializing this with a yt.Playlist, you're probably only looking for the .jsonl
      functionality so that you can immediately write out to disk.
      """
      self.title: str
      self.playlist_comment: list[str] = []
      self.id: str
      self.time: float

      self.items: list[TextPlaylistItem] = []
      if isinstance(source, yt.Playlist):
         self.time = time()
         self.title = source.title
         self.id = source.id
         self.items = [TextPlaylistItem(item) for item in source.items]
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

         self.items = [
            TextPlaylistItem(line, comment_above)
            for line, comment_above in lines_and_comments
         ]
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
