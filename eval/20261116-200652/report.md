# Script model comparison

| model | idea | lang | time s | tok/s | calls | words/budget | beats | scene types | warnings |
|---|---|---|---|---|---|---|---|---|---|
| qwen3:4b | aasman-neela-kyun-hai | hinglish | 49.2 | 39.2 | 15 | 66/117 | 6 | 4 | 3 |
| qwen3:4b | eiffel-tower-bechne-wala-aadmi | hinglish | 75.6 | 42.8 | 19 | 166/133 | 8 | 4 | 3 |
| qwen3:4b | longest-day-planet | english | 23.2 | 43.0 | 2 | 61/100 | 5 | 4 | 1 |
| qwen3:8b | aasman-neela-kyun-hai | hinglish | 77.8 | 25.4 | 5 | 73/117 | 7 | 6 | 3 |
| qwen3:8b | eiffel-tower-bechne-wala-aadmi | | | | | | | | FAILED: timed out |
| qwen3:8b | longest-day-planet | english | 50.8 | 25.1 | 2 | 57/100 | 7 | 6 | 1 |
| gemma4:12b | aasman-neela-kyun-hai | hinglish | 96.3 | 13.2 | 2 | 107/117 | 7 | 6 | 0 |
| gemma4:12b | eiffel-tower-bechne-wala-aadmi | hinglish | 69.4 | 19.8 | 2 | 122/133 | 9 | 5 | 0 |
| gemma4:12b | longest-day-planet | english | 77.8 | 24.2 | 2 | 67/100 | 6 | 6 | 1 |

Scripts are in the per-model folders beside this file. Read them: the table cannot judge writing.
