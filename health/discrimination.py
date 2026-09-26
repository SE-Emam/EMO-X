"""Discrimination health (X-5, WP11). SPEC B50 / DEN C70.

A task's discrimination score requires at least 5 reference models, one
valid score per model, and non-constant inputs — otherwise NA (None),
never zero. The Pearson leave-one-task-out formula lives in
shared.scoring.discrimination and is imported, not reinvented.
"""

try:
    from scoring import discrimination as _pearson_discrimination
except ImportError:  # package-style import (repo root on sys.path)
    from shared.scoring import discrimination as _pearson_discrimination

MIN_REFERENCE_MODELS = 5

__all__ = ["discrimination_snapshot", "MIN_REFERENCE_MODELS",
           "build_model_task_matrix"]


def build_model_task_matrix(events):
    """Build {model: {task: mean_score}} over scored attempts. DEN C9.

    Missing eligibility flags default True; ERROR/VOID excluded.
    """
    try:
        from denominators import eligible_attempts
    except ImportError:
        from shared.denominators import eligible_attempts
    scored = eligible_attempts(list(events))
    acc = {}
    for e in scored:
        acc.setdefault((e.get("model_id"), e.get("task_family_id")),
                       []).append(float(e.get("score", 0) or 0))
    matrix = {}
    for (model, task), vals in acc.items():
        matrix.setdefault(model, {})[task] = sum(vals) / len(vals)
    return matrix


def discrimination_snapshot(task_scores_by_model, task_id):
    """Discrimination snapshot for one task. DEN C70 / SPEC B50.

    Returns dict with discrimination (None = NA when <5 models, missing
    scores, or constant inputs), n_models, eligible bool, reason.
    """
    models = [m for m, ts in task_scores_by_model.items()
              if ts.get(task_id) is not None]
    n_models = len(models)
    if n_models < MIN_REFERENCE_MODELS:  # C70
        return {"discrimination": None, "n_models": n_models,
                "eligible": False,
                "reason": "NA: fewer than 5 models (C70)"}
    value = _pearson_discrimination(task_scores_by_model, task_id,
                                    min_models=MIN_REFERENCE_MODELS)
    if value is None:
        return {"discrimination": None, "n_models": n_models,
                "eligible": False,
                "reason": "NA: missing scores or constant inputs (C70)"}
    return {"discrimination": value, "n_models": n_models,
            "eligible": True, "reason": "ok"}
