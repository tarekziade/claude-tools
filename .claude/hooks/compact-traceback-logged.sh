#!/bin/bash
# Unified hook script with optional logging for transparency
# Set CLAUDE_HOOK_LOG environment variable to enable logging

set -euo pipefail

# Optional logging function
log() {
    if [ -n "${CLAUDE_HOOK_LOG:-}" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$CLAUDE_HOOK_LOG"
    fi
}

# Read hook input JSON from stdin
INPUT=$(cat)

# Extract hook event type
HOOK_EVENT=$(echo "$INPUT" | jq -r '.hook_event_name // "UserPromptSubmit"')

log "Hook triggered: $HOOK_EVENT"

# Determine what text to process based on hook type
if [ "$HOOK_EVENT" = "UserPromptSubmit" ]; then
    # For user prompts, process the prompt text
    TEXT=$(echo "$INPUT" | jq -r '.prompt // ""')

    if [ -z "$TEXT" ]; then
        log "No prompt to process"
        echo "{}"
        exit 0
    fi

    # Check if there's a traceback in the prompt
    if echo "$TEXT" | grep -q "Traceback (most recent call last)"; then
        log "Traceback detected in user prompt - compacting..."

        # Compact tracebacks in the prompt
        COMPACTED=$(echo "$TEXT" | claude-trace-compactor --stdin --project-root "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || echo "$TEXT")

        # Log statistics
        ORIGINAL_LINES=$(echo "$TEXT" | wc -l)
        COMPACTED_LINES=$(echo "$COMPACTED" | wc -l)
        SAVED_LINES=$((ORIGINAL_LINES - COMPACTED_LINES))
        log "Compacted: $ORIGINAL_LINES lines → $COMPACTED_LINES lines (saved $SAVED_LINES lines)"

        # Return updated prompt
        jq -n --arg prompt "$COMPACTED" '{"updatedPrompt": $prompt}'
    else
        log "No traceback found in prompt - passing through"
        echo "{}"
    fi

elif [ "$HOOK_EVENT" = "PostToolUse" ]; then
    # For tool outputs, process stdout and stderr
    TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')

    # Only process Bash tool outputs
    if [ "$TOOL_NAME" != "Bash" ]; then
        exit 0
    fi

    log "Processing Bash tool output..."

    # Extract stdout and stderr
    STDOUT=$(echo "$INPUT" | jq -r '.tool_response.stdout // ""')
    STDERR=$(echo "$INPUT" | jq -r '.tool_response.stderr // ""')

    # Check for tracebacks
    HAS_TRACEBACK=false
    if echo "$STDOUT" | grep -q "Traceback (most recent call last)"; then
        HAS_TRACEBACK=true
    fi
    if echo "$STDERR" | grep -q "Traceback (most recent call last)"; then
        HAS_TRACEBACK=true
    fi

    if [ "$HAS_TRACEBACK" = "true" ]; then
        log "Traceback detected in tool output - compacting..."

        # Compact tracebacks in both
        COMPACTED_STDOUT=""
        COMPACTED_STDERR=""

        if [ -n "$STDOUT" ]; then
            COMPACTED_STDOUT=$(echo "$STDOUT" | claude-trace-compactor --stdin --project-root "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || echo "$STDOUT")
        fi

        if [ -n "$STDERR" ]; then
            COMPACTED_STDERR=$(echo "$STDERR" | claude-trace-compactor --stdin --project-root "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || echo "$STDERR")
        fi

        # Log statistics
        ORIGINAL_LINES=$(echo "$STDOUT$STDERR" | wc -l)
        COMPACTED_LINES=$(echo "$COMPACTED_STDOUT$COMPACTED_STDERR" | wc -l)
        SAVED_LINES=$((ORIGINAL_LINES - COMPACTED_LINES))
        log "Compacted tool output: $ORIGINAL_LINES lines → $COMPACTED_LINES lines (saved $SAVED_LINES lines)"

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
        log "No traceback in tool output - passing through"
        echo "{}"
    fi
else
    # Unknown hook type, pass through
    log "Unknown hook type: $HOOK_EVENT"
    echo "{}"
    exit 0
fi
