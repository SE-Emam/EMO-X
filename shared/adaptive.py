"""Adaptive difficulty controller D0-D7 (X-5, WP12). SPEC section 10.

Each task family lives on a difficulty ladder:

  D0 trivial  D1 standard  D2 perturbed  D3 constrained
  D4 adversarial  D5 recovery  D6 compound  D7 long-horizon

The controller observes pass history and selects the next difficulty:
pass repeatedly -> increase difficulty; fail consistently -> reduce
difficulty, or diagnose when already at the floor (D0). Output is an
ability curve (per-difficulty pass rate) instead of one fixed point.

Variant selection consumes generators VARIANT_DIFFICULTY_BUMP: a variant
with a higher bump expects a higher rung, so the recommendation carries
both a difficulty and a compatible variant.

Stdlib only. Pure observation logic (no I/O); English code.
"""

try:
    from mutations import VARIANT_DIFFICULTY_BUMP, VARIANT_LEVELS
except ImportError:  # package-style import (repo root on sys.path)
    try:
        from generators.mutations import (VARIANT_DIFFICULTY_BUMP,
                                          VARIANT_LEVELS)
    except ImportError:  # standalone `python shared/adaptive.py`
        VARIANT_DIFFICULTY_BUMP = {"canonical": 0, "paraphrase": 0,
                                   "naming": 1, "constraint": 1,
                                   "structural": 2, "adversarial": 2,
                                   "recovery": 3, "novel": 2}
        VARIANT_LEVELS = {"canonical": "C", "paraphrase": "P",
                          "naming": "S", "constraint": "S",
                          "structural": "S", "adversarial": "A",
                          "recovery": "R", "novel": "N"}

MIN_DIFFICULTY = 0
MAX_DIFFICULTY = 7

DIFFICULTY_LABELS = ("trivial", "standard", "perturbed", "constrained",
                     "adversarial", "recovery", "compound", "long-horizon")

PROMOTE_STREAK = 2  # consecutive passes required to step up (SPEC 10)
DEMOTE_STREAK = 2  # consecutive fails required to step down (SPEC 10)

ACTIONS = ("promote", "hold", "demote", "diagnose")

__all__ = ["AdaptiveController", "difficulty_label", "variant_for_difficulty",
           "MIN_DIFFICULTY", "MAX_DIFFICULTY", "DIFFICULTY_LABELS"]


def difficulty_label(difficulty):
    """Human label for a D0-D7 rung. SPEC 10."""
    if not MIN_DIFFICULTY <= difficulty <= MAX_DIFFICULTY:
        raise ValueError("difficulty must be D0-D7, got %r" % (difficulty,))
    return DIFFICULTY_LABELS[difficulty]


def variant_for_difficulty(difficulty):
    """Highest-bump variant compatible with a rung (uses the bump table).

    Rungs D0-D1 stay canonical/paraphrase; higher rungs unlock structural,
    adversarial, recovery, and finally novel material. Note: there is no
    dedicated "compound" variant — D6 and D7 both map to "novel"
    (novel instances serve the compound/long-horizon rungs). This is
    intentional: variant space ends at R/N levels while difficulty keeps
    rising via instance complexity, not new variant labels.
    """
    if difficulty <= 1:
        return "canonical"
    if difficulty == 2:
        return "structural"
    if difficulty == 3:
        return "constraint"
    if difficulty == 4:
        return "adversarial"
    if difficulty == 5:
        return "recovery"
    return "novel"


class AdaptiveController(object):
    """Per-family adaptive difficulty state. SPEC 10.

    Usage:
      ctl = AdaptiveController()
      ctl.observe("H3", difficulty=1, passed=True)
      nxt, action = ctl.recommend("H3", difficulty=1)
      curve = ctl.ability_curve("H3")
    """

    def __init__(self, promote_streak=PROMOTE_STREAK,
                 demote_streak=DEMOTE_STREAK):
        self.promote_streak = promote_streak
        self.demote_streak = demote_streak
        self._history = {}  # family -> list of (difficulty, passed_bool)

    def observe(self, family, difficulty, passed):
        """Record one evaluated attempt at a rung. SPEC 10."""
        if not MIN_DIFFICULTY <= difficulty <= MAX_DIFFICULTY:
            raise ValueError("difficulty must be D0-D7")
        self._history.setdefault(family, []).append(
            (difficulty, bool(passed)))

    def _streaks(self, family):
        hist = self._history.get(family, [])
        pass_run = fail_run = 0
        for _, ok in reversed(hist):
            if ok:
                if fail_run:
                    break
                pass_run += 1
            else:
                if pass_run:
                    break
                fail_run += 1
        return pass_run, fail_run

    def recommend(self, family, difficulty, variant="canonical"):
        """Next (difficulty, action, variant) from pass history. SPEC 10.

        Bump-aware: the variant's VARIANT_DIFFICULTY_BUMP shifts the
        effective rung so a hard variant at a low rung is not mistaken
        for evidence of low ability.
        """
        bump = VARIANT_DIFFICULTY_BUMP.get(variant, 0)
        effective = min(MAX_DIFFICULTY, difficulty + bump)
        pass_run, fail_run = self._streaks(family)
        if pass_run >= self.promote_streak and effective < MAX_DIFFICULTY:
            nxt = min(MAX_DIFFICULTY, difficulty + 1)
            return nxt, "promote", variant_for_difficulty(nxt)
        if fail_run >= self.demote_streak:
            if difficulty <= MIN_DIFFICULTY:
                # At the floor with consistent failure: diagnose, do not
                # invent a rung below D0 (SPEC 10: reduce or diagnose).
                return difficulty, "diagnose", variant
            nxt = max(MIN_DIFFICULTY, difficulty - 1)
            return nxt, "demote", variant_for_difficulty(nxt)
        return difficulty, "hold", variant

    def ability_curve(self, family):
        """Ability curve: per-rung pass rate + overall summary. SPEC 10.

        Returns {rung: rate-or-None (NA when unobserved), ..., "summary":
        {n_observed, best_rung, profile}}. Unobserved rungs are None (NA),
        never 0.
        """
        hist = self._history.get(family, [])
        by_rung = {}
        for rung in range(MIN_DIFFICULTY, MAX_DIFFICULTY + 1):
            vals = [1 if ok else 0 for d, ok in hist if d == rung]
            by_rung[rung] = (sum(vals) / len(vals)) if vals else None
        observed = {r: v for r, v in by_rung.items() if v is not None}
        best = max(observed, key=lambda r: (observed[r], -r)) \
            if observed else None
        curve = dict(by_rung)
        curve["summary"] = {"n_observed": len(hist),
                            "n_rungs_observed": len(observed),
                            "best_rung": best,
                            "label": {r: difficulty_label(r)
                                      for r in range(MIN_DIFFICULTY,
                                                     MAX_DIFFICULTY + 1)}}
        return curve
