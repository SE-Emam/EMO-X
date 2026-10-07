"""Tier 1 deterministic oracle interface. SPEC P6 judging hierarchy.

Pure functions: compare a model output against an expected value with
no model-name inspection (DEN C84). Returns verdict dicts.
"""


def exact_match(output, expected):
    """Exact string equality oracle. Returns {verdict, score}."""
    ok = str(output) == str(expected)
    return {"verdict": "PASS" if ok else "FAIL", "score": 1.0 if ok else 0.0}


def numeric_match(output, expected, tolerance=0.0):
    """Numeric comparison within tolerance. Returns {verdict, score}."""
    try:
        diff = abs(float(output) - float(expected))
    except (TypeError, ValueError):
        return {"verdict": "FAIL", "score": 0.0}
    ok = diff <= tolerance
    return {"verdict": "PASS" if ok else "FAIL", "score": 1.0 if ok else 0.0}


def set_match(output_items, expected_items):
    """Order-insensitive exact set equality oracle."""
    ok = set(output_items) == set(expected_items)
    return {"verdict": "PASS" if ok else "FAIL", "score": 1.0 if ok else 0.0}


def subset_match(output_items, required_items):
    """Pass iff all required items appear in the output."""
    missing = [r for r in required_items if r not in set(output_items)]
    if not missing:
        return {"verdict": "PASS", "score": 1.0}
    if not required_items:
        return {"verdict": "PASS", "score": 1.0}
    found = len(required_items) - len(missing)
    return {"verdict": "FAIL", "score": found / len(required_items)}
