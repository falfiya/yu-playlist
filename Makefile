run:
	uv run src/main.py

test:
   uv run pytest --cov=src --cov-report=html
   start htmlcov/index.html
