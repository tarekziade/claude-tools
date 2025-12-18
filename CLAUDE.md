# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**claude-tools** is a Python package providing hooks and utilities for Claude Code. The primary tool is a traceback compactor that intelligently reduces Python stack traces to save tokens while preserving debugging information.

**Core Design Principles:**
- Zero runtime dependencies (pure Python stdlib)
- Fast execution (runs as CLI hook with timeouts)
- Python 3.8+ compatibility
- Deterministic and testable

## Quick Start Commands

```bash
# Development setup
make install-dev        # Install with dev dependencies (ruff, coverage)
make verify-install     # Verify installation works

# Testing
make test              # Run 32-test suite
make test-verbose      # Verbose test output
python3 -m unittest tests.test_trace_compactor.TestParseTraceback -v  # Run specific test class

# Code quality
make format            # Auto-format with ruff
make lint              # Check code quality
make dev-check         # Format + lint + test (run before committing)

# Build & publish
make clean             # Remove build artifacts
make build             # Build distribution packages
make publish-test      # Upload to TestPyPI
make publish           # Upload to PyPI

# View all commands
make help
```

## Architecture

### High-Level Design

The project implements a **hook-based traceback compaction system** that intercepts text at two points:

1. **User input** (UserPromptSubmit hook) - Compacts tracebacks you paste
2. **Tool output** (PostToolUse hook) - Compacts tracebacks from Python scripts Claude runs

**Data flow:**
```
Text with traceback
    ↓
Regex detection (TRACEBACK_BLOCK_RE)
    ↓
Parse frames (FRAME_RE, CODE_RE, EXC_LINE_RE)
    ↓
Score frames (project_root bonus: +100, user code: +10, recency: -index)
    ↓
Select top N frames (default: 4)
    ↓
Generate compact summary with fingerprint
    ↓
Replace verbose block with <COMPACT_PY_TRACEBACK>
```

### Key Components

**1. Core Module** (`ctools/trace_compactor.py`)

Main functions:
- `parse_traceback_text(text)` - Extract frames and exception from traceback text
- `compact_traceback_block(parsed, max_frames, project_root)` - Score and select relevant frames
- `rewrite_prompt_for_claude(prompt, project_root, max_frames)` - Main entry point, replaces all tracebacks
- `_frame_score(frame, project_root)` - Scoring algorithm for frame relevance
- `_fingerprint(frames, exception)` - Deterministic hash for deduplication

**2. Hook Script** (`.claude/hooks/compact-traceback.sh`)

Unified script handling both hook types:
- Detects hook type via `hook_event_name` field
- Routes to appropriate processing (prompt vs tool output)
- Calls `claude-trace-compactor` CLI with `--stdin`
- Returns JSON in correct format for each hook type

**3. CLI** (`claude-trace-compactor` command)

Entry point: `_cli_main()` in `trace_compactor.py`
- Registered in `pyproject.toml` under `[project.scripts]`
- Options: `--stdin`, `--file`, `--project-root`, `--max-frames`, `--json`

### Frame Scoring Algorithm

Critical to understand for modifications:

```python
def _frame_score(frame, project_root):
    score = -frame['raw_index']  # Recency: recent frames score higher

    if project_root and frame['filename'].startswith(project_root):
        score += 100  # Project frames highest priority

    if not _is_stdlib_or_site_packages(frame['filename']):
        score += 10   # User code over library code

    return score
```

Frames are sorted by score (descending), top N selected, then re-sorted by `raw_index` to preserve chronological order.

### Regex Patterns

**TRACEBACK_BLOCK_RE** - Matches complete traceback blocks:
- Starts with `Traceback (most recent call last):`
- Captures one or more frame lines (`File "...", line N, in func`)
- Optional code line after each frame
- Ends with exception line (`Error|Exception|Warning...`)

**FRAME_RE** - Extracts frame components:
- Captures: filename, line number, function name

**EXC_LINE_RE** - Extracts exception details:
- Captures: exception type, message

### Test Structure

```
tests/
├── test_trace_compactor.py     # Core functionality (6 test classes)
│   ├── TestParseTraceback      # Parsing logic
│   ├── TestCompactTraceback    # Compaction logic
│   ├── TestRewritePrompt       # Full pipeline
│   ├── TestFrameScoring        # Scoring algorithm
│   ├── TestEdgeCases           # Malformed input, unicode
│   └── TestFingerprinting      # Deduplication
└── test_cli.py                 # CLI tests (2 test classes)
    ├── TestCLI                 # Basic CLI operations
    └── TestCLIIntegration      # Real-world scenarios
```

