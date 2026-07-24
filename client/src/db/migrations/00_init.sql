-- 1. Intern the strings
create table string(
   S integer primary key,
   value text unique
) strict;
insert into string(S, value) values (0, null);
insert into string(S, value) values (1, '');

-- 2. Ensure the playlist item exists
create table playlist_item(
   -- PlaylistItem ids are globally unique and durable
   id integer references string(S) primary key,
   -- and the video never changes for that item.
   video_id integer references string(S),
   -- Nor does the playlist it belongs to
   playlist_id integer references string(S)
) strict;

-- 3. Take a Snapshot
--------------------------------------------------------------------------------
-- Playlist Snapshot Structure:
-- Snapshots are inserted into the database using a transaction.
-- If an ⟨epoch, playlist_id⟩ row is present in this table,
-- playlist_item is a complete list of all playlist items.
-- If an item is not present for that epoch, it was removed.
create table playlist_at(
   epoch integer not null,
   playlist_id integer references string(S),
   device integer references string(S), -- useful for figuring out which computer it came from
   ex integer references playlist_ex(ex_id),
   primary key (epoch, playlist_id)
) strict;

create table playlist_item_at(
   epoch integer not null,
   playlist_item_id integer references playlist_item(id),
   position integer not null,
   smol_hash text not null,
   primary key (epoch, playlist_item_id)
   -- foreign key (epoch,
   --    (select playlist_id from playlist_item where id = playlist_item_id))
   -- references playlist_item(epoch, playlist_id)
) strict;

-- 4. Collect Other Pieces of Data
--------------------------------------------------------------------------------
-- Other Pieces of Data:
-- The actual data of most objects doesn't change much over time and is
-- deduplicated into these tables and addressed using a single integer.
create table channel_ex(
   ex_id integer primary key,
   title integer references string(S) unique
) strict;

create table video_ex(
   ex_id integer primary key,
   owner integer references string(S),
   title integer references string(S),
   unique(owner, title)
) strict;

create table playlist_ex(
   ex_id integer primary key,
   title integer references string(S),
   desc integer references string(S),
   unique(title, desc)
) strict;

--------------------------------------------------------------------------------
-- xxx_at tables track the change of data over time.
-- It is expected that each snapshot, many rows are created in each of these.
-- Since most data will be the same, a single integer is a lot cheaper than
-- storing a bunch of integers.
create table channel_at(
   epoch integer not null,
   id integer references string(S),
   ex integer references channel_ex(ex_id),
   primary key (epoch, id)
) strict;

create table video_at(
   epoch integer not null,
   id integer references string(S),
   ex integer references video_ex(ex_id),
   primary key (epoch, id)
) strict;
