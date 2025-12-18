# Claude Code Configuration for claude-tools

This file contains instructions and configuration for working on the claude-tools project with Claude Code.

## Project Overview

**claude-tools** is a Python package that provides hooks and utilities for Claude Code. The primary tool is a traceback compactor that intelligently reduces Python stack traces to save tokens while preserving essential debugging information.

## Quick Start with Makefile

The project is fully driven by a Makefile. All common tasks can be executed using `make` commands:

```bash
# First time setup
make install-dev        # Install with development dependencies
make verify-install     # Verify everything works

# Development workflow
make test              # Run tests
make lint              # Check code quality
make format            # Auto-format code
make check             # Run linter + tests (pre-commit check)

# View all commands
make help
```

**Most Common Commands:**
- `make dev-setup` - Complete development environment setup
- `make dev-check` - Format, lint, and test (run before committing)
- `make test-verbose` - Run tests with detailed output
- `make clean` - Remove all build artifacts

## Hook Architecture

This project uses a **dual hook strategy** to provide complete traceback compaction coverage:

### 1. UserPromptSubmit Hook
**Purpose:** Compact tracebacks in messages you paste

**Flow:**
```
User types message with traceback
    ↓
UserPromptSubmit hook fires
    ↓
compact-traceback.sh processes prompt
    ↓
Traceback compacted
    ↓
Claude receives compacted version
```

**Example:**
```
You: "Fix this error: [500 line traceback]"
  → Hook compacts to 40 lines
  → Claude sees: "Fix this error: <COMPACT_PY_TRACEBACK>..."
```

### 2. PostToolUse Hook
**Purpose:** Compact tracebacks from Python scripts Claude runs

**Flow:**
```
Claude decides to run Python script
    ↓
Bash tool executes script
    ↓
Script fails with traceback
    ↓
PostToolUse hook fires
    ↓
compact-traceback.sh processes stdout/stderr
    ↓
Traceback compacted
    ↓
Claude receives compacted version
```

**Example:**
```
Claude runs: python test.py
  → Script outputs 500 line traceback
  → Hook compacts to 40 lines
  → Claude sees compacted version
  → Saves ~460 lines of context!
```

### Why Both Hooks?

**Without PostToolUse hook:**
- Claude runs a Python script that fails
- Full traceback floods Claude's context
- Wastes tokens on irrelevant stdlib frames
- May hit context limits on complex debugging

**With PostToolUse hook:**
- Tracebacks are compacted before Claude sees them
- Only relevant frames preserved
- More context available for actual debugging
- Claude can iterate faster

### Unified Script Design

The `.claude/hooks/compact-traceback.sh` script handles both hooks:

```bash
# Detects hook type automatically
HOOK_EVENT=$(echo "$INPUT" | jq -r '.hook_event_name')

if [ "$HOOK_EVENT" = "UserPromptSubmit" ]; then
    # Process prompt text
    TEXT=$(echo "$INPUT" | jq -r '.prompt')
    # ...compact and return updatedPrompt
elif [ "$HOOK_EVENT" = "PostToolUse" ]; then
    # Process tool output
    STDOUT=$(echo "$INPUT" | jq -r '.tool_response.stdout')
    # ...compact and return updatedResponse
fi
```

This means:
- ✅ Single script to maintain
- ✅ Same compaction logic for both sources
- ✅ Easy to customize (edit one file)
- ✅ Consistent behavior

## Development Guidelines

### Code Style

- **Python Version**: Python 3.8+ (maintain broad compatibility)
- **Dependencies**: Zero runtime dependencies - keep core modules pure Python
- **Linting & Formatting**: Use ruff (configured in pyproject.toml)
- **Code Style**: PEP 8 compliant, enforced by ruff
- **Line Length**: 100 characters max
- **Type Hints**: Use where helpful for clarity

**Ruff Configuration:**
The project uses ruff for both linting and formatting:
- Checks: pycodestyle (E/W), pyflakes (F), isort (I), bugbear (B), and more
- Auto-formatting: `make format` formats all code
- Pre-commit check: `make check` runs linter + tests

### Testing Philosophy

Since this is a lightweight utility:
- Manual testing is acceptable for initial development
- Focus on real-world traceback examples
- Test with various Python versions (3.8, 3.9, 3.10, 3.11, 3.12)
- Verify CLI works on macOS, Linux, and Windows

