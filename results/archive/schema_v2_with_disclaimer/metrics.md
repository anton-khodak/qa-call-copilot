| model | prompt | sampling | valid 1st try % | repaired % | failed % | p50 s | p95 s | $ / 1k calls | call type acc (all) | extracted acc | inferred acc | objections F1 | golden runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| openai/gpt-4o-mini | v1 | deterministic | 100 | 0 | 0 | 1.7 | 3.2 | 0.528 | 0.64 | 0.62 | 0.50 | 0.50 | 3 |
| openai/gpt-4o-mini | v1 | low | 100 | 0 | 0 | 1.6 | 2.7 | 0.528 | 0.61 | 0.65 | 0.53 | 0.50 | 3 |
| openai/gpt-4o-mini | v2 | deterministic | 100 | 0 | 0 | 1.7 | 2.5 | 0.604 | 0.58 | 0.59 | 0.63 | 0.57 | 3 |
| openai/gpt-4o-mini | v2 | low | 100 | 0 | 0 | 1.7 | 3.6 | 0.605 | 0.56 | 0.59 | 0.63 | 0.57 | 3 |
| qwen3:14b | v1 | deterministic | 100 | 0 | 0 | 15.6 | 33.7 | 0.000 | 0.64 | 0.59 | 0.63 | 0.44 | 3 |
| qwen3:14b | v1 | low | 100 | 0 | 0 | 22.5 | 46.2 | 0.000 | 0.64 | 0.56 | 0.63 | 0.44 | 3 |
| qwen3:14b | v2 | deterministic | 100 | 0 | 0 | 16.0 | 43.7 | 0.000 | 0.64 | 0.64 | 0.60 | 0.44 | 3 |
| qwen3:14b | v2 | low | 100 | 0 | 0 | 16.3 | 33.0 | 0.000 | 0.64 | 0.64 | 0.60 | 0.44 | 3 |
| qwen3:8b | v1 | deterministic | 100 | 0 | 0 | 7.9 | 16.7 | 0.000 | 0.47 | 0.62 | 0.37 | 0.36 | 3 |
| qwen3:8b | v1 | low | 100 | 0 | 0 | 8.7 | 17.0 | 0.000 | 0.47 | 0.62 | 0.37 | 0.36 | 3 |
| qwen3:8b | v2 | deterministic | 100 | 0 | 0 | 7.6 | 15.6 | 0.000 | 0.58 | 0.60 | 0.63 | 0.31 | 3 |
| qwen3:8b | v2 | low | 100 | 0 | 0 | 8.5 | 16.4 | 0.000 | 0.58 | 0.60 | 0.63 | 0.29 | 3 |

Golden-set accuracy per field (median over runs):

| model | prompt | sampling | call_type | direction | outcome | agent_handoff | recording_disclosed | disclaimer_before_benefits | obj P | obj R | obj F1 | handled |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| openai/gpt-4o-mini | v1 | deterministic | 0.80 | 0.10 | 0.60 | 0.90 | 0.60 | 0.50 | 0.67 | 0.40 | 0.50 | 0.00 |
| openai/gpt-4o-mini | v1 | low | 0.80 | 0.20 | 0.60 | 0.90 | 0.60 | 0.60 | 0.67 | 0.40 | 0.50 | 0.00 |
| openai/gpt-4o-mini | v2 | deterministic | 0.70 | 0.60 | 0.60 | 0.80 | 0.60 | 0.40 | 1.00 | 0.40 | 0.57 | 0.00 |
| openai/gpt-4o-mini | v2 | low | 0.70 | 0.60 | 0.60 | 0.90 | 0.60 | 0.30 | 1.00 | 0.40 | 0.57 | 0.00 |
| qwen3:14b | v1 | deterministic | 0.60 | 0.60 | 0.70 | 0.80 | 0.60 | 0.50 | 0.50 | 0.40 | 0.44 | 1.00 |
| qwen3:14b | v1 | low | 0.60 | 0.60 | 0.70 | 0.70 | 0.60 | 0.50 | 0.50 | 0.40 | 0.44 | 1.00 |
| qwen3:14b | v2 | deterministic | 0.60 | 0.60 | 0.60 | 0.80 | 0.60 | 0.70 | 0.50 | 0.40 | 0.44 | 1.00 |
| qwen3:14b | v2 | low | 0.60 | 0.60 | 0.60 | 0.80 | 0.60 | 0.70 | 0.50 | 0.40 | 0.44 | 1.00 |
| qwen3:8b | v1 | deterministic | 0.50 | 0.20 | 0.40 | 0.70 | 1.00 | 0.40 | 0.33 | 0.40 | 0.36 | 1.00 |
| qwen3:8b | v1 | low | 0.50 | 0.20 | 0.40 | 0.70 | 1.00 | 0.40 | 0.33 | 0.40 | 0.36 | 1.00 |
| qwen3:8b | v2 | deterministic | 0.80 | 0.60 | 0.50 | 0.70 | 0.90 | 0.50 | 0.25 | 0.40 | 0.31 | 0.50 |
| qwen3:8b | v2 | low | 0.80 | 0.60 | 0.50 | 0.70 | 0.90 | 0.50 | 0.22 | 0.40 | 0.29 | 0.50 |
