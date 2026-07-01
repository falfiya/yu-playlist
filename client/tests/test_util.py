import util

def test_quote():
   assert util.quote(" world\nween", "hello") == "hello world\nhelloween"

def test_deserialize_raw():
   nn, bbotw = util.deserialize_raw("99 bottles of beer on the wall")
   assert nn == 99
   assert bbotw == " bottles of beer on the wall"

def test_longest_increasing_sublist():
   assert util.longest_increasing_subsequence([1, 2]) == [1, 2]
   assert util.longest_increasing_subsequence([3, 4, 2, 9, 1]) == [3, 4, 9]
