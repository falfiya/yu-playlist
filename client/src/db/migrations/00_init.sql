-- Video data is fetched using the .snippet field of PlaylistItem.
-- We keep track of very basic information.
create table _strings(
   id integer primary key,
   value text unique
) strict;
insert into _strings(id, value) values (0, null);
insert into _strings(id, value) values (1, '');

--------------------------------------------------------------------------------
-- Basic Entity Ids
create table _channels(
   id integer references _strings(id) primary key
) strict;

create table _videos(
   id integer references _strings(id) primary key
) strict;

create table _playlists(
   id integer references _strings(id) primary key
) strict;

create table _playlist_items(
   -- PlaylistItem ids are globally unique and durable
   id integer references _strings(id) primary key,
   -- and the video never changes for that item.
   vid integer references _videos(id),
   -- Nor does the playlist it belongs to
   pid integer references _playlists(id)
) strict;

--------------------------------------------------------------------------------
-- The actual data of most objects doesn't change much over time and is
-- deduplicated into these tables and addressed using a single integer.
create table _channel_data(
   id integer primary key,
   title integer references _strings(id) unique
) strict;

create table _video_data(
   id integer primary key,
   owner integer references _channels(id),
   title integer references _strings(id),
   unique(owner, title)
) strict;

create table _playlist_data(
   id integer primary key,
   title integer references _strings(id),
   desc integer references _strings(id),
   unique(title, desc)
) strict;
--------------------------------------------------------------------------------
-- xxx_at tables track the change of data over time.
-- It is expected that each snapshot, many rows are created in each of these.
-- Since most data will be the same, a single integer is a lot cheaper than
-- storing a bunch of integers.
create table _channel_at(
   epoch integer not null,
   cid integer references _channels(id),
   data integer references _channel_data(id)
) strict;

create table _video_at(
   epoch integer not null,
   vid integer references _videos(id),
   data integer references _video_data(id)
) strict;

create table _playlist_at(
   epoch integer not null,
   pid integer references _playlists(id),
   data integer references _playlist_data(id)
) strict;

create table _playlist_item_at(
   epoch integer not null,
   pid integer references _playlist_items(id),
   position integer not null
) strict;
