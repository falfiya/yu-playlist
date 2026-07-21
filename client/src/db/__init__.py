import hashlib
import os
import re
import typing as t
from pathlib import Path

import apsw
import apsw.bestpractice
import pydantic as p
import zstd
import time
import config

apsw.bestpractice.apply(apsw.bestpractice.recommended)

################################################################################
## Migration Support
INIT = """
pragma foreign_keys = on;
create table if not exists __migration(
   id integer primary key,
   name text not null,
   md5hash text not null
) strict;
"""

AppliedMigrationRow: t.TypeAlias = tuple[int, str, str]

CLOSE = """
pragma analysis_limit=400;
pragma optimize;
"""


class MigrationOnDisk(t.NamedTuple):
   @staticmethod
   def all() -> list[MigrationOnDisk]:
      re_migration_format = re.compile(r"(\d+)_(\w+)\.sql")
      migration_dir = Path(__file__).parent / "migrations"
      stuff_in_migration_dir = [
         (m, re_migration_format.fullmatch(m)) for m in os.listdir(migration_dir)
      ]

      out_objs = []
      for path, match in stuff_in_migration_dir:
         if match is None:
            continue
         f = open(migration_dir / path, "rb")
         buf = f.read()
         out_objs.append(
            MigrationOnDisk(
               id=int(match.group(1)),
               name=match.group(2),
               md5hash=hashlib.md5(buf).hexdigest(),
               content=buf.decode("utf-8"),
            )
         )
      return out_objs

   id: int
   name: str
   md5hash: str
   content: str

