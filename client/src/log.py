import pprint
import sys

import colorama as c

import config

class Logging:
   def __init__(self, config: config.ClientConfig):
      self._indent_level: int = 0
      self.config = config

   def _get_indent(self) -> str:
      return " | " * self._indent_level

   def _pretty_prefix(self, v, prefix: str) -> str:
      msg: str
      if isinstance(v, str):
         msg = v
      else:
         msg = pprint.pformat(v)
      return "".join(
         [
            "" + prefix + c.Style.RESET_ALL + self._get_indent() + " " + line + "\n"
            for line in msg.split("\n")
         ]
      )

   def group_start(self):
      self._indent_level += 1

   def group_end(self):
      if self._indent_level > 1:
         self._indent_level -= 1
      else:
         self._indent_level = 0

   def debug(self, v):
      if self.config.log_level < 1:
         sys.stderr.write(self._pretty_prefix(v, c.Fore.LIGHTBLACK_EX + "DBG"))


   def info(self, v):
      sys.stderr.write(self._pretty_prefix(v, c.Fore.BLUE + "INF"))


   def warn(self, v):
      sys.stderr.write(self._pretty_prefix(v, c.Fore.YELLOW + "WRN"))


   def error(self, v):
      sys.stderr.write(self._pretty_prefix(v, c.Fore.LIGHTRED_EX + "ERR"))
