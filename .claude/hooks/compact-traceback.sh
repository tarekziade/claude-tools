#!/bin/bash
# Unified hook script to compact Python tracebacks in both user prompts and tool outputs
# Works with both UserPromptSubmit and PostToolUse hooks

set -euo pipefail

# Read hook input JSON from stdin
INPUT=$(cat)

# Extract hook event type
HOOK_EVENT=$(echo "$INPUT" | jq -r '.hook_event_name // "UserPromptSubmit"')

# Determine what text to process based on hook type
if [ "$HOOK_EVENT" = "UserPromptSubmit" ]; then
    # For user prompts, process the prompt text
    TEXT=$(echo "$INPUT" | jq -r '.prompt // ""')

    if [ -z "$TEXT" ]; then
        # No prompt to process
        echo "{}"
        exit 0
    fi

    # Compact tracebacks in the prompt
    COMPACTED=$(echo "$TEXT" | claude-trace-compactor --stdin --project-root "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || echo "$TEXT")

    # Return updated prompt
    jq -n --arg prompt "$COMPACTED" '{"updatedPrompt": $prompt}'

elif [ "$HOOK_EVENT" = "PostToolUse" ]; then
    # For tool outputs, process stdout and stderr
    TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')

    # Only process Bash tool outputs (where Python tracebacks would appear)
    if [ "$TOOL_NAME" != "Bash" ]; then
        echo "{}"
        exit 0
    fi

    # Extract stdout and stderr
    STDOUT=$(echo "$INPUT" | jq -r '.tool_response.stdout // ""')
    STDERR=$(echo "$INPUT" | jq -r '.tool_response.stderr // ""')

    # Compact tracebacks in both
    COMPACTED_STDOUT=""
    COMPACTED_STDERR=""

    if [ -n "$STDOUT" ]; then
        COMPACTED_STDOUT=$(echo "$STDOUT" | claude-trace-compactor --stdin --project-root "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || echo "$STDOUT")
    fi

    if [ -n "$STDERR" ]; then
        COMPACTED_STDERR=$(echo "$STDERR" | claude-trace-compactor --stdin --project-root "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || echo "$STDERR")
    fi

    # Return updated tool response
    jq -n \
        --arg stdout "$COMPACTED_STDOUT" \
        --arg stderr "$COMPACTED_STDERR" \
        '{
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "updatedResponse": {
                    "stdout": $stdout,
                    "stderr": $stderr
                }
            }
        }'
else
    # Unknown hook type, pass through
    echo "{}"
    exit 0
fi
