"""Update the suite and test count badges in the project README."""

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def suite_count():
    runner = ast.parse((ROOT / "shared" / "runner.py").read_text(encoding="utf-8"))
    for node in runner.body:
        value = None
        if isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == "SUITE_DIRS"
                for target in node.targets
            ):
                value = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "SUITE_DIRS":
                value = node.value
        if value is not None:
            suites = ast.literal_eval(value)
            if not isinstance(suites, dict):
                raise RuntimeError("SUITE_DIRS must be a dictionary literal")
            return len(suites)
    raise RuntimeError("Could not find SUITE_DIRS in shared/runner.py")


def test_count():
    result = subprocess.run(
        [sys.executable, str(ROOT / "tests" / "run_all.py"), "--count"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode:
        raise RuntimeError(f"Could not count tests:\n{result.stdout}{result.stderr}")
    counts = re.findall(r"^(\S+)\s+(-?\d+)\s*$", result.stdout, re.MULTILINE)
    totals = [int(count) for name, count in counts if name == "total"]
    suite_counts = [int(count) for name, count in counts if name != "total"]
    if (
        len(totals) != 1
        or not suite_counts
        or any(count < 0 for count in suite_counts)
        or totals[0] != sum(suite_counts)
    ):
        raise RuntimeError(
            f"Test runner returned an invalid count:\n{result.stdout}{result.stderr}"
        )
    return totals[0]


def replace_badge(readme, label, count, color, target):
    pattern = re.compile(
        rf"(\[!\[{re.escape(label)}\]\(https://img\.shields\.io/badge/{label.lower()}-)\d+"
        rf"(-{re.escape(color)}\)\]\({re.escape(target)}\))"
    )
    updated, replacements = pattern.subn(r"\g<1>%d\g<2>" % count, readme)
    if replacements != 1:
        raise RuntimeError(
            "Expected exactly one %s badge in README.md; found %d" % (label, replacements)
        )
    return updated


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail instead of writing when README metrics are stale",
    )
    args = parser.parse_args(argv)

    suites = suite_count()
    tests = test_count()
    current = README.read_text(encoding="utf-8")
    updated = replace_badge(current, "Suites", suites, "blue", "suites/")
    updated = replace_badge(updated, "Tests", tests, "green", "tests/run_all.py")

    if args.check:
        if current != updated:
            print(
                "README metrics are stale; expected suites=%d tests=%d" % (suites, tests),
                file=sys.stderr,
            )
            return 1
        print("README metrics are current: suites=%d tests=%d" % (suites, tests))
        return 0

    if current != updated:
        README.write_text(updated, encoding="utf-8")
    print("README metrics updated: suites=%d tests=%d" % (suites, tests))
    return 0


if __name__ == "__main__":
    sys.exit(main())
