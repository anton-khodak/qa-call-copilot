| model | prompt | sampling | valid 1st try % | failed % | p50 s | p95 s | $ / 1k calls | domain acc (all) | extracted acc | inferred acc | objections F1 | golden runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| openai/gpt-4o-mini | v1 | deterministic | 100 | 0 | 2.1 | 3.1 | 0.484 | 0.81 | – | – | – | – |
| openai/gpt-4o-mini | v1 | low | 100 | 0 | 2.0 | 2.7 | 0.483 | 0.83 | – | – | – | – |
| qwen3:8b | v1 | deterministic | 98 | 2 | 9.7 | 19.3 | 0.000 | 0.61 | – | – | – | – |
| qwen3:8b | v1 | low | 100 | 0 | 10.5 | 19.9 | 0.000 | 0.64 | – | – | – | – |

Golden labels missing: accuracy columns are empty until data/golden/golden_v1.jsonl is filled.
