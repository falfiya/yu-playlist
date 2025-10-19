import sys
import pprint
import colorama as c

_indent_level: int = 0

def _get_indent() -> str:
   return " | " * _indent_level

def _pretty_prefix(v, prefix: str) -> str:
   msg: str
   if isinstance(v, str):
      msg = v
   else:
      msg = pprint.pformat(v)
   return "".join([""
      + prefix + c.Style.RESET_ALL + _get_indent() + " "
      + line + "\n"
      for line in msg.split("\n")
   ])

def start_group():
   global _indent_level
   _indent_level += 1

def end_group():
   global _indent_level
   if _indent_level > 1:
      _indent_level -= 1
   else:
      _indent_level = 0

def debug(v):
   sys.stderr.write(_pretty_prefix(v, c.Fore.LIGHTBLACK_EX + "DBG"))

def info(v):
   sys.stderr.write(_pretty_prefix(v, c.Fore.BLUE + "INF"))

def warn(v):
   sys.stderr.write(_pretty_prefix(v, c.Fore.YELLOW + "WRN"))

def error(v):
   sys.stderr.write(_pretty_prefix(v, c.Fore.LIGHTRED_EX + "ERRs"))
