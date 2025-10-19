set shell := ["nu", "-c"]

save:
   uv run src/main.py save

post:
   uv run src/main.py post

clear:
   rm --trash .debug
