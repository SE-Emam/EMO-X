"""Live progress reporting for EMO-X runs (stdlib only).

One ProgressReporter tracks a whole run: suite index, attempt counts,
current step title, running pass/fail tallies, elapsed time, and an
ETA estimated from finished-attempt pacing (always approximate —
rendered with "~", never promised).

Design rules:
  - stderr only, never stdout (stdout stays machine-readable).
  - No writes into events.jsonl: progress is ephemeral UI, and scored
    events must stay byte-identical with progress on or off (DEN: the
    leaderboard never mixes API differences with model quality — same
    for harness UI differences).
  - NullProgress is a drop-in no-op so call sites need no branching.
  - on_event callback receives snapshot() dicts for MCP
    notifications/progress emission.
"""

import sys
import time

_BAR_WIDTH = 20


def _fmt_secs(seconds):
    if seconds is None:
        return "~--:--"
    seconds = max(0, int(seconds))
    return "~%02d:%02d" % (seconds // 60, seconds % 60)


class NullProgress:
    """Drop-in no-op reporter. All methods accept anything, do nothing."""

    def start_run(self, *a, **k):
        return None

    def start_suite(self, *a, **k):
        return None

    def start_attempt(self, *a, **k):
        return None

    def finish_attempt(self, *a, **k):
        return None

    def finish_suite(self, *a, **k):
        return None

    def finish_run(self, *a, **k):
        return None

    def set_suite_index(self, *a, **k):
        return None

    def add_suite_total(self, *a, **k):
        return None

    def snapshot(self):
        return {}


class ProgressReporter:
    """Hierarchical run progress: run > suite > attempt (+ step title).

    Usage:
      prog = ProgressReporter()
      prog.start_run(total_suites=7)
      prog.start_suite("code25", suite_idx=1, total_attempts=75)
      prog.start_attempt("T14 H3 perturbed trial 2/3")
      ... run it ...
      prog.finish_attempt("PASS")
      prog.finish_suite()
      prog.finish_run()
    """

    def __init__(self, stream=None, enabled=True, bar_width=_BAR_WIDTH, on_event=None):
        self._stream = stream
        self.enabled = enabled
        self.bar_width = bar_width
        self.on_event = on_event
        self.reset()

    def reset(self):
        """Clear all counters (a reporter may be reused across runs)."""
        self.total_suites = 0
        self.suite_idx = 0
        self.suite = ""
        self.suite_total = 0
        self.done = 0
        self.passed = 0
        self.failed = 0
        self.title = ""
        self.t0 = None
        self.suite_t0 = None
        self._durations = []
        # Run-level aggregation (single operation bar across suites).
        self.run_total = 0
        self.run_done = 0
        self.run_passed = 0
        self.run_failed = 0

    @property
    def _out(self):
        return self._stream if self._stream is not None else sys.stderr

    def start_run(self, total_suites=1):
        """Begin a run (e.g. profile over N suites)."""
        self.reset()
        self.total_suites = max(1, int(total_suites))
        self.t0 = time.time()
        self._emit()
        return self

    def start_suite(self, suite, suite_idx=1, total_attempts=0):
        """Begin one suite; total_attempts sizes the bar (0 = unknown)."""
        self.suite = str(suite)
        self.suite_idx = int(suite_idx)
        self.suite_total = max(0, int(total_attempts))
        self.done = 0
        self.passed = 0
        self.failed = 0
        self.title = ""
        self.suite_t0 = time.time()
        if self.t0 is None:
            self.t0 = self.suite_t0
        self._emit()
        return self

    def start_attempt(self, title):
        """Announce the current step title before running it."""
        self.title = str(title)
        self._emit()
        return self

    def add_suite_total(self, n):
        """Add one suite's attempt total to the run-level bar."""
        self.run_total += max(0, int(n))
        return self

    def finish_attempt(self, status):
        """Record one finished attempt (status = primary_status string)."""
        now = time.time()
        if self.suite_t0 is not None:
            self._durations.append(now - self.suite_t0)
            self.suite_t0 = now
        self.done += 1
        self.run_done += 1
        if status == "PASS":
            self.passed += 1
            self.run_passed += 1
        else:
            self.failed += 1
            self.run_failed += 1
        self._emit()
        return self

    def finish_suite(self):
        """Close the suite line and break to a fresh line."""
        self._write("\n")
        return self

    def finish_run(self):
        """Close the run (final newline if anything was drawn)."""
        if self.enabled and (self.done or self.title):
            self._write("\n")
        return self

    def set_suite_index(self, idx):
        """Set the profile suite counter without resetting attempts."""
        self.suite_idx = int(idx)
        return self

    def elapsed(self):
        """Seconds since run start (0.0 if not started)."""
        if self.t0 is None:
            return 0.0
        return time.time() - self.t0

    def eta(self):
        """Estimated seconds remaining, or None when unknowable."""
        if self.done < 1 or self.suite_total < 1:
            return None
        pace = sum(self._durations) / len(self._durations)
        return pace * max(0, self.suite_total - self.done)

    def fraction(self):
        """0.0..1.0 of the current suite (0.0 when total unknown)."""
        if self.suite_total < 1:
            return 0.0
        return min(1.0, self.done / float(self.suite_total))

    def snapshot(self):
        """Machine-readable state for MCP notifications/progress."""
        eta = self.eta()
        return {
            "suite": self.suite,
            "suite_idx": self.suite_idx,
            "total_suites": self.total_suites,
            "done": self.done,
            "total": self.suite_total,
            "run_done": self.run_done,
            "run_total": self.run_total,
            "run_passed": self.run_passed,
            "run_failed": self.run_failed,
            "title": self.title,
            "passed": self.passed,
            "failed": self.failed,
            "elapsed_s": round(self.elapsed(), 1),
            "eta_s": None if eta is None else round(eta, 1),
        }

    def render(self):
        """One status line: run bar + suite detail + title + tallies."""
        frac = self.fraction()
        filled = int(round(frac * self.bar_width))
        bar = "█" * filled + "░" * (self.bar_width - filled)
        head = ""
        if self.run_total > 0:
            # Single operation bar across all suites (run-level).
            rfrac = min(1.0, self.run_done / float(self.run_total))
            rfilled = int(round(rfrac * self.bar_width))
            rbar = "█" * rfilled + "░" * (self.bar_width - rfilled)
            head = "[run %d/%d %s] " % (self.run_done, self.run_total, rbar)
        elif self.total_suites > 1:
            head = "[profile %d/%d] " % (self.suite_idx, self.total_suites)
        scope = ""
        if self.suite:
            if self.suite_total > 0:
                scope = "[%s %d/%d] " % (self.suite, self.done, self.suite_total)
            else:
                scope = "[%s] " % self.suite
        title = ("| %s " % self.title) if self.title else ""
        tallies = "✓%d ✗%d" % (self.passed, self.failed)
        elapsed = time.strftime("%M:%S", time.gmtime(self.elapsed()))
        line = "%s%s%s %3d%% %s%s · %s · %s %s" % (
            head,
            scope,
            bar,
            int(round(frac * 100)),
            title,
            tallies,
            elapsed,
            _fmt_secs(self.eta()),
            "",
        )
        return line.rstrip()

    def _emit(self):
        if self.on_event is not None:
            try:
                self.on_event(self.snapshot())
            except Exception:
                pass
        self._draw()

    def _write(self, text):
        if not self.enabled:
            return
        try:
            self._out.write(text)
            self._out.flush()
        except Exception:
            pass

    def _draw(self):
        if not self.enabled:
            return
        self._write("\r" + self.render())
