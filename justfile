set shell := ["nu", "-c"]

save:
   uv run main.py save

post:
   uv run main.py post

clear:
   rm --trash .debug