################################################################################
## Database API
class ClientDatabase:
   """
   Opens the database, runs migration, and hooks up Python bindings
   """

   def __init__(self, *, path: str, config: config.ClientConfig):
      self.config = config
      self.f = open(path, "r+b")
      raw = self.f.read()
      self.conn = apsw.Connection(":memory:")
      if len(raw) != 0:
         decoded = zstd.decode(raw)
         self.conn.deserialize("main", decoded)
      self.conn.execute(INIT)
      self.__run_migrations()

   def close(self):
      self.conn.execute(CLOSE)
      self.conn.close()

   def add_playlist_snapshot(self, s: InsertablePlaylistSnapshot):
      epoch = int(time.time())
      self.conn.execute("begin immediate transaction")
      intern_map = self._add_strings(s.strings() + [self.config.device_name])
      _snapshot = _InsertablePlaylistSnapshot2.upgrade(s, map=intern_map, device_name=self.config.device_name)

      self._add_playlist(epoch, _snapshot.playlist)
      self._add_channels(epoch, _snapshot.channels)
      self._add_videos(epoch, _snapshot.videos)
      self._add_playlist_items(epoch, _snapshot.items)
      self.conn.execute("end transaction")

   def __run_migrations(self):
      """
      Migrations are written as migrations/00_name.sql and must increase
      sequentially without skipping any numbers.

      This is pretty delicate code and it's very important we get it right on
      the first try.

      "If it's so important, you should write tests for it", you sagely opine. <br>
      "dont wanna", said the developer. <br>
      "tests are for stupid people", the developer continued <br>
      "But-but... then you can confirm that it works!".
      You feel suddenly ill. <br>
      "i am not a stupid people!", the developer seemed sure of this fact <br>
      """
      applied_migration_rows = p.TypeAdapter(list[AppliedMigrationRow]).validate_python(
         self.conn.execute("select id, name, md5hash from __migration;").fetchall()
      )
      applied_migrations: dict[int, tuple[str, str]] = {}
      for id, name, md5hash in applied_migration_rows:
         assert id not in applied_migrations, f"Duplicate migration id {id}"
         applied_migrations[id] = (name, md5hash)

      migrations_on_disk: dict[int, MigrationOnDisk] = {}
      for m in MigrationOnDisk.all():
         migrations_on_disk[m.id] = m

      prevent_already_applied_migrations = False
      for id in range(0, len(migrations_on_disk)):
         if id in applied_migrations:
            assert not prevent_already_applied_migrations, (
               f"SANITY: The previous migration {id - 1} was not applied, yet somehow {id} was!"
            )
            # Confirm that it's the same migration
            applied_name, applied_md5hash = applied_migrations[id]
            # Confirm that it exists on disk still
            assert id in migrations_on_disk, (
               f"Missing migration {id}_{applied_name}.sql"
            )
            on_disk = migrations_on_disk[id]
            assert applied_name == on_disk.name, (
               f"Migration {id} was applied as {applied_name} but now has {on_disk.name}"
            )
            assert applied_md5hash == on_disk.md5hash, (
               f"Migration {id} ({applied_name}) previously had md5={applied_md5hash} but now has md5={on_disk.md5hash}"
            )
         elif id in migrations_on_disk:
            # We need to apply the migration.
            # Additionally, all migrations from here on out should not be applied either.
            # Let me illustrate this visually:
            #
            # disk: [a] [b] [c]
            # db  : [a]  o
            #            o
            #            ooooooooooooooooooooo we are here.
            #
            prevent_already_applied_migrations = True
            # This is the kind of situation we want to prevent:
            #
            # disk: [a] [b] [c]
            # db  : [a]     [c]
            #
            # What's in that missing gap?
            # Surely this could have never happened because I didn't write the code like this.
            # We do count up sequentially so this should never be the case.
            # But I'm nothing if not careful here, and a careless programming mistake could lead to
            # something really awful happening. Let us ensure that this never happens.
            to_apply = migrations_on_disk[id]
            with self.conn:
               self.conn.execute(to_apply.content)
               self.conn.execute(
                  "insert into __migration(id, name, md5hash) values (?, ?, ?)",
                  (to_apply.id, to_apply.name, to_apply.md5hash),
               )
         else:
            raise AssertionError(f"Missing migration {id}")

   def _add_strings(self, strings: list[str]) -> StringInternMap:
      rows = p.TypeAdapter(list[tuple[int]]).validate_python(
         self.conn.executemany(
            "insert into string(value) values (?) "
            "on conflict (value) do update set value = value "
            "returning id",
            strings
         ).fetchall())
      handles = {}
      for (s, row) in zip(strings, rows):
         handles[s] = row[0]
      return handles

   def _add_playlist(self, epoch: int, playlist: _InsertablePlaylist2):
      """
      Only adds the playlist content.
      """
      ex_id = p.TypeAdapter(tuple[int]).validate_python(
         self.conn.execute(
            "insert into playlist_ex(title, desc) values (?, ?) "
            "on conflict (title, desc) do update set title = title "
            "returning ex_id",
            (playlist.title, playlist.desc),
         ).fetchone()
      )
      self.conn.execute(
         "insert or ignore into playlist_at(epoch, playlist_id, device, ex) "
         "values (?, ?, ?, ?)",
         (epoch, playlist.playlist_id, playlist.device_name, ex_id[0])
      )

   def _add_channels(self, epoch: int, channels: list[_InsertableChannel2]):
      ex_ids = p.TypeAdapter(list[tuple[int]]).validate_python(
         self.conn.executemany(
            "insert into channel_ex(title) values (?) "
            # You're probably wondering what this is for. Let me explain.
            # * judelow music starts playing *
            # The returning clause only works if the row is actually written to.
            # Ordinarily we'd want insert or ignore, but ignore unfortunately
            # returns None in the case that the row was already there!
            # Therefore we perform a no-op update.
            # And that's how
            "on conflict (title) do update set title = title "
            "returning id",
            ((channel.title,) for channel in channels)
         ).fetchall()
      )

      self.conn.executemany(
         "insert or ignore into channel_at(epoch, id, ex) values (?, ?, ?) ",
         ((epoch, channel.channel_id, ex_id)
            for channel, (ex_id,) in zip(channels, ex_ids))
      )

   def _add_videos(self, epoch: int, videos: list[_InsertableVideo2]):
      ex_ids = p.TypeAdapter(list[tuple[int]]).validate_python(
         self.conn.executemany(
            "insert into video_ex(owner, title) values(?, ?) "
            "on conflict (owner, title) do update set title = title "
            "returning ex_id",
            ((video.owner_id, video.title) for video in videos)
         ).fetchall()
      )

      self.conn.executemany(
         "insert or ignore into video_at(epoch, id, ex) values (?, ?, ?)",
         ((epoch, video.video_id, ex_id)
            for video, (ex_id,) in zip(videos, ex_ids))
      )

   def _add_playlist_items(self, epoch: int, items: list[_InsertablePlaylistItem2]):
      self.conn.executemany(
         "insert or ignore into playlist_item(id, video_id, playlist_id) "
         "values (?, ?, ?)",
         ((item.playlist_item_id, item.video_id, item.playlist_id) for item in items),
      )

      self.conn.executemany(
         "insert or ignore into playlist_item_at(epoch, playlist_item_id, position) "
         "values (?, ?, ?)",
         ((epoch, item.playlist_item_id, item.position) for item in items),
      )

