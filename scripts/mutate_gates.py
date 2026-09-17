"""Mutation-test the gates (#627): does the suite notice when a gate is broken?

A gate that always returns False scores green in CI when nothing tests the blocking case -
the #715 comment-out guard and the #754 forced-overage test were both green on code that did
nothing. This breaks one decision at a time and runs the tests that name the function:

- a comparison flipped (`>` to `<=`, `==` to `!=`, `in` to `not in`, `is` to `is not`)
- `and` swapped with `or`
- a `not` removed
- a literal `return True` / `return False` inverted

The mutant exists only in a subprocess's memory - the function is recompiled from its
mutated source into its own module's namespace before the test modules load. No file is
edited. A mutant the tests still pass is a hole: add the test that kills it.

    py -m scripts.ops mutate-gates
    py -m scripts.ops mutate-gates --target claim_types
    py -m scripts.mutate_gates --list

Minutes, not seconds (one interpreter per mutant), so it is an ops verb and not in CI.
"""

from __future__ import annotations
import __future__ as future_flags

import argparse
import ast
import importlib
import inspect
import io
import os
import re
import subprocess
import sys
import textwrap
import unittest
from dataclasses import dataclass

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHILD_ENV = "MUTATION_CHILD"
_HARNESS_ERROR = 3

# The decisions that stop a render, a publish, or a public upload.
TARGETS: tuple[tuple[str, str], ...] = (
    ("core.claim_types", "normalize_type"),
    ("core.claim_types", "claim_blocks"),
    ("core.claim_types", "typed_unsupported"),
    ("core.claim_verifier", "gate_blocks"),
    ("core.negative_facts", "negative_gate_blocks"),
    ("core.relational_check", "merge_reversals"),
    ("core.spaced_queue", "slot_privacy"),
    ("core.spaced_queue", "_override_held"),
    ("core.cadence", "target_line"),
    ("core.thin_facts", "thin_facts_abort_reason"),
)

_FLIPS: dict[type, type] = {
    ast.Lt: ast.GtE,
    ast.GtE: ast.Lt,
    ast.Gt: ast.LtE,
    ast.LtE: ast.Gt,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
}


class _Mutator(ast.NodeTransformer):
    """Visits every mutable site in a fixed order; changes only the `target`-th one."""

    def __init__(self, target: int) -> None:
        self.target = target
        self.seen = 0
        self.description = ""

    def _hit(self, node: ast.AST, what: str) -> bool:
        hit = self.seen == self.target
        if hit:
            self.description = f"line {getattr(node, 'lineno', '?')}: {what}"
        self.seen += 1
        return hit

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        self.generic_visit(node)
        for j, op in enumerate(node.ops):
            flipped = _FLIPS.get(type(op))
            if flipped and self._hit(node, f"{type(op).__name__} -> {flipped.__name__}"):
                node.ops[j] = flipped()
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        is_and = isinstance(node.op, ast.And)
        if self._hit(node, "and -> or" if is_and else "or -> and"):
            node.op = ast.Or() if is_and else ast.And()
        return node

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.op, ast.Not) and self._hit(node, "not removed"):
            return node.operand
        return node

    def visit_Return(self, node: ast.Return) -> ast.AST:
        self.generic_visit(node)
        value = node.value
        if (
            isinstance(value, ast.Constant)
            and isinstance(value.value, bool)
            and self._hit(node, f"return {value.value} -> {not value.value}")
        ):
            value.value = not value.value
        return node


def function_source(module: str, name: str) -> str:
    return textwrap.dedent(inspect.getsource(getattr(importlib.import_module(module), name)))


def count_mutants(source: str) -> int:
    mutator = _Mutator(-1)
    mutator.visit(ast.parse(source))
    return mutator.seen


def describe_mutant(source: str, index: int) -> str:
    mutator = _Mutator(index)
    mutator.visit(ast.parse(source))
    return mutator.description


def apply_mutant(source: str, index: int) -> str:
    tree = ast.parse(source)
    _Mutator(index).visit(tree)
    return ast.unparse(ast.fix_missing_locations(tree))


