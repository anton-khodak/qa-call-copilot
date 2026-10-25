data:
	uv run python data/download.py

# fetches the transcripts if missing, runs all models x prompts x samplings (config defaults), then metrics
run: data
	uv run python main.py matrix $(ARGS)

eval:
	uv run python main.py eval

test:
	uv run pytest

# local UI for hand-labelling data/golden/golden_v2.jsonl
label:
	uv run python -m src.label_app

.PHONY: data run eval test label
