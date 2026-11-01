| model | prompt | sampling | valid 1st try % | repaired % | failed % | p50 s | p95 s | $ / 1k calls | call type acc (all) | extracted acc | inferred acc | objections F1 | golden runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-opus-5-5 | v1 | cli_default | 100 | 0 | 0 | 5.6 | 10.6 | 24.088 | 0.75 | 0.91 | 0.73 | 0.73 | 3 |
| claude-opus-5-5 | v2 | cli_default | 100 | 0 | 0 | 5.8 | 10.0 | 23.535 | 0.78 | 0.91 | 0.83 | 0.73 | 3 |
| openai/gpt-4o-mini | v1 | deterministic | 100 | 0 | 0 | 1.3 | 1.9 | 0.393 | 0.64 | 0.70 | 0.53 | 0.50 | 3 |
| openai/gpt-4o-mini | v1 | low | 100 | 0 | 0 | 1.3 | 1.8 | 0.392 | 0.58 | 0.70 | 0.53 | 0.50 | 3 |
| openai/gpt-4o-mini | v2 | deterministic | 100 | 0 | 0 | 1.3 | 2.3 | 0.446 | 0.69 | 0.72 | 0.67 | 0.57 | 3 |
| openai/gpt-4o-mini | v2 | low | 100 | 0 | 0 | 1.3 | 2.0 | 0.444 | 0.69 | 0.72 | 0.67 | 0.57 | 3 |
| qwen3:14b | v1 | deterministic | 100 | 0 | 0 | 12.9 | 35.7 | 0.000 | 0.61 | 0.60 | 0.67 | 0.40 | 3 |
| qwen3:14b | v1 | low | 100 | 0 | 0 | 13.3 | 25.6 | 0.000 | 0.61 | 0.60 | 0.67 | 0.40 | 3 |
| qwen3:14b | v2 | deterministic | 100 | 0 | 0 | 13.1 | 44.2 | 0.000 | 0.72 | 0.61 | 0.77 | 0.44 | 3 |
| qwen3:14b | v2 | low | 100 | 0 | 0 | 12.0 | 21.7 | 0.000 | 0.72 | 0.67 | 0.77 | 0.50 | 3 |
| qwen3:8b | v1 | deterministic | 100 | 0 | 0 | 6.1 | 13.3 | 0.000 | 0.53 | 0.61 | 0.47 | 0.43 | 3 |
| qwen3:8b | v1 | low | 100 | 0 | 0 | 6.1 | 9.0 | 0.000 | 0.53 | 0.61 | 0.47 | 0.43 | 3 |
| qwen3:8b | v2 | deterministic | 100 | 0 | 0 | 6.2 | 16.8 | 0.000 | 0.64 | 0.77 | 0.67 | 0.60 | 3 |
| qwen3:8b | v2 | low | 100 | 0 | 0 | 6.9 | 11.3 | 0.000 | 0.64 | 0.69 | 0.67 | 0.36 | 3 |

Golden-set accuracy per field (median over runs):

| model | prompt | sampling | call_type | direction | outcome | agent_handoff | recording_disclosed | obj P | obj R | obj F1 | handled |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-opus-5-5 | v1 | cli_default | 1.00 | 0.60 | 0.60 | 1.00 | 1.00 | 0.67 | 0.80 | 0.73 | 1.00 |
| claude-opus-5-5 | v2 | cli_default | 1.00 | 0.80 | 0.70 | 1.00 | 1.00 | 0.67 | 0.80 | 0.73 | 1.00 |
| openai/gpt-4o-mini | v1 | deterministic | 0.70 | 0.30 | 0.60 | 1.00 | 0.60 | 0.67 | 0.40 | 0.50 | 1.00 |
| openai/gpt-4o-mini | v1 | low | 0.70 | 0.30 | 0.60 | 1.00 | 0.60 | 0.67 | 0.40 | 0.50 | 1.00 |
| openai/gpt-4o-mini | v2 | deterministic | 0.90 | 0.50 | 0.60 | 0.80 | 0.80 | 1.00 | 0.40 | 0.57 | 0.00 |
| openai/gpt-4o-mini | v2 | low | 0.90 | 0.50 | 0.60 | 0.80 | 0.80 | 1.00 | 0.40 | 0.57 | 0.50 |
| qwen3:14b | v1 | deterministic | 0.70 | 0.60 | 0.70 | 0.80 | 0.60 | 0.40 | 0.40 | 0.40 | 1.00 |
| qwen3:14b | v1 | low | 0.70 | 0.60 | 0.70 | 0.80 | 0.60 | 0.40 | 0.40 | 0.40 | 1.00 |
| qwen3:14b | v2 | deterministic | 1.00 | 0.60 | 0.70 | 0.80 | 0.60 | 0.50 | 0.40 | 0.44 | 1.00 |
| qwen3:14b | v2 | low | 1.00 | 0.60 | 0.70 | 0.80 | 0.70 | 0.67 | 0.40 | 0.50 | 1.00 |
| qwen3:8b | v1 | deterministic | 0.60 | 0.40 | 0.40 | 0.70 | 0.70 | 0.33 | 0.60 | 0.43 | 1.00 |
| qwen3:8b | v1 | low | 0.60 | 0.40 | 0.40 | 0.70 | 0.70 | 0.33 | 0.60 | 0.43 | 1.00 |
| qwen3:8b | v2 | deterministic | 0.90 | 0.60 | 0.50 | 0.70 | 1.00 | 0.60 | 0.60 | 0.60 | 1.00 |
| qwen3:8b | v2 | low | 0.90 | 0.60 | 0.50 | 0.70 | 1.00 | 0.33 | 0.40 | 0.36 | 1.00 |
