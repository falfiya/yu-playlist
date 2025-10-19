import colorama as c
import sys
import bridge
import log as l

from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import choice
from prompt_toolkit.completion import WordCompleter

def local():
   filenames = bridge.my_playlist_files()
   for t in filenames:
      print(f" - {t}")

   title = prompt("> ", completer=WordCompleter(filenames, ignore_case=True, match_middle=True))
   filename = filenames[filenames.index(title)]
   analyze(bridge.get_playlist_offline(filename))

def online():
   filenames = bridge.my_playlists_online()
   for p in filenames:
      analyze(p)

   l.info(f"Recorded {len(filenames)} playlists!")
   exit(0)

def analyze(p: bridge.Playlist):
   group_started = [False]
   def group():
      if not group_started[0]:
         l.info(p.yt_playlist.title)
         l.group_start()
         group_started[0] = True

   if len(p.missing_shadow) > 0:
      group()
      l.warn("Local Missing:")
      l.group_start()
      for missing in p.missing_shadow:
         l.warn(missing)
      l.group_end()

   if len(p.missing_yt) > 0:
      group()
      l.warn("Local Extra:")
      l.group_start()
      for extra in p.missing_yt:
         l.warn(extra)
      l.group_end()

   if group_started[0]:
      l.group_end()
   l.info(p.shadow_playlist.friendly_jsonl())

print(f"{c.ansi.CSI}2J{c.ansi.CSI}HWelcome to the command-line interface for yu-playlist!")

choice_start = choice(
   message="How do you want to start?",
   options=[
      ("local", "Work with what I have right now."),
      ("online", "Fetch all playlist information from YouTube immediately."),
   ],
   default="local",
)

if choice_start == "local":
   local()

if choice_start == "online":
   online()
