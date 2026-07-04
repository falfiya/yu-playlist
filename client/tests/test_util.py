import util as u


def test_quote():
   assert u.quote(" world\nween", "hello") == "hello world\nhelloween"


def test_deserialize_raw():
   nn, bbotw = u.deserialize_raw("99 bottles of beer on the wall")
   assert nn == 99
   assert bbotw == " bottles of beer on the wall"


def test_longest_increasing_sublist():
   assert u.longest_increasing_subsequence([1, 2]) == [1, 2]
   assert u.longest_increasing_subsequence([3, 4, 2, 9, 1]) == [3, 4, 9]


def test_head_comments():
   src = [
      "",
      "// foo",
      "   // foo",
      "",
      "there's something here",
      "",
      "// and here",
      "this is last",
   ]
   head, src = u.head_comments(src)
   print(head, src)
   assert src.pop(0) == "there's something here"
   head, src = u.head_comments(src)
   print(head, src)
   assert src.pop(0) == "this is last"
