create view channels as
select
   (select value from _strings where id = ch.id) as id
from _channels as ch;

create trigger channels_insert instead of insert on channels
begin
   insert or ignore into _strings(value) values (new.id);

   insert into _channels(id) values (
      (select id from _strings where value = new.id));
end;

create view videos as
select
   (select value from _strings where id = v.id) as id
from _videos as v;

create trigger videos_insert instead of insert on videos
begin
   insert or ignore into _strings(value) values (new.id);

   insert into _videos(id) values (
      (select id from _strings where value = new.id));
end;

create view playlists as
select
   (select value from _strings where id = p.id) as id
from _playlists as p;

create trigger playlists_insert instead of insert on playlists
begin
   insert or ignore into _strings(value) values (new.id);

   insert into _playlists(id) values (
      (select id from _strings where value = new.id));
end;

create view playlist_items as
select
   (select value from _strings where id = i.id) as id,
   (select value from _strings where id = i.vid) as vid,
   (select value from _strings where id = i.pid) as pid
from _playlist_items as i;

create trigger playlist_items_insert instead of insert on playlist_items
begin
   insert or ignore into _strings(value) values (new.id);

   insert or ignore into videos(id) values (new.vid);

   insert or ignore into playlists(id) values (new.pid);

   insert into _playlist_items(id, vid, pid) values (
      (select id from _strings where value = new.id),
      (select id from _strings where value = new.vid),
      (select id from _strings where value = new.pid));
end;

create view channel_at as
select
   ca.epoch,
   (select value from _strings where id = ch.id) as id,
   (select value from _strings where id = cd.title) as title
from _channel_at as ca
join _channels as ch on ch.id = ca.cid
join _channel_data as cd on cd.id = ca.data;

create trigger channel_at_insert instead of insert on channel_at
begin
   insert or ignore into channels(id) values (new.id);

   insert or ignore into _strings(value) values (new.title);

   insert or ignore into _channel_data(title) values (
      (select id from _strings where value = new.title));

   insert into _channel_at(epoch, cid, data) values (
      new.epoch,
      (select id from _strings where value = new.id),
      (select id from _channel_data where title =
         (select id from _strings where value = new.title)));
end;

create view video_at as
select
   va.epoch,
   (select value from _strings where id = v.id) as id,
   (select value from _strings where id = vd.owner) as owner,
   (select value from _strings where id = vd.title) as title
from _video_at as va
join _videos as v on v.id = va.vid
join _video_data as vd on vd.id = va.data;

create trigger video_at_insert instead of insert on video_at
begin
   insert or ignore into videos(id) values (new.id);

   insert or ignore into channels(id) values (new.owner);

   insert or ignore into _strings(value) values (new.title);

   insert or ignore into _video_data(owner, title) values (
      (select id from _strings where value = new.owner),
      (select id from _strings where value = new.title));

   insert into _video_at(epoch, vid, data) values (
      new.epoch,
      (select id from _strings where value = new.id),
      (
         select id from _video_data
         where (1
            and owner = (select id from _strings where value = new.owner)
            and title = (select id from _strings where value = new.title))));
end;

create view playlist_at as
select
   pa.epoch,
   (select value from _strings where id = p.id) as id,
   (select value from _strings where id = pd.title) as title,
   (select value from _strings where id = pd.desc) as desc
from _playlist_at as pa
join _playlists as p on p.id = pa.pid
join _playlist_data as pd on pd.id = pa.data;

create trigger playlist_at_insert instead of insert on playlist_at
begin
   insert or ignore into playlists(id) values (new.id);

   insert or ignore into _strings(id) values (new.title);

   insert or ignore into _strings(id) values (new.desc);

   insert or ignore into _playlist_data(title, desc)
      values (
         (select id from _strings where value = new.title),
         (select id from _strings where value = new.desc));

   insert into _playlist_at(epoch, pid, data)
   values (
      new.epoch,
      (select id from _strings where value = new.id),
      (
         select id from _playlist_data
         where (1
            and title = (select id from _strings where value = new.title)
            and desc = (select id from _strings where value = new.description))));
end;

create view playlist_item_at as
select
   pia.epoch,
   (select value from _strings where id = pi.id) as id,
   pia.position
from _playlist_item_at as pia
join _playlist_items as pi on pi.id = pia.pid;

-- TODO: Should take more than that.
create trigger playlist_item_at_insert instead of insert on playlist_item_at
begin
   insert into _playlist_item_at(epoch, pid, position) values (
      new.epoch,
      (select id from _playlist_items where id =
         (select id from _strings where value = new.id)),
      new.position);
end;
