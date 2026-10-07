# EMO-X developer shortcuts (roadmap: DX). Every target mirrors CI.
# `make gate` is the pre-push gate (REVIEW-X.md R1).

PY ?= python3
ROOT := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

.PHONY: gate selftest suites secrets-scan patterns-scan compile clean

gate: compile secrets-scan patterns-scan selftest suites

selftest:
	$(PY) shared/run.py --self-test

suites:
	$(PY) tests/run_all.py

compile:
	$(PY) -m compileall -q shared suites generators judges health mcp-server adapters tests

secrets-scan:
	! rg -n --pcre2 "(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|(?i:api[_-]?key\s*[:=]\s*['\"][^'\"]{8,}|password\s*[:=]\s*['\"][^'\"]{6,}|bearer\s+[A-Za-z0-9\-_.]{16,}))" \
	  --glob '!suites/security/fixtures/*' \
	  --glob '!security-bench/fixtures/*' \
	  --glob '!shared/PROMPT_PACK_v1.md' \
	  --glob '!reports/*' \
	  shared suites generators judges health mcp-server adapters tests prompts || exit 1

patterns-scan:
	! rg -n "shell\s*=\s*True|os\.system|import pickle|[^_.a-zA-Z]eval\(|[^_.a-zA-Z]exec\(" \
	  --glob '*.py' shared suites generators judges health mcp-server adapters tests || exit 1

clean:
	find . -path ./.git -prune -o -type d -name __pycache__ -print | xargs rm -rf