**32 total tests** - All use stdlib `unittest`, zero test dependencies.

## Development Workflow

### Pre-commit Checklist

**Always run before committing:**
```bash
make dev-check   # Formats, lints, and tests
```

This runs:
1. `ruff format` - Auto-format code
2. `ruff check` - Lint with auto-fix
3. `python3 -m unittest` - Run all tests

### Adding New Tools

When adding additional tools to `ctools/`:

1. **Create module** in `ctools/` (e.g., `ctools/log_summarizer.py`)
2. **Export main functions** in `ctools/__init__.py`
3. **Add CLI entry point** in `pyproject.toml`:
   ```toml
   [project.scripts]
   claude-log-summarizer = "ctools.log_summarizer:_cli_main"
   ```
4. **Follow module template**:
   ```python
   """
   ctools.your_tool
   ----------------
   Description...
   """
   from __future__ import annotations
   import argparse
   from typing import Optional, List

   __all__ = ["main_function"]

   def main_function(text: str) -> str:
       """Core logic."""
       pass

   def _cli_main(argv: Optional[List[str]] = None) -> int:
       """CLI entry point."""
       parser = argparse.ArgumentParser(prog="claude-your-tool")
       # ... setup
       return 0

   if __name__ == "__main__":
       import sys
       raise SystemExit(_cli_main())
   ```
5. **Maintain zero dependencies** unless absolutely necessary
6. **Add tests** in `tests/test_your_tool.py`
7. **Update README** with usage examples

### Modifying Frame Scoring

If changing frame relevance logic:

1. **Edit `_frame_score()`** in `trace_compactor.py`
2. **Update tests** in `TestFrameScoring` class
3. **Test with real tracebacks**:
   ```bash
   cat your_traceback.txt | claude-trace-compactor --stdin --project-root /path/to/project
   ```
4. **Verify hook behavior**:
   ```bash
   echo '{"prompt":"Traceback..."}' | .claude/hooks/compact-traceback.sh
   ```

### Testing Hook Integration

**Manual hook testing:**
```bash
# Test UserPromptSubmit hook
echo '{"prompt":"Traceback (most recent call last):\n  File \"test.py\", line 1\nValueError: test", "hook_event_name": "UserPromptSubmit"}' | \
  .claude/hooks/compact-traceback.sh

# Test PostToolUse hook
echo '{"tool_name":"Bash","tool_response":{"stdout":"Traceback (most recent call last):\n  File \"test.py\", line 1\nValueError: test"},"hook_event_name":"PostToolUse"}' | \
  .claude/hooks/compact-traceback.sh
```

**Verify hooks loaded in Claude Code:**
```bash
# In Claude Code session, run:
/hooks
```

### Python Version Compatibility

Target: Python 3.8+

Required imports for compatibility:
```python
from __future__ import annotations  # Use in all modules
from typing import Optional, List, Dict, Any  # Explicit types for 3.8
```

Avoid:
- `str | None` syntax (use `Optional[str]`)
- `list[str]` syntax (use `List[str]`)
- Walrus operator `:=` in critical paths (acceptable in tests)

## Code Style & Standards

**Enforced by ruff** (configured in `pyproject.toml`):
- Line length: 100 characters
- Double quotes for strings
- Space indentation
- PEP 8 compliant
- Import sorting (isort)

**Enabled checks:**
- E/W (pycodestyle errors/warnings)
- F (pyflakes - unused imports/variables)
- I (isort - import sorting)
- UP (pyupgrade - modern Python syntax)
- B (bugbear - common bugs)
- C4 (comprehensions)
- SIM (simplify)

**Type hints:**
- Use for public API functions
- Optional for internal helpers
- Always annotate return types

## Hook Configuration

