import colorama as c
import bridge
import log as l

from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import choice
from prompt_toolkit.completion import WordCompleter

def specific(fn):
   filenames = bridge.my_playlist_files()
   for t in filenames:
      print(f" - {t}")

   try:
      title = prompt("> ", completer=WordCompleter(filenames, ignore_case=True, match_middle=True))
   except KeyboardInterrupt:
      print("Interrupt")
      exit()
   filename = filenames[filenames.index(title)]
   fn(bridge.get_playlist_offline(filename))

def full(fn):
   filenames = bridge.my_playlists_online()
   for p in filenames:
      fn(p)
   l.info(f"Processed {len(filenames)} playlists!")

def analyze(p: bridge.Playlist):
   group_started = [False]
   def group():
      if not group_started[0]:
         l.info(p.yt_playlist.title)
         l.group_start()
         group_started[0] = True

   if len(p.missing_from_yt) > 0:
      group()
      l.warn("Local Extra (Please Remove These)")
      l.group_start()
      for extra in p.missing_from_yt:
         l.warn(extra)
      l.group_end()

   if len(p.missing_from_shadow) > 0:
      group()
      l.warn("Local Missing:")
      l.group_start()
      for missing in p.missing_from_shadow:
         l.warn(missing)
      l.group_end()

   if len(p.ooo) > 0:
      group()
      l.warn("Out-of-order:")
      l.group_start()
      for ooo in p.ooo:
         l.warn(ooo)
      l.group_end()

   if group_started[0]:
      l.group_end()

def ingest(p: bridge.Playlist):
   l.info(f"Ingest {p.shadow_playlist.title}")
   l.group_start()
   p.ingest_new_yt()
   l.group_end()

def reset(p: bridge.Playlist):
   l.info(f"Reset {p.shadow_playlist.title}")
   l.group_start()
   p.reset_to_yt()
   l.group_end()

print(f"{c.ansi.CSI}2J{c.ansi.CSI}H Welcome to the command-line interface for yu-playlist!")

try:
   what_to_do = choice(
      message="How do you want to start?",
      options=[
         ("specific(analyze)", "Fine-grained analysis"),
         ("full(analyze)"    , "Full analysis"),
         ("specific(ingest)" , "Fine-grained ingest"),
         ("full(ingest)"     , "Full ingest"),
         ("specific(reset)"  , "Specific reset to match YouTube"),
         ("full(reset)"      , "Reset all to match YouTube"),
      ],
      default="specific_analysis",
   )
except KeyboardInterrupt:
   print("Interrupt")
   exit()

eval(what_to_do)
