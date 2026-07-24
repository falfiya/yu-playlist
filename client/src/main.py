import argparse
import shutil
from pathlib import Path

import colorama as c
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.shortcuts import choice, message_dialog, yes_no_dialog

import bridge
from config import ClientConfig
from log import Logging
import sys

assert __name__ == "__main__", "You must invoke this as a script"

################################################################################
## Command Line Parsing
class ClientArguments:
   directory: str



parser = argparse.ArgumentParser(
   prog="yu-playlist",
   description="CLI and TUI for managing YouTube Playlists",
   epilog="and thats how you use the program. thank you for coming to my ted talk",
)
parser.add_argument("directory", help="The directory where playlists are stored")
if len(sys.argv) < 2:
   parser.print_help()
   exit()
options = ClientArguments()
parser.parse_args(namespace=options)

################################################################################
## Loading the config file
config_path = Path(options.directory) / "yu-playlist.toml"
try:
   config_file = open(config_path, "r")
except FileNotFoundError:
   copy_default_config_file = yes_no_dialog(
      title="Config file missing!",
      text=(
         f"I looked for a config file at {config_path.absolute()} but I couldn't find one. "
         "Do you want me to make one for you?"
      ),
   ).run()
   if copy_default_config_file:
      default_config_path = Path(__file__).parent / "config.default.toml"
      shutil.copyfile(default_config_path, config_path)
      message_dialog(
         title="All done :3",
         text="I created the config file. Please be sure to edit it.",
      )
      quit(0)
   else:
      exit(1)
config = ClientConfig.from_file(config_file)

################################################################################
## The Meat
l = Logging(config)


def specific(fn):
   filenames = bridge.my_playlist_files()
   for t in filenames:
      print(f" - {t}")

   try:
      title = prompt(
         "> ", completer=WordCompleter(filenames, ignore_case=True, match_middle=True)
      )
   except KeyboardInterrupt:
      l.error("Interrupt")
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
         l.info(extra)
      l.group_end()

   if len(p.missing_from_shadow) > 0:
      group()
      l.warn("Local Missing:")
      l.group_start()
      for missing in p.missing_from_shadow:
         l.info(missing)
      l.group_end()

   if p.diff_ok:
      if len(p.ooo) > 0:
         group()
         l.warn("Out-of-order:")
         l.group_start()
         for ooo in p.ooo:
            l.warn(ooo)
         l.group_end()
   else:
      l.warn("Refusing to calculate out-of-order items.")

   if group_started[0]:
      l.group_end()


def ingest(p: bridge.Playlist):
   l.info(f"Ingest {p.shadow_file_object.title}")
   l.group_start()
   p.ingest_new_yt()
   l.group_end()


def push(p: bridge.Playlist):
   p.push()


def reset(p: bridge.Playlist):
   l.info(f"Reset {p.shadow_file_object.title}")
   l.group_start()
   p.reset_to_yt()
   l.group_end()


print(
   f"{c.ansi.CSI}2J{c.ansi.CSI}H Welcome to the textual user interface for yu-playlist!"
)

try:
   what_to_do = choice(
      message="How do you want to start?",
      options=[
         ("diff" , "diff: Displays the difference between local and remote"),
         ("pull" , "pull: Pulls new additions and deletions from remote"),
         ("push" , "push: Enforces the local order on the remote"),
         ("reset", "reset: Discards all local changes and resets to the remote"),
      ],
      default="diff",
   )
except KeyboardInterrupt:
   l.error("Interrupt")
   exit()

# TODO: Read all local playlist files
match what_to_do:
   case "diff":
      # TODO:
      # From the local perspective
      # New items from the remote should be marked as + with green.
      # Items that were removed on the remote should be marked as - with red.
      # To achieve this, first read the textual playlist.
      # Using the database, immediately convert back from smol_hash to playlist item ids.
      # In fact, reading the textual playlist requires that the database be present.
      # LATER: you may handle the case where the database is corrupted,
      #        and allow a complete ingest of all youtube playlists to put a
      #        playlist id to there. You may make a new option called "doctor"
      # Continuing:
      # Perform a left set difference and right set difference between the local
      # playlist items and the remote playlist items.
      # Since we are not stateful, I believe all of the diffing can be cached.
      # (Though when would we need it twice?)
      ...
   case "pull":
      # TODO:
      # Use the above diffing code somehow.
      # When an item is removed on the remote, comment it out in the textual playlist.
      ...
   case "push":
      # This requires pulling anyways.
      # Additionally, do that cursed least moves algo.
      ...
   case "reset":
      # Ask a confirmation from the user.
      # Do you really want to hard reset? Any playlist items and comments you had will be lost.
      ...
   case _:
      raise ValueError("SANITY: The choice was invalid!")
