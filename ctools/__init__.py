"""
claude-tools: Hooks and tools for Claude Code
"""

from ctools.trace_compactor import (
    rewrite_prompt_for_claude,
    compact_traceback_block,
    parse_traceback_text,
)

__version__ = "0.1.0"

__all__ = [
    "rewrite_prompt_for_claude",
    "compact_traceback_block",
    "parse_traceback_text",
]
