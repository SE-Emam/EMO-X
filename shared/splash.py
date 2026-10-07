"""EMO-X hero splash screen (stdlib only).

Large centered blue ASCII logo shown on stderr at startup. Rules:
  - stderr ONLY: stdout stays machine-parseable (SPEC: raw bundles and
    report JSON must parse with or without the banner).
  - NO_COLOR respected; non-tty streams get plain (colorless) text.
  - Dynamic content (version/suite/manifest/test counts) is computed
    live from the code — never hardcoded.
  - --quiet (or enabled=False) silences it entirely.
"""

import os
import shutil
import sys

BLUE_BRIGHT = "\033[94m"
BLUE_DIM = "\033[34m"
CYAN = "\033[96m"
GRAY = "\033[90m"
RESET = "\033[0m"

LOGO_LINES = [
    "███████╗███╗   ███╗ ██████╗       ██╗  ██╗",
    "██╔════╝████╗ ████║██╔═══██╗      ╚██╗██╔╝",
    "█████╗  ██╔████╔██║██║   ██║█████╗ ╚███╔╝ ",
    "██╔══╝  ██║╚██╔╝██║██║   ██║╚════╝ ██╔██╗ ",
    "███████╗██║ ╚═╝ ██║╚██████╔╝      ██╔╝ ██╗",
    "╚══════╝╚═╝     ╚═╝ ╚═════╝       ╚═╝  ╚═╝",
]

TAGLINE = "Execution · Measurement · Observability"
MIN_WIDTH = 60


def _colors_enabled(stream=None):
    """False under NO_COLOR or when the stream is not a tty."""
    if os.environ.get("NO_COLOR"):
        return False
    try:
        target = stream if stream is not None else sys.stderr
        return bool(target.isatty())
    except Exception:
        return False


def collect_stats(root=None):
    """Live counts: version, suites, manifests, tests. Never raises."""
    stats = {"version": "unknown", "suites": 0, "manifests": 0, "tests": 0}
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        base = root or os.path.normpath(os.path.join(here, ".."))
        sys.path.insert(0, os.path.join(base, "shared"))
        try:
            import runner as _runner

            stats["version"] = str(getattr(_runner, "BENCHMARK_VERSION", "unknown"))
            stats["suites"] = len(getattr(_runner, "SUITE_DIRS", {}))
        finally:
            pass
        manifests = 0
        suites_dir = os.path.join(base, "suites")
        if os.path.isdir(suites_dir):
            for _dir, _sub, files in os.walk(suites_dir):
                manifests += sum(1 for f in files if f.endswith(".json") and "manifest" in _dir)
        stats["manifests"] = manifests
        tests = 0
        tests_dir = os.path.join(base, "tests")
        if os.path.isdir(tests_dir):
            for _dir, _sub, files in os.walk(tests_dir):
                for f in files:
                    if f.startswith("test_") and f.endswith(".py"):
                        path = os.path.join(_dir, f)
                        try:
                            with open(path, encoding="utf-8", errors="replace") as fh:
                                tests += fh.read().count("    def test_")
                        except OSError:
                            pass
        stats["tests"] = tests
    except Exception:
        pass
    return stats


