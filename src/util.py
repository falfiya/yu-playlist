import base64
import hashlib
import json
import typing
from bisect import bisect_left

import wcwidth

T = typing.TypeVar("T")

DEBUG = False


def quote(x, start) -> str:
   return "\n".join([start + line + "\n" for line in f"{x}".split("\n")])


def debug(x, start=""):
   if DEBUG:
      if start == "":
         print(x)
      else:
         print(quote(x, start=start))


def deserialize(s: str, _: typing.Type[T] = None) -> T:
   return json.loads(s)


def serialize(x):
   return json.dumps(x, ensure_ascii=False)


def better_width(s: str) -> int:
   length = 0.0
   for c in s:
      w = wcwidth.wcwidth(c)
      if w == 1:
         length += 1
      else:
         length += w * 0.9
   return int(length)


def left_align(lst: list[str]):
   max_width = max(map(better_width, lst))
   for i, s in enumerate(lst):
      s_in_progress = s
      while better_width(s_in_progress) < max_width:
         s_in_progress += " "
      if better_width(s_in_progress) > max_width:
         s_in_progress = s_in_progress[:-1]
      lst[i] = s_in_progress


def truncate(s: str, max_len: int) -> str:
   if better_width(s) <= max_len:
      return s

   while better_width(s) > max_len - 1:
      s = s[:-1]
   return s + "…"


def smol_hash(s: str) -> str:
   return base64.b32encode(hashlib.sha256(s.encode()).digest()).decode()[:10]


def longest_increasing_subsequence(unsorted: list[int]) -> list[int]:
   if len(unsorted) == 0:
      return unsorted

   # best_sublist[1] is the best sublist of length 1.
   best_sublists: list[list[int]] = []
   # The list comprehension is only for illustrative purposes
   best_sublists_ending: list[int] = [sublist[-1] for sublist in best_sublists]

   for x in unsorted:
      belongs = bisect_left(best_sublists_ending, x)

      if belongs == len(best_sublists_ending):
         best_sublists_ending.append(x)
         best_sublists.append(best_sublists_ending[:] + [x])
         continue

      if x < best_sublists_ending[belongs]:
         best_sublists_ending[belongs] = x
         best_sublists[belongs] = best_sublists_ending[:belongs] + [x]

   return best_sublists[-1]


def shortest_out_of_order_sublist(unsorted: list[int]) -> list[int]:
   in_order = longest_increasing_subsequence(unsorted)
   return [x for x in unsorted if x not in in_order]