The `.claude/settings.json` configures both hooks to use the unified script:

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/compact-traceback.sh",
        "timeout": 10
      }]
    }],
    "PostToolUse": [{
      "matcher": "Bash",
      "hooks": [{
        "type": "command",
        "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/compact-traceback.sh",
        "timeout": 10
      }]
    }]
  }
}
```

**Environment variables available in hooks:**
- `$CLAUDE_PROJECT_DIR` - Absolute path to project root
- `$CLAUDE_ENV_FILE` - File for persisting environment variables
- `$CLAUDE_CODE_REMOTE` - "true" if remote, empty if local

## Important Implementation Details

### Why No Dependencies?

Hooks must execute quickly (10s timeout) and work in any environment. External dependencies:
- Increase installation complexity
- May not be available in user's environment
- Slow down hook execution
- Create version conflicts

### Fingerprinting Algorithm

```python
def _fingerprint(frames, exception_lines):
    h = hashlib.sha1()
    for f in frames:
        h.update(f"{f['filename']}:{f['lineno']}:{f['name']}".encode())
    for exc in exception_lines:
        h.update(exc.encode())
    return h.hexdigest()[:10]
```

Used for:
- Deduplication of identical errors
- Recognizing recurring issues
- Deterministic (same traceback = same fingerprint)

### Compaction Format

Output template:
```
<COMPACT_PY_TRACEBACK fingerprint={10_char_hash}>
Exception: {exception_type}: {message}

Relevant frames:
- {basename}:{lineno} in {func} → {code_line}
- {basename}:{lineno} in {func} → {code_line}
...
</COMPACT_PY_TRACEBACK>
```

**Token savings:** Typically reduces 200-500 tokens to 30-50 tokens.

## Common Pitfalls

1. **Forgetting to run `make dev-check`** - Always run before committing
2. **Breaking Python 3.8 compatibility** - Test with older Python versions
3. **Adding dependencies** - Avoid unless absolutely necessary
4. **Modifying hook JSON output format** - Must match Claude Code's expected schema
5. **Ignoring hook timeouts** - Keep execution fast (<2s typical, 10s max)
6. **Not testing with real tracebacks** - Unit tests don't catch all edge cases

## Debugging

### Hook Not Running

1. Check hook configuration: Run `/hooks` in Claude Code
2. Verify syntax: `jq . .claude/settings.json`
3. Test CLI: `claude-trace-compactor --help`
4. Test script manually: `echo '{"prompt":"test"}' | .claude/hooks/compact-traceback.sh`
5. Check timeout: Increase in settings if needed

### Unexpected Compaction Results

1. Test CLI directly: `cat traceback.txt | claude-trace-compactor --stdin --project-root .`
2. Enable JSON output: `--json` flag shows structured data
3. Check frame scoring: Add debug prints in `_frame_score()`
4. Verify regex matching: Test TRACEBACK_BLOCK_RE with your input

### Test Failures

```bash
# Run specific failing test
python3 -m unittest tests.test_trace_compactor.TestParseTraceback.test_specific_case -v

# Run with debug output (add print statements to code)
python3 -m unittest tests.test_cli -v
```

## Project-Specific Conventions

### Commit Messages

Use conventional commits:
- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation only
- `refactor:` - Code refactoring
- `test:` - Test changes
- `chore:` - Maintenance

Examples from git history:
```
feat: add dual hook support for complete traceback compaction
test: add comprehensive test suite with 32 tests
docs: add transparency and verification section
```

### File Organization

```
ctools/                     # Package code (pure Python, no dependencies)
  ├── __init__.py          # Public API exports
  └── trace_compactor.py   # Main module (~400 lines)

tests/                      # Test suite (uses stdlib unittest)
  ├── __init__.py
  ├── test_trace_compactor.py  # Core tests (~500 lines)
  └── test_cli.py              # CLI tests (~200 lines)

.claude/                    # Claude Code configuration
  ├── settings.json        # Hook configuration (checked in)
  └── hooks/
      └── compact-traceback.sh  # Unified hook script

Makefile                    # All development commands
pyproject.toml             # Package metadata, build config, ruff config
README.md                  # User documentation
```

### When to Add Tests

**Always add tests when:**
- Adding new public API functions
- Modifying frame scoring algorithm
- Changing regex patterns
- Adding CLI options
- Fixing bugs (add regression test)

**Test naming convention:**
- `test_<function_name>_<scenario>` for unit tests
- `test_<feature>_integration` for integration tests

## Resources

- Repository: https://github.com/tarekziade/claude-tools
- Claude Code Docs: https://code.claude.com/docs
- Hooks Guide: https://code.claude.com/docs/en/hooks-guide