def banner(stats=None, width=None, color=None):
    """Build the hero splash text. Pure function (no I/O)."""
    if stats is None:
        stats = collect_stats()
    try:
        term_width = int(width or shutil.get_terminal_size().columns)
    except Exception:
        term_width = 80
    use_color = (sys.stdout.isatty() if color is None else color) and not os.environ.get("NO_COLOR")

    def paint(text, code):
        return ("%s%s%s" % (code, text, RESET)) if use_color else text

    def center(text):
        pad = max(0, (min(term_width, 120) - len(text)) // 2)
        return " " * pad + text

    def center_painted(text, code=""):
        # Center on VISIBLE width: pad first, paint after (ANSI codes
        # must never enter the width computation).
        pad = max(0, (min(term_width, 120) - len(text)) // 2)
        if code and use_color:
            return " " * pad + code + text + RESET
        return " " * pad + text

    if term_width < MIN_WIDTH:
        # Compact fallback for narrow terminals/machines.
        lines = [
            paint("EMO-X v%s · %s" % (stats["version"], TAGLINE), BLUE_BRIGHT),
            paint(
                "%d suites · %d manifests · %d tests"
                % (stats["suites"], stats["manifests"], stats["tests"]),
                GRAY,
            ),
        ]
        return "\n".join(lines) + "\n"
    stats_text = "v%s · %d suites · %d manifests · %d tests" % (
        stats["version"],
        stats["suites"],
        stats["manifests"],
        stats["tests"],
    )
    # Frame fits the widest content (logo, tagline, or live stats line):
    # a longer version string must widen the frame, never overflow it
    # (overflow breaks the single-indent frame invariant).
    frame_w = max([len(line) for line in LOGO_LINES] + [len(TAGLINE), len(stats_text)]) + 8
    top = "╔" + "═" * (frame_w - 2) + "╗"
    bottom = "╚" + "═" * (frame_w - 2) + "╝"
    empty = "║" + " " * (frame_w - 2) + "║"

    def framed(text, code=""):
        # Paint applies to the INNER text only; the frame bars stay
        # plain so every line measures identically with/without color.
        inner = text.center(frame_w - 2)
        if code and use_color:
            return "║" + code + inner + RESET + "║"
        return "║" + inner + "║"

    def center_framed(text, code=""):
        plain = "║" + text.center(frame_w - 2) + "║"
        pad = max(0, (min(term_width, 120) - len(plain)) // 2)
        if code and use_color:
            return " " * pad + "║" + code + text.center(frame_w - 2) + RESET + "║"
        return " " * pad + plain

    lines = [center_painted(top, BLUE_DIM), center_painted(empty, BLUE_DIM)]
    for logo_line in LOGO_LINES:
        lines.append(center_framed(logo_line, BLUE_BRIGHT))
    lines.append(center_painted(empty, BLUE_DIM))
    lines.append(center_framed(TAGLINE, CYAN))
    lines.append(center_framed(stats_text, GRAY))
    lines.append(center_painted(empty, BLUE_DIM))
    lines.append(center_painted(bottom, BLUE_DIM))
    return "\n".join(lines) + "\n"


def should_show(args=None, stream=None):
    """True unless --quiet passed or output cannot render color/tty.

    Note: the banner goes to stderr, so non-tty stdout (piped JSON)
    still gets a banner on a tty stderr — callers that need total
    silence use --quiet.
    """
    argv = list(sys.argv[1:] if args is None else args)
    if "--quiet" in argv or "-q" in argv:
        return False
    return True


def print_banner(stream=None, stats=None, width=None, enabled=True):
    """Write the hero splash to stderr. Returns the text (or '')."""
    if not enabled:
        return ""
    text = banner(stats=stats, width=width, color=_colors_enabled(stream))
    target = stream if stream is not None else sys.stderr
    try:
        target.write(text)
        target.flush()
    except Exception:
        pass
    return text


def main(argv=None):
    """CLI: `python3 shared/splash.py [--print] [--width N] [--no-color]`.

    Prints the banner to stdout (for plugins/skills that capture stdout,
    e.g. the forge-agent plugin's splash action). Exit 0 always unless
    the tree is unreadable (never — collect_stats never raises).
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv:
        print(__doc__.strip().splitlines()[0])
        print("Usage: python3 shared/splash.py [--print] [--width N] [--no-color]")
        return 0
    width = None
    if "--width" in argv:
        try:
            width = int(argv[argv.index("--width") + 1])
        except (ValueError, IndexError):
            width = None
    color = "--no-color" not in argv and not os.environ.get("NO_COLOR")
    sys.stdout.write(banner(width=width, color=color))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
