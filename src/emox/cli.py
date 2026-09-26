"""`emo` console entry: hero splash, then the full run.py CLI.

`emo ...` behaves exactly like `python3 shared/run.py ...`, including
the stderr hero banner (silenced by --quiet) and JSON-clean stdout.
"""

import sys


def main(argv=None):
    """Entry point for the `emo` console script. Returns exit code."""
    import emox
    args = list(sys.argv[1:] if argv is None else argv)
    if args in (["--version"], ["-V"]):
        print("emo-x %s" % emox.__version__)
        return 0
    emox._boot()
    try:
        import run as _run
    except ImportError:
        from shared import run as _run
    return _run.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
