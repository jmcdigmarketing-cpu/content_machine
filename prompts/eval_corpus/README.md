# Prompt-eval corpus

Drop adversarial / reference prompt files here (`*.md`, `*.txt`) — e.g. selected cases
from the `system_prompts_leaks` archive, or hand-written jailbreak / hallucination
prompts. `core/run_eval_corpus.py` replays each as a regression case:

```
py -m core.run_eval_corpus            # list loaded cases (no LLM spend)
EVAL_CORPUS_LLM=true py -m core.run_eval_corpus   # score each via core/prompt_evals
```

Files here (other than this README and the in-repo
`invented_release_date.md` fixture) are gitignored by default — keep leaked
prompts local so verbatim third-party corpora don't land in the repo. This
README is the directory marker. The original `invented_release_date` case is
tracked so `load_cases()` has something to list with EVAL_CORPUS_LLM off.
