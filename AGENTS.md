# AGENTS.md

Entry point for coding agents (Cursor, Codex, and anything else reading `AGENTS.md`).
One source of truth — read them in this order:

0. **[docs/handoff.md](docs/handoff.md)** — *the mailbox.* What the other agent just
   did, what it left uncommitted, what it found broken. Read it before anything else and
   verify it against `git log`; write your own slot as your last edit before you stop.
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

Say what was broken and how you know. The message is the audit trail: name the
measurement, not the intention.

**Sign your commits.** Two agents work in this tree and both commit as the same git
author, so the trailer is the only per-commit record of who wrote a change:

```
Co-authored-by: Cursor <cursoragent@cursor.com>
Co-authored-by: Claude <noreply@anthropic.com>
```

Check the split at any time:

```bash
git log --format='%h %s' -i --grep='Co-authored-by: Cursor'
py -m scripts.ops agents
```

This reverses the earlier ban (hooks used to strip and reject these). The ban made the
two agents indistinguishable in history at exactly the moment the repo started running
both at once. `.githooks/commit-msg` now warns when a trailer is missing rather than
rejecting one, and still refuses "Generated with ..." — that is marketing, not
provenance. Enable the hooks once per clone:

```bash
git config core.hooksPath .githooks
```

More than one agent works in this repo at a time. Re-read a file immediately before
editing it, and never `git checkout` a file to discard changes you did not make.
