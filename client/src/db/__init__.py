import hashlib
import os
import re
import typing as t
from pathlib import Path

import apsw
import apsw.bestpractice
import pydantic as p
import zstd

INIT = """
pragma foreign_keys = on;
create table if not exists __migrations(
   id integer primary key,
   name text not null,
   md5hash text not null
) strict;
"""

AppliedMigrationRow = tuple[int, str, str]

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
         f = open(path, "rb")
         buf = f.read()
         out_objs.append(
            MigrationOnDisk(
               id=int(match.group(1)),
               name=match.group(2),
               md5hash=hashlib.md5(buf).hexdigest(),
               content=str(buf),
            )
         )
      return out_objs

   id: int
   name: str
   md5hash: str
   content: str


apsw.bestpractice.apply(apsw.bestpractice.recommended)


class ClientDatabase:
   """
   Opens the database, runs migration, and hooks up Python bindings
   """

   def __init__(self, path: str):
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

   def add_playlist_item(self):
      ...

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
      rows = self.conn.execute("select (id, name, md5hash) from __migrations;").fetchall()
      applied_migration_rows = p.TypeAdapter(list[AppliedMigrationRow]).validate_python(
         rows
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
                  "insert into __migrations(id, name, md5hash) values (?, ?, ?)",
                  (to_apply.id, to_apply.name, to_apply.md5hash),
               )
         else:
            raise AssertionError(f"Missing migration {id}")
