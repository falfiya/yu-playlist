"""
Tests that the database migrations apply cleanly to a fresh in-memory database
and produce the schema defined in src/db/migrations.

These are intentionally smoke tests: they confirm the migrations run without
error and yield the expected tables. They do not exhaustively exercise the
corner cases of the migration bookkeeping logic in ClientDatabase.
"""

import apsw

import config
from db import ClientDatabase, MigrationOnDisk


def _make_config() -> config.ClientConfig:
   # Migrations don't depend on config values; we just need a valid object.
   return config.ClientConfig(
      log_level=1,
      oauth2_callback_port=0,
      secrets_path="secrets",
      device_name="test-device",
   )


def _open() -> ClientDatabase:
   conn = apsw.Connection(":memory:")
   return ClientDatabase(conn=conn, config=_make_config())


def test_migrations_apply_to_fresh_db():
   """Migrations should run without error on an empty in-memory database."""
   db = _open()
   db.close()


def test_migration_bookkeeping_table_exists():
   """The __migration table is created by INIT and tracks applied migrations."""
   db = _open()
   rows = db.conn.execute(
      "select id, name, md5hash from __migration order by id"
   ).fetchall()
   db.close()

   on_disk = {m.id: m for m in MigrationOnDisk.all()}
   assert len(rows) == len(on_disk), (
      f"expected {len(on_disk)} applied migrations, got {len(rows)}"
   )
   for (id, name, md5hash) in rows:
      assert id in on_disk, f"__migration has id {id} with no file on disk"
      assert name == on_disk[id].name, (
         f"migration {id} name mismatch: db={name!r} disk={on_disk[id].name!r}"
      )
      assert md5hash == on_disk[id].md5hash, (
         f"migration {id} md5 mismatch: db={md5hash} disk={on_disk[id].md5hash}"
      )


def test_expected_tables_exist():
   """Every table defined by the migrations should be present after running them."""
   db = _open()
   table_names = {
      r[0]
      for r in db.conn.execute(
         "select name from sqlite_master where type = 'table'"
      ).fetchall()
   }
   db.close()

   expected = {
      "__migration",
      "string",
      "playlist_item",
      "playlist_at",
      "playlist_item_at",
      "channel_ex",
      "video_ex",
      "playlist_ex",
      "channel_at",
      "video_at",
   }
   missing = expected - table_names
   assert not missing, f"missing tables: {missing}"


def test_foreign_keys_enforced():
   """INIT enables foreign_keys; the connection should report it as on."""
   db = _open()
   (fk,) = db.conn.execute("pragma foreign_keys").fetchone()
   db.close()
   assert fk == 1


def test_reopening_idempotent():
   """
   Re-running migrations against a database that already has them applied
   should be a no-op (no errors, no duplicate rows).
   """
   db = _open()
   # Running the constructor's migration logic again by re-invoking the
   # private method directly on the same connection.
   db._ClientDatabase__run_migrations()
   rows = db.conn.execute(
      "select count(*) from __migration"
   ).fetchone()
   db.close()
   assert rows[0] == len(MigrationOnDisk.all())


def test_seed_strings_present():
   """
   The 00_init migration seeds string(S=0, value=null) and string(S=1, value='').
   These are relied on by the rest of the schema.
   """
   db = _open()
   rows = db.conn.execute(
      "select S, value from string where S in (0, 1) order by S"
   ).fetchall()
   db.close()
   assert rows == [(0, None), (1, "")]
