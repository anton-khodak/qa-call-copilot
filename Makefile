data:
	uv run python data/download.py

# all models x prompts x samplings (config defaults), then metrics
run:
	uv run python main.py matrix

eval:
	uv run python main.py eval

test:
	uv run pytest

# local UI for hand-labelling data/golden/golden_v1.jsonl
label:
	uv run python -m src.label_app

.PHONY: data run eval test label
