| model | prompt | sampling | valid 1st try % | failed % | p50 s | p95 s | $ / 1k calls | call type acc (all) | extracted acc | inferred acc | objections F1 | golden runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| openai/gpt-4o-mini | v1 | deterministic | 100 | 0 | 1.7 | 3.2 | 0.528 | 0.64 | 0.62 | 0.50 | 0.50 | 3 |
| openai/gpt-4o-mini | v1 | low | 100 | 0 | 1.6 | 2.7 | 0.528 | 0.61 | 0.65 | 0.53 | 0.50 | 3 |
| qwen3:14b | v1 | deterministic | 100 | 0 | 15.6 | 33.7 | 0.000 | 0.64 | 0.59 | 0.63 | 0.44 | 3 |
| qwen3:14b | v1 | low | 100 | 0 | 22.5 | 46.2 | 0.000 | 0.64 | 0.56 | 0.63 | 0.44 | 3 |
| qwen3:8b | v1 | deterministic | 100 | 0 | 7.9 | 16.7 | 0.000 | 0.47 | 0.62 | 0.37 | 0.36 | 3 |
| qwen3:8b | v1 | low | 100 | 0 | 8.7 | 17.0 | 0.000 | 0.47 | 0.62 | 0.37 | 0.36 | 3 |