def tests_for(name: str, module: str = "") -> list[str]:
    """Test modules that name the function or import its module.

    Name alone missed `claim_blocks`, which the suite reaches through `gate_blocks`.
    """
    terms = [rf"\b{re.escape(name)}\b"]
    if module:
        terms.append(re.escape(module))
    pattern = re.compile("|".join(terms))
    tests_dir = os.path.join(REPO_ROOT, "tests")
    out: list[str] = []
    for filename in sorted(os.listdir(tests_dir)):
        if not (filename.startswith("test_") and filename.endswith(".py")):
            continue
        try:
            with open(os.path.join(tests_dir, filename), encoding="utf-8") as f:
                if pattern.search(f.read()):
                    out.append(f"tests.{filename[:-3]}")
        except OSError:
            continue
    return out


def run_one(module: str, name: str, index: int, test_names: list[str]) -> int:
    """In the child: install the mutant, run the tests. 0 = survived, 1 = killed."""
    try:
        import tests  # noqa: F401 - the suite-wide store redirect, before anything else

        target = importlib.import_module(module)
        mutated = apply_mutant(function_source(module, name), index)
        code = compile(
            mutated,
            f"<mutant {module}.{name}#{index}>",
            "exec",
            flags=future_flags.annotations.compiler_flag,
            dont_inherit=True,
        )
        exec(code, target.__dict__)
        suite = unittest.defaultTestLoader.loadTestsFromNames(test_names)
    except Exception as exc:
        print(f"harness error: {exc}", file=sys.stderr)
        return _HARNESS_ERROR
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0, failfast=True).run(suite)
    return 0 if result.wasSuccessful() else 1


def mutant_status(
    module: str, name: str, index: int, test_names: list[str], *, timeout: int = 900
) -> str:
    """killed | survived | error"""
    env = {**os.environ, CHILD_ENV: "1"}
    argv = [sys.executable, "-m", "scripts.mutate_gates", "--run-one", module, name, str(index)]
    try:
        proc = subprocess.run(
            [*argv, *test_names],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "killed"  # a mutant that hangs the suite is noticed
    if proc.returncode == 0:
        return "survived"
    if proc.returncode == _HARNESS_ERROR:
        return "error"
    return "killed"


def run_mutant(module: str, name: str, index: int, test_names: list[str]) -> bool:
    return mutant_status(module, name, index, test_names) == "killed"


@dataclass
class MutantResult:
    target: str
    index: int
    description: str
    status: str


def mutate_all(*, target_filter: str = "", print_fn=print) -> list[MutantResult]:
    results: list[MutantResult] = []
    for module, name in TARGETS:
        label = f"{module}.{name}"
        if target_filter and target_filter not in label:
            continue
        source = function_source(module, name)
        total = count_mutants(source)
        test_names = tests_for(name, module)
        print_fn(f"\n{label}: {total} mutant(s), {len(test_names)} test module(s)")
        if not test_names:
            print_fn("  ! no test module names this function - every mutant survives")
        for index in range(total):
            description = describe_mutant(source, index)
            status = mutant_status(module, name, index, test_names) if test_names else "survived"
            results.append(MutantResult(label, index, description, status))
            marker = {"killed": "  ok  ", "survived": "  HOLE", "error": "  ERR "}[status]
            print_fn(f"{marker} #{index} {description}")
    killed = sum(1 for r in results if r.status == "killed")
    holes = [r for r in results if r.status == "survived"]
    print_fn(f"\nKilled {killed}/{len(results)}; {len(holes)} survived")
    for hole in holes:
        print_fn(f"  HOLE {hole.target} #{hole.index} {hole.description}")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mutation-test the gates (#627)")
    parser.add_argument("--run-one", nargs="+", metavar="ARG", help=argparse.SUPPRESS)
    parser.add_argument("--target", default="", help="only module.function containing this")
    parser.add_argument("--list", action="store_true", help="list targets and mutant counts")
    args = parser.parse_args(argv)

    if args.run_one:
        module, name, index, *test_names = args.run_one
        return run_one(module, name, int(index), test_names)
    if args.list:
        for module, name in TARGETS:
            source = function_source(module, name)
            print(
                f"{module}.{name}: {count_mutants(source)} mutant(s), tests: {len(tests_for(name, module))}"
            )
        return 0
    results = mutate_all(target_filter=args.target)
    return 1 if any(r.status == "error" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
