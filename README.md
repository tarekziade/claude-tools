# claude-tools

Hooks and tools for Claude Code

## Overview

A collection of utilities to enhance your Claude Code experience. Currently includes:

### Trace Compactor

A dependency-free Python module that detects Python tracebacks in text and replaces them with compact summaries suitable for sending to Claude (or other LLMs) as an in-flight prompt hook.

**Key features:**
- Detect traceback blocks with robust regex
- Parse frames and exception lines from pasted tracebacks
- Compact aggressively (no file I/O by default, no locals) to reduce token size
- Deterministic fingerprinting for deduplication
- JSON output option for structured agent payloads
- Small CLI for local testing

## Installation

```bash
pip install claude-tools
```

## Usage

### As a library

```python
from ctools import rewrite_prompt_for_claude

new_prompt = rewrite_prompt_for_claude(
    original_prompt,
    project_root="/home/me/myproj"
)
```

### CLI

```bash
# From stdin
echo "Your text with traceback" | claude-trace-compactor --stdin --project-root /path/to/project

# From file
claude-trace-compactor --file error.txt --project-root /path/to/project --max-frames 4

# JSON output
claude-trace-compactor --stdin --json
```

## Development

### Setup

```bash
git clone https://github.com/tarekziade/claude-tools.git
cd claude-tools
pip install -e .
```

### Testing

The module is designed to be lightweight and dependency-free. You can test it directly:

```bash
python -m ctools.trace_compactor --stdin --project-root .
```

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