### Key Files

```
claude-tools/
├── .claude/
│   ├── settings.json                  # Dual hook configuration
│   └── hooks/
│       └── compact-traceback.sh       # Unified hook script
├── ctools/
│   ├── __init__.py                    # Package exports
│   └── trace_compactor.py             # Main traceback compactor module
├── tests/
│   ├── __init__.py
│   ├── test_trace_compactor.py        # Core tests
│   └── test_cli.py                    # CLI tests
├── Makefile                           # Development automation
├── pyproject.toml                     # Package metadata and build config
├── README.md                          # User-facing documentation
├── CLAUDE.md                          # This file - for Claude Code
└── .gitignore                         # Python-specific ignores
```

## Common Development Tasks

### Installing for Development

Use the Makefile for easy setup:

```bash
# Install with development dependencies (ruff, coverage)
make install-dev

# Or just install the package in editable mode
make install

# Verify installation
make verify-install
```

This installs the package in editable mode, so changes take effect immediately.

### Running Tests

Use the Makefile for testing:

```bash
# Run all tests (32 tests)
make test

# Run with verbose output
make test-verbose

# Run with coverage report
make test-coverage
```

**Or use unittest directly:**

```bash
# Run all tests
python3 -m unittest discover -s tests -p "test_*.py" -v

# Run specific test categories
python3 -m unittest tests.test_trace_compactor -v  # Core functionality
python3 -m unittest tests.test_cli -v               # CLI tests
```

**Test Structure:**

```
tests/
├── __init__.py
├── test_trace_compactor.py    # Core module tests
│   ├── TestParseTraceback     # Parsing functionality
│   ├── TestCompactTraceback   # Compaction logic
│   ├── TestRewritePrompt      # Prompt rewriting
│   ├── TestFrameScoring       # Frame prioritization
│   ├── TestEdgeCases          # Error handling
│   └── TestFingerprinting     # Deduplication
└── test_cli.py                # CLI tests
    ├── TestCLI                # Basic CLI operations
    └── TestCLIIntegration     # Real-world scenarios
```

### Testing the Trace Compactor

```bash
# Test with example traceback
cat > test_trace.txt << 'EOF'
Traceback (most recent call last):
  File "/usr/local/lib/python3.11/site-packages/click/core.py", line 1130, in _main
    rv = self.invoke(ctx)
  File "/home/user/myproject/api/handlers.py", line 45, in handle_request
    result = process_data(payload)
  File "/home/user/myproject/api/processor.py", line 123, in process_data
    return data['items'][0]['value']
KeyError: 'value'
EOF

# Run compactor
python3 -m ctools.trace_compactor --stdin --project-root /home/user/myproject < test_trace.txt
```

### Testing as a Claude Hook

The project includes `.claude/settings.json` with **dual hook configuration**:

**Covers both cases:**
1. **UserPromptSubmit** - Compacts tracebacks in user messages
2. **PostToolUse** - Compacts tracebacks from Python scripts Claude runs

The configuration uses the unified script at `.claude/hooks/compact-traceback.sh` that automatically handles both hook types.

**To test:**

```bash
# The hooks are already configured in .claude/settings.json
# Just make sure the package is installed
make install

# Restart Claude Code to load the hooks
# Then try:
# 1. Paste a traceback in your message - it will be compacted
# 2. Ask Claude to run a Python script that errors - output will be compacted
```

**Manual inline configuration (for reference):**

```bash
mkdir -p .claude
cat > .claude/settings.json << 'EOF'
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.prompt' | claude-trace-compactor --stdin --project-root \"$CLAUDE_PROJECT_DIR\" | jq -Rs '{\"updatedPrompt\": .}'",
            "timeout": 10
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_response.stdout // \"\"' | claude-trace-compactor --stdin --project-root \"$CLAUDE_PROJECT_DIR\" | jq -Rs '{\"hookSpecificOutput\": {\"hookEventName\": \"PostToolUse\", \"updatedResponse\": {\"stdout\": .}}}'",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
EOF
```

