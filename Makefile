.PHONY: help install install-dev test test-verbose test-coverage lint format check clean build publish publish-test verify-install run-example

# Default Python interpreter
PYTHON := python3
PIP := $(PYTHON) -m pip

# Project directories
SRC_DIR := ctools
TEST_DIR := tests

help:
	@echo "claude-tools - Makefile commands"
	@echo ""
	@echo "Installation:"
	@echo "  make install          Install package in editable mode"
	@echo "  make install-dev      Install with development dependencies (ruff)"
	@echo "  make verify-install   Verify installation works correctly"
	@echo ""
	@echo "Development:"
	@echo "  make test             Run test suite"
	@echo "  make test-verbose     Run tests with verbose output"
	@echo "  make test-coverage    Run tests with coverage report (requires coverage)"
	@echo "  make lint             Run ruff linter"
	@echo "  make format           Format code with ruff"
	@echo "  make check            Run linter and tests (CI check)"
	@echo ""
	@echo "Building:"
	@echo "  make clean            Remove build artifacts and cache"
	@echo "  make build            Build distribution packages"
	@echo ""
	@echo "Publishing:"
	@echo "  make publish-test     Upload to TestPyPI"
	@echo "  make publish          Upload to PyPI (production)"
	@echo ""
	@echo "Examples:"
	@echo "  make run-example      Run example traceback compaction"

install:
	@echo "Installing claude-tools in editable mode..."
	$(PIP) install -e .
	@echo "✅ Installation complete!"
	@echo "Run 'make verify-install' to test the installation"

install-dev:
	@echo "Installing claude-tools with development dependencies..."
	$(PIP) install -e .
	$(PIP) install ruff
	@echo "✅ Development installation complete!"
	@echo "Available commands: make lint, make format, make test"

verify-install:
	@echo "Verifying installation..."
	@echo "1. Testing module import..."
	@$(PYTHON) -c "from ctools import rewrite_prompt_for_claude; print('   ✅ Module import successful')"
	@echo "2. Testing CLI command..."
	@claude-trace-compactor --help > /dev/null && echo "   ✅ CLI command available"
	@echo "3. Running syntax check..."
	@$(PYTHON) -m py_compile $(SRC_DIR)/*.py && echo "   ✅ Syntax check passed"
	@echo ""
	@echo "✅ Installation verified successfully!"

test:
	@echo "Running test suite..."
	@$(PYTHON) -m unittest discover -s $(TEST_DIR) -p "test_*.py"

test-verbose:
	@echo "Running test suite (verbose)..."
	@$(PYTHON) -m unittest discover -s $(TEST_DIR) -p "test_*.py" -v

test-coverage:
	@echo "Running tests with coverage..."
	@if command -v coverage >/dev/null 2>&1; then \
		coverage run -m unittest discover -s $(TEST_DIR) -p "test_*.py"; \
		coverage report -m; \
		coverage html; \
		echo ""; \
		echo "✅ Coverage report generated in htmlcov/index.html"; \
	else \
		echo "❌ Coverage not installed. Run: pip install coverage"; \
		exit 1; \
	fi

lint:
	@echo "Running ruff linter..."
	@if command -v ruff >/dev/null 2>&1; then \
		ruff check $(SRC_DIR) $(TEST_DIR); \
		echo "✅ Linting complete!"; \
	else \
		echo "❌ Ruff not installed. Run: make install-dev"; \
		exit 1; \
	fi

format:
	@echo "Formatting code with ruff..."
	@if command -v ruff >/dev/null 2>&1; then \
		ruff check --fix $(SRC_DIR) $(TEST_DIR); \
		ruff format $(SRC_DIR) $(TEST_DIR); \
		echo "✅ Formatting complete!"; \
	else \
		echo "❌ Ruff not installed. Run: make install-dev"; \
		exit 1; \
	fi

check: lint test
	@echo ""
	@echo "✅ All checks passed!"

clean:
	@echo "Cleaning build artifacts..."
	@rm -rf build/
	@rm -rf dist/
	@rm -rf *.egg-info
	@rm -rf $(SRC_DIR)/*.egg-info
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name "*.pyo" -delete
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf htmlcov/
	@rm -rf .coverage
	@echo "✅ Cleanup complete!"

build: clean
	@echo "Building distribution packages..."
	@if command -v $(PYTHON) -m build >/dev/null 2>&1; then \
		$(PYTHON) -m build; \
	else \
		echo "Installing build tools..."; \
		$(PIP) install build; \
		$(PYTHON) -m build; \
	fi
	@echo ""
	@echo "✅ Build complete! Packages in dist/"
	@ls -lh dist/

publish-test: build
	@echo "Uploading to TestPyPI..."
	@if command -v twine >/dev/null 2>&1; then \
		twine upload --repository testpypi dist/*; \
	else \
		echo "Installing twine..."; \
		$(PIP) install twine; \
		twine upload --repository testpypi dist/*; \
	fi
	@echo ""
	@echo "✅ Uploaded to TestPyPI!"
	@echo "Test installation: pip install --index-url https://test.pypi.org/simple/ claude-tools"

publish: build
	@echo "⚠️  WARNING: This will publish to PyPI (production)!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read -r
	@if command -v twine >/dev/null 2>&1; then \
		twine upload dist/*; \
	else \
		echo "Installing twine..."; \
		$(PIP) install twine; \
		twine upload dist/*; \
	fi
	@echo ""
	@echo "✅ Published to PyPI!"
	@echo "Install with: pip install claude-tools"

run-example:
	@echo "Creating example traceback..."
	@echo 'Traceback (most recent call last):\n  File "/usr/lib/python3.11/site-packages/click/core.py", line 100, in invoke\n    return callback()\n  File "/home/user/myproject/main.py", line 20, in main\n    process_data()\n  File "/home/user/myproject/processor.py", line 10, in process_data\n    return data["missing"]\nKeyError: "missing"' | $(PYTHON) -m ctools.trace_compactor --stdin --project-root /home/user/myproject
	@echo ""
	@echo "✅ Example complete!"

# Development workflow shortcuts
.PHONY: dev-setup dev-check dev-format-check

dev-setup: install-dev verify-install
	@echo ""
	@echo "🚀 Development environment ready!"
	@echo "Next steps:"
	@echo "  - Run 'make test' to run tests"
	@echo "  - Run 'make check' before committing"
	@echo "  - Run 'make format' to auto-format code"

dev-check: format lint test
	@echo ""
	@echo "✅ Development checks complete - ready to commit!"

dev-format-check:
	@echo "Checking code formatting..."
	@if command -v ruff >/dev/null 2>&1; then \
		ruff format --check $(SRC_DIR) $(TEST_DIR); \
		echo "✅ Code formatting is correct!"; \
	else \
		echo "❌ Ruff not installed. Run: make install-dev"; \
		exit 1; \
	fi
