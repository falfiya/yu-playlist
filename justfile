set shell := ["nu", "-c"]

save:
   uv run src/main.py save

post:
   uv run src/main.py post

test:
   uv run pytest --cov=src --cov-report=html
   start htmlcov/index.html

clear:
   rm --trash .debug
