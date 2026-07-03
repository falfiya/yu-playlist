# Textual Representations of playlist data.
# Unfortunately it also knows the internal structure of yt, but it at least does
# not know about the filesystem.
from __future__ import annotations
import util as u
import typing as t
import log as l

import pydantic as p

import datetime

class TextPlaylistItem(p.BaseModel):
   title: str
   channel_title: t.Optional[str]
   video_id: str
   smol_hash_playlist_item_id: str
   above_comment: list[str]
   inline_comment: str

   @staticmethod
   def from_line(line: str) -> TextPlaylistItem:
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

   def __repr__(self) -> str:
      return f"{self.title} - {self.channel_title}"


class TextPlaylist(p.BaseModel):
   """
   <pre>
                                                         // overline_comments[0]
   "Playlist Title"                                      // inline_comments[0]
                                                         // overline_comments[1]
   "playlist.id"                                         // inline_comments[1]
                                                         // overline_comments[2]
   00000.0000                                            // inline_comments[2]
   ["Rich Man"  , "aespa"       , "WAQ5_7YFAVo", "73PNDXNHGL"]
   ["Aris Rage" , "BasedMonster", "zbsbcKfqtSQ", "PTZI4WR47P"]
   </pre>
   """

   id: str
   title: str
   last_jsonl_time: t.Any
   overline_comments: tuple[list[str], list[str], list[str]]
   inline_comments: tuple[str, str, str]
   items: list[TextPlaylistItem]
   trailing_comments: list[str]

   @staticmethod
   def from_str(lines: list[str]) -> TextPlaylist:
      overline_comments: list[list[str]] = [[]] * 3
      inline_comments: list[str] = [""] * 3

      overline_comments[0], lines = u.head_comments(lines)
      title, inline_comments[0] = u.deserialize_raw(lines.pop(0))

      overline_comments[1], lines = u.head_comments(lines)
      id, inline_comments[1] = u.deserialize_raw(lines.pop(0))

      overline_comments[2], lines = u.head_comments(lines)
      last_jsonl_time, inline_comments[2] = u.deserialize_raw(lines.pop(0))

      items: list[TextPlaylistItem] = []
      trailing_comments = []
      while len(lines) > 0:
         comment_above, lines = u.head_comments(lines)
         if len(lines) == 0:
            trailing_comments = comment_above
            break
         else:
            items.append(TextPlaylistItem.from_line(lines.pop(0)))

      return TextPlaylist(
         id=id,
         title=title,
         last_jsonl_time=last_jsonl_time,
         overline_comments=overline_comments, # type: ignore coerce
         inline_comments=inline_comments, # type: ignore coerce
         items=items,
         trailing_comments=trailing_comments,
      )

   def jsonl(self) -> str:
      this_jsonl_time = datetime.datetime.now().isoformat()
      jsonl_out = ""
      jsonl_out += "\n".join(self.overline_comments[0]) + "\n"
      jsonl_out += u.serialize(self.title) + self.inline_comments[0] + "\n"
      jsonl_out += "\n".join(self.overline_comments[1]) + "\n"
      jsonl_out += u.serialize(self.id) + self.inline_comments[1] + "\n"
      jsonl_out += "\n".join(self.overline_comments[2])
      jsonl_out += u.serialize(this_jsonl_time) + self.inline_comments[2] + "\n"

      cols: tuple[list[str], list[str], list[str], list[str]] = ([], [], [], [])
      for i in self.items:
         cols[0].append(u.serialize(i.title))
         cols[1].append(u.serialize(i.channel_title))
         cols[2].append(u.serialize(i.video_id))
         cols[3].append(u.serialize(i.smol_hash_playlist_item_id))

      for col in cols:
         u.left_align(col)

      for i, item in enumerate(self.items):
         jsonl_out += "".join(line + "\n" for line in item.above_comment)
         jsonl_out += f"[{cols[0][i]}, {cols[1][i]}, {cols[2][i]}, {cols[3][i]}]"
         if item.inline_comment:
            jsonl_out += item.inline_comment
         jsonl_out += "\n"

      jsonl_out += "\n".join(self.trailing_comments) + "\n"
      return jsonl_out
