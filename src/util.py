import os
import base64
import hashlib
import json
import typing as t
from bisect import bisect_left

import wcwidth

T = t.TypeVar("T")

DEBUG = False


def quote(x, start) -> str:
   return "\n".join([start + line for line in f"{x}".split("\n")])


def debug(x, start=""):
   if DEBUG:
      if start == "":
         print(x)
      else:
         print(quote(x, start=start))


def deserialize(s: str):
   return json.loads(s)

def serialize(x):
   return json.dumps(x, ensure_ascii=False)

_default_decoder = json.JSONDecoder()
def deserialize_raw(s: str, _: t.Optional[t.Type[T]] = None) -> tuple[T, str]:
   val, last_idx = _default_decoder.raw_decode(s)
   return val, s[last_idx:]

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

def mkdir(p: str):
   os.makedirs("playlists/in/full", exist_ok=True)


def longest_increasing_subsequence(unsorted: list[int]) -> list[int]:
   if len(unsorted) < 2:
      return unsorted

   best_sublists: list[list[int]] = [[unsorted[0]]]

   # This is simply a convenience variable which always mirrors the last element
   # of best_sublists. That is:
   # ∀ i ∈ indexof best_sublists. best_sublists[i][-1] = best_sublists_ending[i]
   #
   # Invariant:
   # ∀ i,j ∈ indexof best_sublists_ending where i < j.
   #     best_sublists_ending[i] < best_sublists_ending[j]
   #
   # We update best_sublists_ending[i] from x₁ to x₂ IFF x₂ < x₁.
   #
   # The list comprehension is for illustrative purposes.
   best_sublists_ending: list[int] = [sublist[-1] for sublist in best_sublists]

   for x2 in unsorted[1:]:
      belongs = bisect_left(best_sublists_ending, x2)

      if belongs == len(best_sublists_ending):
         best_sublists_ending.append(x2)
         best_sublists.append(best_sublists[-1] + [x2])
         continue

      x1 = best_sublists_ending[belongs]
      if x2 < x1:
         best_sublists_ending[belongs] = x2
         best_sublists[belongs] = best_sublists_ending[:belongs] + [x2]

   return best_sublists[-1]


def shortest_out_of_order_sublist(unsorted: list[int]) -> list[int]:
   in_order = longest_increasing_subsequence(unsorted)
   return [x for x in unsorted if x not in in_order]
