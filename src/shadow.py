# Shadow, what the fuck are you talking about?
# You're a beta male, Sonic!

import util as u
import typing as t
import yt

from time import time

class PlaylistItem:
   """
   Incomplete PlaylistItem which contains only as much information as is in the
   friendly jsonl file.
   """

   def __init__(self, source: t.Union[str, yt.PlaylistItem], above_comment: list[str] = []):
      self.title: str
      self.channel_name: t.Optional[str]
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
         self.channel_name = obj[1]
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

      raise TypeError(f"Unexpected type {type(source)}!")

   def __repr__(self) -> str:
      return f"{self.title}#{self.video_id}"



class Playlist:
   """
   The Playlist file that we are going to try to mirror.
   """

   def __init__(self, source: t.Union[t.Sequence[str], yt.Playlist]):
      # This can't be None because I'm only archiving my own playlists.
      # It can't be set to private!
      self.title: str
      self.title_comment: list[str] = []

      self.id: str
      self.id_comment: list[str] = []

      self.time: float
      self.time_comment: list[str] = []

      self.items: list[PlaylistItem] = []
      if isinstance(source, yt.Playlist):
         self.time = time()
         self.title = source.title
         self.id = source.id
         self.items = [PlaylistItem(item) for item in source.items]
         return

      # thank you, Guido van Rossum
      #if isinstance(source, t.Sequence[str]):
      # source is jsonl

      lines_and_comments: list[tuple[str, list[str]]] = []
      comment_above = []
      for line in source:
         line = line.strip()

         if line == "":
            continue

         if line.startswith("//"):
            comment_above.append(line)
            continue

         lines_and_comments.append((line, comment_above))
         comment_above = []

      raw_title, title_comment = lines_and_comments.pop(0)
      title = u.deserialize(raw_title)
      if not isinstance(title, str):
         raise ValueError("Title must be a string!")
      self.title: str = title
      self.title_comment = title_comment

      raw_id, id_comment = lines_and_comments.pop(0)
      id_ = u.deserialize(raw_id)
      if not isinstance(id_, str):
         raise ValueError("id must be a string!")
      self.id: str = id_
      self.id_comment = id_comment

      raw_time, time_comment = lines_and_comments.pop(0)
      time_ = u.deserialize(raw_time)
      if not isinstance(time_, float):
         raise ValueError("id must be a string!")
      self.time: float = time_
      self.time_comment = time_comment

      self.items = [PlaylistItem(line, comment_above) for line, comment_above in lines_and_comments]