**Key Benefits of Dual Hooks:**
- **User prompts**: You paste long tracebacks → automatically compacted
- **Tool outputs**: Claude runs Python that errors → output compacted before Claude sees it
- **Complete coverage**: All tracebacks are compacted, regardless of source

### Building for Distribution

Use the Makefile for building and publishing:

```bash
# Build distribution packages
make build

# Upload to TestPyPI (for testing)
make publish-test

# Upload to PyPI (production)
make publish
```

**Or manually:**

```bash
# Install build tools
pip install build twine

# Build distribution packages
python3 -m build

# Check distribution
twine check dist/*

# Upload to PyPI
twine upload dist/*
```

## Project Conventions

### Commit Messages

Follow conventional commits:
- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

Examples:
```
feat: add --json output option to trace compactor
fix: handle malformed traceback lines gracefully
docs: update README with hook configuration examples
refactor: improve frame scoring algorithm
```

### Adding New Tools

When adding a new tool to claude-tools:

1. Create new module in `ctools/` directory (e.g., `ctools/log_summarizer.py`)
2. Export main functions in `ctools/__init__.py`
3. Add CLI entry point in `pyproject.toml` under `[project.scripts]`
4. Update README with new tool documentation
5. Keep zero-dependency philosophy unless absolutely necessary

Example structure for new tool:

```python
"""
ctools.log_summarizer
---------------------

Description of what this tool does.
"""

from __future__ import annotations
import argparse
from typing import Optional, List

__all__ = [
    "summarize_logs",
]

def summarize_logs(text: str, max_lines: int = 10) -> str:
    """Main function that does the work."""
    pass

def _cli_main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(prog="claude-log-summarizer")
    # ... argument setup
    return 0

if __name__ == "__main__":
    import sys
    raise SystemExit(_cli_main())
```

## Integration with Claude Code

### Recommended Hook Configuration

For developers working on this project, add these hooks to `.claude/settings.local.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path' | { read file_path; if echo \"$file_path\" | grep -q '\\.py$'; then python3 -m py_compile \"$file_path\" 2>&1; if [ $? -ne 0 ]; then exit 2; fi; fi; }",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

This validates Python syntax after file edits.

### Testing Changes

**The Golden Rule:** Always run `make dev-check` before committing!

```bash
# Complete pre-commit check (format, lint, test)
make dev-check

# Or run steps individually:
make format      # Auto-format code
make lint        # Check code quality
make test        # Run all tests
```

**Manual checks (if needed):**

```bash
# Syntax check all Python files
find ctools -name "*.py" -exec python3 -m py_compile {} \;

# Test CLI works
python3 -m ctools.trace_compactor --help

# Test import works
python3 -c "from ctools import rewrite_prompt_for_claude; print('OK')"

# Manual test with real traceback
cat test_trace.txt | python3 -m ctools.trace_compactor --stdin
```

**When Adding New Features:**
1. Write tests first (TDD approach recommended)
2. Add test cases to appropriate test file in `tests/`
3. Run `make test` to verify tests fail initially
4. Implement the feature
5. Run `make dev-check` to format, lint, and test
6. Ensure all 32+ existing tests still pass

**Quick Development Workflow:**
```bash
# 1. Make changes to code
# 2. Run this before committing:
make dev-check

