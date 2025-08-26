# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 Loyaltydraw.com, Inc.

# Simple helpers for local use and CI.
# Usage examples:
#   make verify    PERIOD=2025-07 BASE=https://audit.loyaltydraw.com
#   make reproduce PERIOD=2025-07 BASE=https://audit.loyaltydraw.com
#   make audit     PERIOD=2025-07 BASE=https://audit.loyaltydraw.com
#   make local-audit  (when winners.json & snapshot.csv are in the current folder)

PY ?= python3
PERIOD ?= 2025-07
BASE ?= https://audit.loyaltydraw.com

.PHONY: help verify reproduce audit local-verify local-reproduce local-audit

help:
	@echo "Targets:"
	@echo "  verify       : Run Levels 1 + 2 against $(BASE)/$(PERIOD)"
	@echo "  reproduce    : Run Level 3 (requires revealed seed); fails if missing"
	@echo "  audit        : Run Levels 1 + 2 + 3; Level 3 is skipped if seed not revealed"
	@echo "  local-verify : Levels 1 + 2 using ./winners.json + ./snapshot.csv"
	@echo "  local-reproduce : Level 3 using local files (requires revealed seed)"
	@echo "  local-audit  : Levels 1 + 2 + 3 using local files; skip Level 3 if no seed"

verify:
	$(PY) audit.py --period $(PERIOD) --base $(BASE) --level 1
	$(PY) audit.py --period $(PERIOD) --base $(BASE) --level 2

reproduce:
	$(PY) audit.py --period $(PERIOD) --base $(BASE) --level 3 --on-missing-seed error

audit:
	$(PY) audit.py --period $(PERIOD) --base $(BASE) --level all --on-missing-seed skip

local-verify:
	test -f winners.json && test -f snapshot.csv
	$(PY) audit.py --winners ./winners.json --snapshot ./snapshot.csv --level 1
	$(PY) audit.py --winners ./winners.json --snapshot ./snapshot.csv --level 2

local-reproduce:
	test -f winners.json && test -f snapshot.csv
	$(PY) audit.py --winners ./winners.json --snapshot ./snapshot.csv --level 3 --on-missing-seed error

local-audit:
	test -f winners.json && test -f snapshot.csv
	$(PY) audit.py --winners ./winners.json --snapshot ./snapshot.csv --level all --on-missing-seed skip
