| model | prompt | sampling | valid 1st try % | failed % | p50 s | p95 s | $ / 1k calls | call type acc (all) | extracted acc | inferred acc | objections F1 | golden runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| openai/gpt-4o-mini | v1 | deterministic | 100 | 0 | 1.7 | 3.2 | 0.528 | 0.64 | 0.62 | 0.50 | 0.50 | 3 |
| openai/gpt-4o-mini | v1 | low | 100 | 0 | 1.6 | 2.7 | 0.528 | 0.61 | 0.65 | 0.53 | 0.50 | 3 |
| qwen3:8b | v1 | deterministic | 89 | 11 | 9.0 | 67.4 | 0.000 | 0.17 | 0.33 | 0.20 | 0.00 | 3 |
| qwen3:8b | v1 | low | 89 | 11 | 9.7 | 65.8 | 0.000 | 0.17 | 0.27 | 0.20 | 0.00 | 3 |