# If all passes, you're ready to commit!
```

## Architecture Notes

### Why Zero Dependencies?

The trace compactor is designed to run as a Claude Code hook, which means:
- Must execute quickly (hooks have timeouts)
- Should work in any Python environment
- Can't rely on external packages being installed
- Needs to be extremely reliable

### Frame Scoring Algorithm

The compactor uses a scoring system to identify the most relevant frames:

1. **Project frames** (+100): Files within `--project-root` get highest priority
2. **User code** (+10): Non-stdlib/site-packages files are prioritized
3. **Recency** (-index): More recent frames (closer to error) score higher
4. **Deduplication**: Same frame appearing multiple times only counted once

This ensures users see frames from their code, not deep in library internals.

### Fingerprinting

Each compacted traceback gets a deterministic fingerprint (first 10 chars of SHA1):
- Allows deduplication of identical errors
- Helps Claude recognize recurring issues
- Based on file paths, line numbers, and function names

## Future Tools (Roadmap)

Ideas for future additions to claude-tools:

### Log Summarizer
- Detect repeated log lines and show counts
- Group related log messages
- Highlight errors and warnings
- Compact timestamps

### Diff Compressor
- Reduce large git diffs to essential changes
- Skip generated files (package-lock.json, etc.)
- Highlight additions/deletions
- Context-aware trimming

### Test Output Formatter
- Compact pytest/unittest output
- Show only failed tests
- Clean up assertion diffs
- Preserve stack traces (with compactor)

### Context Injector
- SessionStart hook to add project context
- Include recent git commits
- Show open issues/PRs
- Add project-specific guidelines

### Memory System
- Persistent memory across Claude sessions
- Remember project decisions
- Track common issues and solutions
- Learn user preferences

## Tips for Working with Claude

When asking Claude to work on this project:

- **Be specific about changes**: "Update the regex in trace_compactor.py to also match AssertionError"
- **Reference existing code**: "Following the pattern in _frame_score(), add a similar function for..."
- **Test thoroughly**: "Run the test cases and verify the output matches expected format"
- **Maintain style**: "Keep the same docstring style and type hints"
- **Think about hooks**: "Ensure this change doesn't slow down hook execution"

## Known Issues

None currently. Report issues at: https://github.com/tarekziade/claude-tools/issues

## Resources

- [Claude Code Documentation](https://code.claude.com/docs)
- [Hooks Guide](https://code.claude.com/docs/en/hooks-guide)
- [Python Traceback Module](https://docs.python.org/3/library/traceback.html)
- [Ripgrep (rg) for testing](https://github.com/BurntSushi/ripgrep)

## Makefile Commands Reference

The project provides a comprehensive Makefile for all development tasks. Run `make help` to see all available commands.

### Installation Commands

| Command | Description |
|---------|-------------|
| `make install` | Install package in editable mode |
| `make install-dev` | Install with dev dependencies (ruff, coverage) |
| `make verify-install` | Verify installation works correctly |
| `make dev-setup` | Complete development environment setup |

### Development Commands

| Command | Description |
|---------|-------------|
| `make test` | Run test suite |
| `make test-verbose` | Run tests with verbose output |
| `make test-coverage` | Run tests with coverage report |
| `make lint` | Run ruff linter |
| `make format` | Format code with ruff |
| `make check` | Run linter + tests (CI check) |
| `make dev-check` | Format + lint + test (pre-commit) |
| `make dev-format-check` | Check if code is formatted |

### Build Commands

| Command | Description |
|---------|-------------|
| `make clean` | Remove build artifacts and cache |
| `make build` | Build distribution packages |

### Publishing Commands

| Command | Description |
|---------|-------------|
| `make publish-test` | Upload to TestPyPI |
| `make publish` | Upload to PyPI (production) |

### Example Commands

| Command | Description |
|---------|-------------|
| `make run-example` | Run example traceback compaction |

### Common Workflows

**First time setup:**
```bash
make dev-setup
# Installs dev dependencies and verifies installation
```

**Daily development:**
```bash
# Edit code...
make dev-check
# Formats, lints, and tests before commit
```

**Before committing:**
```bash
make dev-check
# Ensures code is formatted, linted, and tested
```

**Building for release:**
```bash
make clean
make build
make publish-test  # Test on TestPyPI first
make publish       # When ready for production
```

## Ruff Configuration

The project uses ruff for linting and formatting. Configuration is in `pyproject.toml`:

### Enabled Checks

- **E/W** - pycodestyle errors and warnings
- **F** - pyflakes (unused imports, variables, etc.)
- **I** - isort (import sorting)
- **UP** - pyupgrade (modernize Python syntax)
- **B** - flake8-bugbear (common bugs)
- **C4** - flake8-comprehensions (list/dict comprehensions)
- **SIM** - flake8-simplify (simplify code)

### Configuration Details

```toml
# From pyproject.toml
[tool.ruff]
target-version = "py38"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP", "B", "C4", "SIM"]
ignore = ["E501"]  # Line too long (handled by formatter)
fixable = ["ALL"]  # Auto-fix everything possible

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### Using Ruff

```bash
# Check code
make lint
# or: ruff check ctools tests

# Format code
make format
# or: ruff format ctools tests

# Check + auto-fix
ruff check --fix ctools tests
```

## License

MIT License - This project is open source and welcomes contributions.
