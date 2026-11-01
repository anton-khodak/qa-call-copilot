| model | prompt | sampling | valid 1st try % | repaired % | failed % | p50 s | p95 s | $ / 1k calls | call type acc (all) | extracted acc | inferred acc | objections F1 | golden runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| openai/gpt-4o-mini | v1 | deterministic | 100 | 0 | 0 | 1.3 | 1.9 | 0.393 | 0.64 | 0.70 | 0.53 | 0.50 | 3 |
| openai/gpt-4o-mini | v1 | low | 100 | 0 | 0 | 1.3 | 1.8 | 0.392 | 0.58 | 0.70 | 0.53 | 0.50 | 3 |
| qwen3:14b | v1 | deterministic | 100 | 0 | 0 | 12.9 | 35.7 | 0.000 | 0.61 | 0.60 | 0.67 | 0.40 | 3 |
| qwen3:14b | v1 | low | 100 | 0 | 0 | 13.3 | 25.6 | 0.000 | 0.61 | 0.60 | 0.67 | 0.40 | 3 |
| qwen3:8b | v1 | deterministic | 100 | 0 | 0 | 6.1 | 13.3 | 0.000 | 0.53 | 0.61 | 0.47 | 0.43 | 3 |
| qwen3:8b | v1 | low | 100 | 0 | 0 | 6.1 | 9.0 | 0.000 | 0.53 | 0.61 | 0.47 | 0.43 | 3 |

Golden-set accuracy per field (median over runs):

| model | prompt | sampling | call_type | direction | outcome | agent_handoff | recording_disclosed | obj P | obj R | obj F1 | handled |
|---|---|---|---|---|---|---|---|---|---|---|---|
| openai/gpt-4o-mini | v1 | deterministic | 0.70 | 0.30 | 0.60 | 1.00 | 0.60 | 0.67 | 0.40 | 0.50 | 1.00 |
| openai/gpt-4o-mini | v1 | low | 0.70 | 0.30 | 0.60 | 1.00 | 0.60 | 0.67 | 0.40 | 0.50 | 1.00 |
| qwen3:14b | v1 | deterministic | 0.70 | 0.60 | 0.70 | 0.80 | 0.60 | 0.40 | 0.40 | 0.40 | 1.00 |
| qwen3:14b | v1 | low | 0.70 | 0.60 | 0.70 | 0.80 | 0.60 | 0.40 | 0.40 | 0.40 | 1.00 |
| qwen3:8b | v1 | deterministic | 0.60 | 0.40 | 0.40 | 0.70 | 0.70 | 0.33 | 0.60 | 0.43 | 1.00 |
| qwen3:8b | v1 | low | 0.60 | 0.40 | 0.40 | 0.70 | 0.70 | 0.33 | 0.60 | 0.43 | 1.00 |
