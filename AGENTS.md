# AGENTS.md

Entry point for coding agents (Cursor, Codex, and anything else reading `AGENTS.md`).
One source of truth, three files — read them in this order:

1. **[.cursor/rules/content-machine.mdc](.cursor/rules/content-machine.mdc)** — *how to
   work here.* The failure mode this repo actually suffers from (features that ship
   green and do nothing), the test rules that catch it, and the definition of done.
   Read this even if your tool does not auto-load `.cursor/rules`.
2. **[CLAUDE.md](CLAUDE.md)** — *what this is.* Pipeline, entry points, the signal
   contract, the LLM router, and the hard rules.
3. **[docs/decisions.md](docs/decisions.md)** — *why.* ADR-lite. §18, §24, §25 and §26
   are required reading before you add any gate, check, or repair pass.
4. **[docs/agent_collaboration.md](docs/agent_collaboration.md)** — *how we work
   together.* Read it **before starting a project**: who decides what gets built, what
   each agent is reliably good at, and the two mistakes that keep recurring. Short.

Directory-scoped rules exist and are more specific than the above — obey them when you
are working in that directory:

- **[tests/CLAUDE.md](tests/CLAUDE.md)** — store isolation. Getting this wrong writes
  the operator's real quota state and silently disables paid signals in production.
- **[apis/CLAUDE.md](apis/CLAUDE.md)** — the signal contract, thread-safety, breaker
  layering, and the "never add a second cache" rule.

## The 30-second version

```powershell
ruff check .                                      # CI-blocking
ruff format --check .                             # CI-blocking
python -m unittest discover -s tests -t .         # CI-blocking; the `-t .` is load-bearing
```

Done means: lint clean, test count went **up**, the new test **failed before your
change**, `git status --short data/` is empty, and every function you added is
reachable from a real caller. Green tests alone have never been sufficient here — read
the table at the top of the rules file for four defects that were green.

## Commit messages

**No AI attribution.** No `Co-authored-by:` naming an agent, no "Generated with ...".
The operator rejected this explicitly. It is enforced by a hook, not just by this
paragraph — a written rule was not enough, since `e4d2242` landed one the commit after
the rule was added.

Enable it once per clone:

```bash
git config core.hooksPath .githooks
```

`.githooks/commit-msg` rejects agent co-author trailers and "Generated with" lines. Human
co-authors are unaffected. If your commit is refused, delete the trailer — do not pass
`--no-verify`.

More than one agent works in this repo at a time. Re-read a file immediately before
editing it, and never `git checkout` a file to discard changes you did not make.
