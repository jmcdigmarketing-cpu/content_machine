# Prompt-eval corpus

Drop adversarial / reference prompt files here (`*.md`, `*.txt`) — e.g. selected cases
from the `system_prompts_leaks` archive, or hand-written jailbreak / hallucination
prompts. `core/run_eval_corpus.py` replays each as a regression case:

```
py -m core.run_eval_corpus            # list loaded cases (no LLM spend)
EVAL_CORPUS_LLM=true py -m core.run_eval_corpus   # score each via core/prompt_evals
```

Files here (other than this README) are gitignored by default — keep the corpus local so
verbatim leaked prompts don't land in the repo. This README is the directory marker.
