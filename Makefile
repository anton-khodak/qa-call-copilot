data:
	uv run python data/download.py

# all models x prompts x samplings (config defaults), then metrics
run:
	uv run python main.py matrix

eval:
	uv run python main.py eval

test:
	uv run pytest

.PHONY: data run eval test
