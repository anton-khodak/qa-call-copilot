data:
	uv run python data/download.py

# fetches the transcripts if missing, runs all models x prompts x samplings (config defaults), then metrics
run: data
	uv run python main.py matrix $(ARGS)

# frontier reference: Opus 5.5 through the local Claude Code CLI (its default sampling), both prompts, then metrics
frontier: data
	uv run python main.py matrix --models opus_5_5 --samplings cli_default $(ARGS)

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

.PHONY: data run frontier eval errors test label
