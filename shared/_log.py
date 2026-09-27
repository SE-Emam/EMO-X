"""Central stdlib logging for EMO-X CLIs and adapters (P1-02).

Stdlib ``logging`` only. Behavior-preserving rules:
  - Machine-readable stdout (JSON bundles, probe/trace payloads) is NEVER
    routed through here: those call sites keep print().
  - Human status lines move from print() to log.info(); infra errors that
    previously used print(..., file=sys.stderr) become log.warning().
  - The default handler writes bare messages (no timestamps or levels) to
    stderr, so converted lines render byte-identical to the old prints;
    only the stream changes (stdout -> stderr) for info lines, matching
    the splash/progress rule that stdout stays machine-parseable.
  - The hero splash and live progress bar stay on stderr as-is; they do
    not use this module.
"""

from __future__ import annotations

import logging
import sys

FORMAT = "%(message)s"
_ROOT_NAME = "emox"


def configure(level: int = logging.INFO, stream=None) -> logging.Logger:
    """Install the stderr handler on the ``emox`` logger (idempotent).

    Returns the ``emox`` logger. Safe to call from every CLI main():
    repeat calls only adjust the level, never duplicate handlers.
    """
    logger = logging.getLogger(_ROOT_NAME)
    logger.setLevel(level)
    for handler in logger.handlers:
        if getattr(handler, "_emox_handler", False):
            handler.setLevel(level)
            return logger
    handler = logging.StreamHandler(
        stream if stream is not None else sys.stderr)
    handler.setFormatter(logging.Formatter(FORMAT))
    handler.setLevel(level)
    handler._emox_handler = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return the ``emox.<name>`` logger (shares the configured handler)."""
    return logging.getLogger(_ROOT_NAME + "." + name)
