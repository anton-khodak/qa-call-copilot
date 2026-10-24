data:
	uv run python data/download.py

run:
	uv run python main.py run

test:
	uv run pytest

.PHONY: data run test
