RTK := $(shell command -v rtk 2>/dev/null)

define maybe_rtk
$(if $(RTK),rtk $(1),$(1))
endef

.PHONY: install dev test test-unit test-integration lint typecheck mcdc mcdc-eval mcdc-coverage mcdc-coverage-eval docs-map agent-setup validate-docs validate-agent-docs detect-large-context-docs detect-large-agent-files check-context-staleness audit-module-cards audit-task-logs check-architecture-boundaries update-module-cards targeted-tests task-trace rtk-gain git-status git-diff test-unit-compact lint-compact typecheck-compact understand understand-dashboard understand-search validate-understand-graph retrieval-eval

install:
	python -m pip install -e ".[dev]"

dev:
	python -m uvicorn src.api.app:app --reload --host 127.0.0.1 --port 8000

test: test-unit test-integration

test-unit:
	python -m pytest tests/unit

test-integration:
	python -m pytest tests/integration

lint:
	python -m compileall src tests

typecheck:
	python -m compileall src tests

mcdc:
	@if [ -z "$(SOURCE)" ]; then echo "Usage: make mcdc SOURCE=path/to/file.c"; exit 2; fi
	python -m src.cli "$(SOURCE)" $(foreach header,$(HEADERS),--header "$(header)") $(foreach include,$(INCLUDES),-I "$(include)") $(foreach flag,$(CFLAGS),--compile-flag="$(flag)") $(if $(TARGET),--target-function "$(TARGET)",) $(if $(MODE),--mcdc-mode "$(MODE)",) -o "$(if $(OUT),$(OUT),build/mcdc)"

mcdc-eval:
	python scripts/evaluate_mcdc_fixtures.py

mcdc-coverage:
	@if [ -z "$(SOURCE)" ] || [ -z "$(TARGET)" ]; then echo "Usage: make mcdc-coverage SOURCE=path/to/file.c TARGET=target_func"; exit 2; fi
	python scripts/run_llvm_mcdc_coverage.py "$(SOURCE)" --target-function "$(TARGET)" $(if $(MODE),--mcdc-mode "$(MODE)",) --output-dir "$(if $(OUT),$(OUT),build/llvm-mcdc)"

mcdc-coverage-eval:
	python scripts/evaluate_llvm_mcdc_fixtures.py

docs-map:
	python scripts/generate_codemap.py

agent-setup:
	python scripts/agent_setup.py

validate-docs:
	python scripts/validate_docs.py

validate-agent-docs:
	python scripts/validate_agent_docs.py

detect-large-context-docs:
	python scripts/detect_large_context_docs.py

detect-large-agent-files:
	python scripts/detect_large_agent_files.py

check-context-staleness:
	python scripts/check_context_staleness.py

audit-module-cards:
	python scripts/audit_module_cards.py

audit-task-logs:
	python scripts/audit_task_logs.py

check-architecture-boundaries:
	python scripts/check_architecture_boundaries.py

update-module-cards:
	python scripts/update_module_cards.py

targeted-tests:
	python scripts/run_targeted_tests.py

task-trace:
	python scripts/collect_task_trace.py

rtk-gain:
	@if command -v rtk >/dev/null 2>&1; then rtk gain; else echo "rtk not installed"; fi

git-status:
	$(call maybe_rtk,git status)

git-diff:
	$(call maybe_rtk,git diff)

test-unit-compact:
	$(call maybe_rtk,make test-unit)

lint-compact:
	$(call maybe_rtk,make lint)

typecheck-compact:
	$(call maybe_rtk,make typecheck)

understand:
	python scripts/understand_placeholder.py

understand-dashboard:
	@echo "Open the Understand Anything dashboard with the installed runtime command, for example /understand-dashboard."

understand-search:
	python scripts/search_understand_graph.py "$(QUERY)"

validate-understand-graph:
	python scripts/validate_understand_graph.py

retrieval-eval:
	python eval/retrieval/run_retrieval_eval.py
