.PHONY: help lint test install-hooks

help:
	@echo "Usage:"
	@echo "  make test    Run all tests (bats + pytest)"
	@echo "  make lint    Quick frontmatter check"
	@echo "  make install-hooks  Configure git to use .githooks/"

lint:
	@echo "Checking SKILL.md frontmatter..."
	@for skill in skills/*/SKILL.md; do \
	  head -10 "$$skill" | grep -q '^name:' || echo "FAIL: $$skill missing name"; \
	  head -10 "$$skill" | grep -q '^description:' || echo "FAIL: $$skill missing description"; \
	done

test:
	@echo "Running bats tests..."
	@bats tests/test_structure.bats
	@echo "Running pytest..."
	@uvx --from pytest pytest tests/test_deploy.py -v

install-hooks:
	@echo "Configuring git hooks path to .githooks"
	@git config core.hooksPath .githooks
	@echo "Git hooks will now run from .githooks/"
