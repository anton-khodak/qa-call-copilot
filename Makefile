data:
	uv run python data/download.py

# fetches the transcripts if missing, runs all models x prompts x samplings (config defaults), then metrics
run: data
	uv run python main.py matrix $(ARGS)

eval:
	uv run python main.py eval

# golden-set disagreements of the latest runs, for the error analysis in REPORT.md
errors:
	uv run python main.py errors

test:
	uv run pytest

# local UI for hand-labelling data/golden/golden.jsonl
label:
	uv run python -m src.label_app

.PHONY: data run eval errors test label
