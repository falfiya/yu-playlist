-- Video data is fetched using the .snippet field of PlaylistItem.
-- We keep track of very basic information.
create table strings(
   id integer primary key,
   value text unique
) strict;
insert into strings(id, value) values (0, null);
insert into strings(id, value) values (1, '');

create table videos(
   id integer references strings(id) primary key
) strict;

create table channels(
   id integer references strings(id) primary key
) strict;

create table playlists(
   id integer references strings(id) primary key
) strict;

create table playlist_items(
   -- PlaylistItem ids are globally unique and durable
   id integer references strings(id),
   -- and the video never changes for that item.
   vid integer references videos(id),
   -- Nor does the playlist it belongs to
   pid integer references playlists(id)
) strict;

-- The actual data of most objects doesn't change much over time and is
-- deduplicated into these tables and addressed using a single integer.
create table video_data(
   id integer primary key,
   owner integer references channels(id),
   title integer references strings(id)
) strict;

create table playlist_data(
   id integer primary key,
   title integer references strings(id),
   desc integer references strings(id)
) strict;

create table video_at(
   epoch integer not null,
   vid integer references videos(id),
   data integer references video_data(id)
) strict;

create table channel_data(
   id integer not null,
   title integer references strings(id)
) strict;

-- xxx_at tables track the change of data over time.
-- It is expected that each snapshot, many rows are created in each of these.
-- Since most data will be the same, a single integer is a lot cheaper than
-- storing a bunch of integers.
create table channel_at(
   epoch integer not null,
   cid integer references channels(id),
   data integer references channel_data(id)
) strict;

create table playlist_at(
   epoch integer not null,
   pid integer references playlists(id),
   data integer references playlist_data(id)
) strict;

create table playlist_item_at(
   epoch integer not null,
   pid integer references playlist_items(id),
   position integer not null
) strict;
