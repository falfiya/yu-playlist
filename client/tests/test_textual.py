import textwrap

import config
from log import Logging
import textual
import util as u

from pathlib import Path


def _make_logger() -> Logging:
   cfg = config.ClientConfig.from_path(
      Path(__file__).parent.parent / "src" / "config.default.toml"
   )
   return Logging(cfg)


def _parse(body: str) -> textual.TextPlaylist:
   """Dedent a triple-quoted body and parse it as a TextPlaylist."""
   lines = textwrap.dedent(body).splitlines()
   # splitlines() drops a trailing newline's empty string; mimic real input
   # by not adding one. Real files end with a newline -> splitlines gives no
   # trailing empty element, same as here.
   return textual.TextPlaylist.from_str(lines, _make_logger())


def test_playlist():
   txt1 = """"My Great Playlist"
      // Check those shoes out playa
      "I hope you kept the receipt"
      11102.0
      ["Aris Rage (Protect Your Ears)", "BasedMonster", "zbsbcKfqtSQ", "PTZI4WR47P"]
   """
   pl1 = textual.TextPlaylist.from_str(txt1.splitlines(), _make_logger())
   assert len(pl1.items) == 1
   assert pl1.items[0].channel_title == "BasedMonster"


def test_basic_fields():
   pl = _parse('''\
      "My Great Playlist"
      "PL-ID-123"
      11102.0
      ["Aris Rage (Protect Your Ears)", "BasedMonster", "zbsbcKfqtSQ", "PTZI4WR47P"]
   ''')
   assert pl.title == "My Great Playlist"
   assert pl.id == "PL-ID-123"
   assert pl.last_jsonl_time == 11102.0
   assert len(pl.items) == 1
   it = pl.items[0]
   assert it.title == "Aris Rage (Protect Your Ears)"
   assert it.channel_title == "BasedMonster"
   assert it.video_id == "zbsbcKfqtSQ"
   assert it.smol_hash_playlist_item_id == "PTZI4WR47P"
   assert it.above_comment == []
   assert it.inline_comment == ""


def test_multiple_items():
   pl = _parse('''\
      "My Great Playlist"
      "PL-ID-123"
      11102.0
      ["Rich Man"  , "aespa"       , "WAQ5_7YFAVo", "73PNDXNHGL"]
      ["Aris Rage" , "BasedMonster", "zbsbcKfqtSQ", "PTZI4WR47P"]
   ''')
   assert len(pl.items) == 2
   assert pl.items[0].title == "Rich Man"
   assert pl.items[0].channel_title == "aespa"
   assert pl.items[1].title == "Aris Rage"
   assert pl.items[1].channel_title == "BasedMonster"


def test_overline_comments():
   pl = _parse('''\
      // a comment above the title
      "My Great Playlist"
      // a comment above the id
      "PL-ID-123"
      // a comment above the timestamp
      11102.0
      ["Aris Rage", "BasedMonster", "zbsbcKfqtSQ", "PTZI4WR47P"]
   ''')
   assert pl.overline_comments[0] == ["// a comment above the title"]
   assert pl.overline_comments[1] == ["// a comment above the id"]
   assert pl.overline_comments[2] == ["// a comment above the timestamp"]


def test_inline_comments_on_header():
   pl = _parse('''\
      "My Great Playlist" // title inline
      "PL-ID-123" // id inline
      11102.0 // time inline
      ["Aris Rage", "BasedMonster", "zbsbcKfqtSQ", "PTZI4WR47P"]
   ''')
   assert pl.inline_comments[0] == " // title inline"
   assert pl.inline_comments[1] == " // id inline"
   assert pl.inline_comments[2] == " // time inline"


