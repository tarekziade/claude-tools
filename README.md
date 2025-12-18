# claude-tools

Hooks and tools for Claude Code to enhance your development workflow.

## Overview

A collection of utilities designed to integrate seamlessly with [Claude Code](https://code.claude.com), Anthropic's official CLI tool. These tools use Claude Code's powerful hooks system to automatically improve the quality of information sent to the AI.

### What are Claude Code Hooks?

Claude Code hooks are user-defined shell commands that execute automatically at various points in Claude Code's lifecycle. They provide **deterministic control** over Claude Code's behavior by running actual code rather than relying on the LLM to choose to run them. Hooks can modify, approve, or block tool executions, add context, and automate workflows.

## Tools

### 🔧 Trace Compactor

A dependency-free Python module that automatically detects Python tracebacks in your prompts and replaces them with compact summaries. This dramatically reduces token usage while preserving the essential debugging information Claude needs.

**Perfect for:**
- Debugging sessions with large stack traces
- Reducing context window usage
- Preserving relevant frames while filtering noise
- Automatic deduplication of similar errors

**Key features:**
- Detects traceback blocks with robust regex patterns
- Intelligently scores and prioritizes relevant stack frames
- Compacts aggressively (no file I/O, no locals) to reduce token size
- Deterministic fingerprinting for error deduplication
- Project-aware: prioritizes frames from your code over stdlib/site-packages
- Zero dependencies - pure Python implementation

**Example transformation:**

Before (250+ tokens):
```
Traceback (most recent call last):
  File "/usr/local/lib/python3.11/site-packages/click/core.py", line 1130, in _main
    rv = self.invoke(ctx)
  File "/usr/local/lib/python3.11/site-packages/click/core.py", line 1657, in invoke
    return _process_result(sub_ctx.command.invoke(sub_ctx))
  File "/home/user/myproject/api/handlers.py", line 45, in handle_request
    result = process_data(payload)
  File "/home/user/myproject/api/processor.py", line 123, in process_data
    return data['items'][0]['value']
KeyError: 'value'
```

After (40 tokens):
```
<COMPACT_PY_TRACEBACK fingerprint=a3f5d91b2c>
Exception: KeyError: 'value'

Relevant frames:
- processor.py:123 in process_data → return data['items'][0]['value']
- handlers.py:45 in handle_request → result = process_data(payload)
</COMPACT_PY_TRACEBACK>
```

## Installation

### From GitHub (Latest)

```bash
pip install git+https://github.com/tarekziade/claude-tools.git
```

### From PyPI (Coming Soon)

```bash
pip install claude-tools
```

### For Development

```bash
git clone https://github.com/tarekziade/claude-tools.git
cd claude-tools
pip install -e .
```

## Usage

### As a Claude Code Hook (Recommended)

The most powerful way to use the trace compactor is as a Claude Code hook that automatically processes all prompts before they reach Claude.

**1. Install claude-tools:**

```bash
pip install git+https://github.com/tarekziade/claude-tools.git
```

**2. Configure the hook in your Claude settings:**

Add to `~/.claude/settings.json` (global) or `.claude/settings.json` (project-specific):

```json
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
    ]
  }
}
```

**3. Start using Claude Code normally!**

Any Python tracebacks in your prompts will be automatically compacted before being sent to Claude.

#### Advanced Hook Configuration

**Project-specific hook with custom frame limit:**

`.claude/settings.json`:
```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.prompt' | claude-trace-compactor --stdin --project-root \"$CLAUDE_PROJECT_DIR\" --max-frames 6 | jq -Rs '{\"updatedPrompt\": .}'",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

**Custom hook script for more control:**

`.claude/hooks/compact-trace.sh`:
```bash
#!/bin/bash
set -euo pipefail

# Read hook input
INPUT=$(cat)

# Extract prompt
PROMPT=$(echo "$INPUT" | jq -r '.prompt')

# Compact tracebacks
COMPACTED=$(echo "$PROMPT" | claude-trace-compactor \
  --stdin \
  --project-root "$CLAUDE_PROJECT_DIR" \
  --max-frames 4)

# Return updated prompt
jq -n --arg prompt "$COMPACTED" '{"updatedPrompt": $prompt}'
```

Make it executable and reference it in settings:
```bash
chmod +x .claude/hooks/compact-trace.sh
```

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/compact-trace.sh"
          }
        ]
      }
    ]
  }
}
```

### As a Python Library

```python
from ctools import rewrite_prompt_for_claude

# Basic usage
new_prompt = rewrite_prompt_for_claude(original_prompt)

# With project-aware frame scoring
new_prompt = rewrite_prompt_for_claude(
    original_prompt,
    project_root="/home/user/myproject",
    max_frames=4
)
```

### As a CLI Tool

```bash
# From stdin
cat error.log | claude-trace-compactor --stdin --project-root /path/to/project

# From file
claude-trace-compactor --file error.txt --project-root /path/to/project

# Custom frame limit
claude-trace-compactor --stdin --max-frames 6 --project-root .

# JSON output for programmatic use
claude-trace-compactor --stdin --json
```

## Configuration

### Hook Configuration Files

Claude Code supports three levels of hook configuration:

1. **User-level** (`~/.claude/settings.json`) - Global hooks for all projects
2. **Project-level** (`.claude/settings.json`) - Team-shared, version controlled
3. **Local project** (`.claude/settings.local.json`) - Personal overrides, not committed

### Environment Variables

When running as a hook, these variables are available:

- `$CLAUDE_PROJECT_DIR` - Project root directory (absolute path)
- `$CLAUDE_ENV_FILE` - File for persisting environment variables
- `$CLAUDE_CODE_REMOTE` - "true" if running remotely, empty if local

### Compactor Options

- `--stdin` - Read input from stdin
- `--file PATH` - Read input from file
- `--project-root PATH` - Path to your project (improves frame relevance scoring)
- `--max-frames N` - Maximum frames to include (default: 4)
- `--json` - Output structured JSON instead of text

## How It Works

The trace compactor uses a sophisticated scoring algorithm to identify the most relevant stack frames:

1. **Detection**: Uses robust regex to find Python traceback blocks
2. **Parsing**: Extracts frames, line numbers, function names, and exception details
3. **Scoring**: Ranks frames by relevance:
   - +100 points: Frames from your project code
   - +10 points: Non-stdlib/site-packages frames
   - Negative score: Older frames (further from error)
4. **Selection**: Picks top N frames (default: 4), preserving chronological order
5. **Compaction**: Generates compact summary with fingerprint for deduplication
6. **Replacement**: Replaces verbose traceback with compact version

## Hook Security

⚠️ **Important Security Note**: Hooks run arbitrary shell commands automatically. Always review and test hooks before adding them to your configuration. Malicious hooks can access, modify, or delete any files your user account can access.

**Best practices:**
- Always quote shell variables: `"$VAR"` not `$VAR`
- Validate and sanitize inputs
- Use absolute paths with `$CLAUDE_PROJECT_DIR`
- Test hooks in a safe environment first
- Review hooks regularly
- Keep sensitive files out of hook scope

## Testing

### Test the compactor directly

```bash
# Create a test traceback
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

# Test compaction
cat test_trace.txt | claude-trace-compactor --stdin --project-root /home/user/myproject
```

### Test the hook configuration

```bash
# Verify hooks are loaded
claude code /hooks

# Run in debug mode to see hook execution
claude code --debug

# Test hook command manually
echo '{"prompt":"Traceback (most recent call last):\n  File \"test.py\", line 1\nValueError: test"}' | \
  jq -r '.prompt' | \
  claude-trace-compactor --stdin | \
  jq -Rs '{"updatedPrompt": .}'
```

## Troubleshooting

### Hook not running

1. Verify hook configuration: `claude code /hooks`
2. Check settings file syntax (must be valid JSON)
3. Ensure `claude-trace-compactor` is in your PATH
4. Restart Claude Code session (hooks are loaded at startup)

### Hook timing out

Increase timeout in settings:
```json
{
  "type": "command",
  "command": "...",
  "timeout": 30
}
```

### Permission errors

Make sure hook scripts are executable:
```bash
chmod +x .claude/hooks/*.sh
```

## Roadmap

Future tools planned for claude-tools:

- 🔍 **Log Summarizer** - Compact lengthy log files intelligently
- 📊 **Diff Compressor** - Reduce large diffs to essential changes
- 🧪 **Test Output Formatter** - Clean up verbose test failures
- 🎯 **Context Injector** - Automatically add relevant project context
- 📝 **Memory System** - Persistent memory across Claude sessions

## Contributing

Contributions are welcome! Here's how you can help:

1. **Report bugs** - Open an issue with reproducible examples
2. **Suggest features** - Propose new hooks or improvements
3. **Submit PRs** - Add new tools or enhance existing ones
4. **Share configs** - Post your hook configurations

### Development Setup

```bash
git clone https://github.com/tarekziade/claude-tools.git
cd claude-tools
pip install -e .

# Run tests
python -m ctools.trace_compactor --stdin --project-root . < test_trace.txt

# Test as module
python -c "from ctools import rewrite_prompt_for_claude; print('Import successful')"
```

## Resources

- [Claude Code Documentation](https://code.claude.com/docs)
- [Hooks Guide](https://code.claude.com/docs/en/hooks-guide)
- [GitHub Repository](https://github.com/tarekziade/claude-tools)
- [Report Issues](https://github.com/tarekziade/claude-tools/issues)

## License

MIT License - see LICENSE file for details

## Author

Created by [Tarek Ziadé](https://github.com/tarekziade)

---

**Built for Claude Code** - Enhancing AI-assisted development, one hook at a time.
