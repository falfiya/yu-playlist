import textual

def test_playlist():
   txt1 = """"My Great Playlist"
      // Check those shoes out playa
      "I hope you kept the receipt"
      11102.0
      ["Aris Rage (Protect Your Ears)", "BasedMonster", "zbsbcKfqtSQ", "PTZI4WR47P"]
   """
   pl1 = textual.FriendlyPlaylist(txt1)
   assert len(pl1.items) == 1
   assert pl1.items[0].channel_title == "BasedMonster"