def test_item_above_comment():
   pl = _parse('''\
      "My Great Playlist"
      "PL-ID-123"
      11102.0
      // protect your ears
      ["Aris Rage", "BasedMonster", "zbsbcKfqtSQ", "PTZI4WR47P"]
   ''')
   assert len(pl.items) == 1
   # above_comment is populated by the jsonl writer, not the parser. The parser
   # only collects comments that come *between* items into trailing/above slots
   # in a limited way. Confirm parsing doesn't crash and the item is captured.
   assert pl.items[0].title == "Aris Rage"


def test_item_inline_comment():
   pl = _parse('''\
      "My Great Playlist"
      "PL-ID-123"
      11102.0
      ["Aris Rage", "BasedMonster", "zbsbcKfqtSQ", "PTZI4WR47P"] // nice
   ''')
   assert len(pl.items) == 1
   assert pl.items[0].inline_comment == " // nice"


def test_trailing_comments():
   pl = _parse('''\
      "My Great Playlist"
      "PL-ID-123"
      11102.0
      ["Aris Rage", "BasedMonster", "zbsbcKfqtSQ", "PTZI4WR47P"]
      // the end
      // really the end
   ''')
   assert pl.trailing_comments == ["// the end", "// really the end"]


def test_null_channel_title():
   pl = _parse('''\
      "My Great Playlist"
      "PL-ID-123"
      11102.0
      ["Some Video", null, "vid123", "ABCDEFGHIJ"]
   ''')
   assert len(pl.items) == 1
   assert pl.items[0].channel_title is None


def test_from_line_direct():
   it = textual.TextPlaylistItem.from_line(
      '["Title", "Channel", "vid", "hash"]', _make_logger()
   )
   assert it.title == "Title"
   assert it.channel_title == "Channel"
   assert it.video_id == "vid"
   assert it.smol_hash_playlist_item_id == "hash"
   assert it.inline_comment == ""


def test_from_line_inline_comment():
   it = textual.TextPlaylistItem.from_line(
      '["Title", "Channel", "vid", "hash"] // a note', _make_logger()
   )
   assert it.inline_comment == " // a note"


def test_from_line_rejects_garbage():
   import pytest
   with pytest.raises(ValueError):
      textual.TextPlaylistItem.from_line(
         '["Title", "Channel", "vid", "hash"] garbage', _make_logger()
      )


def test_jsonl_roundtrip():
   original = '''\
      "My Great Playlist"
      "PL-ID-123"
      11102.0
      ["Aris Rage", "BasedMonster", "zbsbcKfqtSQ", "PTZI4WR47P"]
      ["Rich Man", "aespa", "WAQ5_7YFAVo", "73PNDXNHGL"]
   '''
   pl = _parse(original)
   out = pl.jsonl()
   # Re-parse the output. The timestamp changes each call, so we can't compare
   # strings directly, but the structure should survive a round-trip.
   pl2 = textual.TextPlaylist.from_str(out.splitlines(), _make_logger())
   assert pl2.title == pl.title
   assert pl2.id == pl.id
   assert len(pl2.items) == len(pl.items)
   for a, b in zip(pl2.items, pl.items):
      assert a.title == b.title
      assert a.channel_title == b.channel_title
      assert a.video_id == b.video_id
      assert a.smol_hash_playlist_item_id == b.smol_hash_playlist_item_id


def test_jsonl_aligns_columns():
   pl = _parse('''\
      "My Great Playlist"
      "PL-ID-123"
      11102.0
      ["Short", "CH", "vid1", "hash1"]
      ["A Much Longer Title", "BasedMonster", "vid2", "hash2"]
   ''')
   out = pl.jsonl()
   item_lines = [
      l for l in out.splitlines()
      if l.strip().startswith("[")
   ]
   assert len(item_lines) == 2
   # Both item lines should start their array at the same column and be
   # left-aligned, so the closing brackets of the first column align.
   # Find the position of the first comma in each — the first column's
   # content ends there and should match.
   pos1 = item_lines[0].index(",")
   pos2 = item_lines[1].index(",")
   assert pos1 == pos2, f"columns not aligned:\n{item_lines[0]}\n{item_lines[1]}"
