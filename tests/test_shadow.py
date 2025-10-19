import shadow

def test_playlist():
   txt1 = """
      // There's a comment here--step on him
      "My Great Playlist"
      // Check those shoes out playa
      "I hope you kept the receipt"
      ["Aris Rage (Protect Your Ears)", "BasedMonster", "zbsbcKfqtSQ", "PTZI4WR47P"]
   """
   pl1 = shadow.Playlist(txt1.split("\n"))
   assert len(pl1.items) == 1
   assert pl1.items[0].channel_name == "BasedMonster"