################################################################################
## External API Structures (they closely match what the yt-api gives us!)
class InsertablePlaylistSnapshot(t.NamedTuple):
   id: str
   title: str
   desc: str
   items: list[InsertablePlaylistItem]
   def strings(self) -> list[str]:
      return [self.id, self.title, *(s for item in self.items for s in item.strings())]

class InsertablePlaylistItem(t.NamedTuple):
   """
   Must be the same as parent InsertablePlaylistSnapshot
   """
   # PlaylistItem ids are globally unique across playlists and durable
   id: str
   playlist_id: str
   """
   Must be the same as parent InsertablePlaylistSnapshot
   """
   video_id: str
   video_title: str
   video_owner_channel_id: str
   video_owner_channel_title: str
   position: int
   def strings(self) -> list[str]:
      return [
         self.id,
         self.playlist_id,
         self.video_id,
         self.video_title,
         self.video_owner_channel_id,
         self.video_owner_channel_title
      ]

################################################################################
## Internal API Structures
# These more closely match what's going on in the database.
# They reflect the string interning and split a playlist item from its video and
# videos from their channel owner
StringHandle: t.TypeAlias = int
StringInternMap: t.TypeAlias = dict[str, StringHandle]

class _InsertablePlaylistSnapshot2(t.NamedTuple):
   playlist: _InsertablePlaylist2
   channels: list[_InsertableChannel2]
   videos: list[_InsertableVideo2]
   items: list[_InsertablePlaylistItem2]
   @staticmethod
   def upgrade(a: InsertablePlaylistSnapshot, map: StringInternMap, device_name: str) -> _InsertablePlaylistSnapshot2:
      return _InsertablePlaylistSnapshot2(
         playlist=_InsertablePlaylist2(
            playlist_id=map[a.id],
            device_name=map[device_name],
            title=map[a.title],
            desc=map[a.desc],
         ),
         channels=[
            # This may contain duplicates. That's OK! Let SQLite3 handle them for us.
            _InsertableChannel2(
               channel_id=map[item.video_owner_channel_id],
               title=map[item.video_owner_channel_title],
            ) for item in a.items
         ],
         videos=[
            _InsertableVideo2(
               video_id=map[item.video_id],
               owner_id=map[item.video_owner_channel_id],
               title=map[item.video_title],
            ) for item in a.items
         ],
         items=[
            # This one should not contain duplicates though
            _InsertablePlaylistItem2(
               playlist_item_id=map[item.id],
               video_id=map[item.video_id],
               playlist_id=map[item.playlist_id],
               position=item.position
            ) for item in a.items
         ],
      )

class _InsertablePlaylist2(t.NamedTuple):
   """
   Represents tables playlist_at & playlist_ex
   """
   playlist_id: StringHandle
   device_name: StringHandle
   title: StringHandle
   desc: StringHandle

class _InsertableChannel2(t.NamedTuple):
   """
   Represents tables channel_at & channel_ex
   """
   channel_id: int
   title: int

class _InsertableVideo2(t.NamedTuple):
   """
   Represents tables video_at & video_ex
   """
   video_id: StringHandle
   owner_id: StringHandle
   """
   Channel Id of where this video was posted
   """
   title: StringHandle

class _InsertablePlaylistItem2(t.NamedTuple):
   """
   Represents tables playlist_item & playlist_ex
   """
   # Worth commenting on the Hungarian Notation here.
   # InsertablePlaylistItem has id
   # table playlist_item_at has id
   # Why, then, does _InsertablePlaylistItem2 write playlist_item_id instead of id?
   #
   # I don't know. It felt correct. I feel that these internal structures should
   # make sure to qualify what type of identifier they point to.
   playlist_item_id: StringHandle
   video_id: StringHandle
   playlist_id: StringHandle
   position: int
