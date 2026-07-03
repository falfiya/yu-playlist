import sqlite3
import zstd
import os
from pathlib import Path
import typing as t

import hashlib
import re

INIT = """
pragma foreign_keys = on;
create table if not exists __migrations(
   id integer primary key,
   name text not null,
   md5hash text not null
) strict;
"""

CLOSE = """
pragma analysis_limit=400;
pragma optimize;
"""

class Migration(t.NamedTuple):
   @staticmethod
   def all() -> list[Migration]:
      re_migration_format = re.compile(r"(\d+)_(\w+)\.sql")
      migration_dir = Path(__file__).parent / "migrations"
      stuff_in_migration_dir = [
         (m, re_migration_format.fullmatch(m)) for m in os.listdir(migration_dir)]

      out_objs = []
      for path, match in stuff_in_migration_dir:
         if match is None:
            continue
         f = open(path, "rb")
         buf = f.read()
         out_objs.append(
            Migration(
               id=int(match.group(1)),
               name=match.group(2),
               md5hash=hashlib.md5(buf).hexdigest(),
               content=str(buf)
            ))
      return out_objs

   id: int
   name: str
   md5hash: str
   content: str

class ClientDatabase:
   """
   Opens the database, runs migration, and hooks up Python bindings
   """
   def __init__(self, path: str):
      self.f = open(path, "r+b")
      raw = self.f.read()
      self.conn = sqlite3.connect(":memory:")
      if len(raw) != 0:
         decoded = zstd.decode(raw)
         self.conn.deserialize(decoded)
      self.conn.execute(INIT)
      self.__run_migrations()

   def __run_migrations(self):
      for migration in Migration.all():
         self.conn.execute("select * from __migrations;").fetchall()
