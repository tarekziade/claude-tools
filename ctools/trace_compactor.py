"""
claude_trace_compactor
----------------------

A small, dependency-free Python module that detects Python tracebacks inside
arbitrary text and replaces them with compact summaries suitable for sending to
Claude (or other LLMs) as an in-flight prompt hook.

Key features
- Detect traceback blocks (robust regex)
- Parse frames and exception lines from pasted tracebacks
- Compact aggressively (no file I/O by default, no locals) to reduce token size
- Deterministic fingerprinting for deduplication
- JSON output option for structured agent payloads
- Small CLI for local testing

Usage (in your code / hook):

    from claude_trace_compactor import rewrite_prompt_for_claude

    new_prompt = rewrite_prompt_for_claude(original_prompt, project_root="/home/me/myproj")

CLI example:

    python -m claude_trace_compactor --stdin --project-root /home/me/myproj

"""

from __future__ import annotations

import re
import os
import sys
import json
import hashlib
import argparse
from typing import Optional, List, Dict, Any, Tuple

__all__ = [
    "rewrite_prompt_for_claude",
    "compact_traceback_block",
    "parse_traceback_text",
]

# ---------------------------------------------------------------------------
# Regexes / constants
# ---------------------------------------------------------------------------
TRACEBACK_BLOCK_RE = re.compile(
    r"("  # capture the whole block
    r"Traceback\s*\(most\s+recent\s+call\s+last\):"  # header
    r"(?:\r?\n)"
    r"(?:[ \t]+File\s+\".*?\",\s+line\s+\d+,\s+in\s+.*(?:\r?\n)"
    r"(?:[ \t]+.*(?:\r?\n))?"  # optional code line after each frame
    r")+"
    r'[^"]+?(?:Error|Exception|Warning|RuntimeError|AssertionError|TypeError|ValueError)[:]?.*?'
    r")",
    re.VERBOSE | re.MULTILINE,
)

FRAME_RE = re.compile(r'File "(.+?)", line (\d+), in (.+)')
CODE_RE = re.compile(r'^\s+(.*\S.*)$')
EXC_LINE_RE = re.compile(r'([\w\.]+(?:Error|Exception|Warning|RuntimeError|AssertionError|TypeError|ValueError)):\s*(.*)')

# compact block wrapper template
COMPACT_OPEN = "<COMPACT_PY_TRACEBACK fingerprint={fp}>"
COMPACT_CLOSE = "</COMPACT_PY_TRACEBACK>"

# ---------------------------------------------------------------------------
# Parsing logic
# ---------------------------------------------------------------------------

def parse_traceback_text(text: str) -> Dict[str, Any]:
    """Parse a pasted traceback text into frames and exception lines.

    Returns a dict with keys:
      - frames: list of {filename, lineno, name, code_line, raw_index}
      - exception_lines: list of exception strings found (in order of appearance)
      - raw_lines: the original split lines

    The parser is conservative and skips malformed lines.
    """
    lines = text.splitlines()
    frames: List[Dict[str, Any]] = []
    exception_lines: List[str] = []

    i = 0
    while i < len(lines):
        ln = lines[i]
        m = FRAME_RE.search(ln)
        if m:
            filename, lineno_s, func = m.groups()
            try:
                lineno = int(lineno_s)
            except Exception:
                lineno = -1

            code_line = ""
            if i + 1 < len(lines):
                mcode = CODE_RE.match(lines[i + 1])
                if mcode:
                    code_line = mcode.group(1).strip()

            frames.append({
                "filename": filename,
                "lineno": lineno,
                "name": func.strip(),
                "code_line": code_line,
                "raw_index": i,
            })
            i += 1
            continue

        m2 = EXC_LINE_RE.search(ln.strip())
        if m2:
            # collect continuations that are indented or blank
            collected = ln.strip()
            j = i + 1
            while j < len(lines) and (lines[j].startswith("    ") or lines[j].strip() == ""):
                collected += " " + lines[j].strip()
                j += 1
            exception_lines.append(collected)
            i = j
            continue

        i += 1

    return {"frames": frames, "exception_lines": exception_lines, "raw_lines": lines}


# ---------------------------------------------------------------------------
# Compaction logic
# ---------------------------------------------------------------------------

def _is_stdlib_path(path: str) -> bool:
    """Lightweight heuristic to detect stdlib/site-packages paths.

    It's intentionally conservative and only used as a heuristic for scoring.
    """
    if not path:
        return False
    try:
        p = os.path.abspath(path)
    except Exception:
        return False

    if sys_prefix := getattr(os, "sys", None):
        # defensive: avoid importing sys at module scope for some embed scenarios
        pass

    if "site-packages" in p or "/lib/python" in p or p.endswith(".egg"):
        return True
    # also mark virtualenvs under .venv
    if ".venv" in p or "venv" in p:
        return True
    return False


def _frame_score(f: Dict[str, Any], project_root: Optional[str] = None) -> int:
    """Score frames to choose the most relevant ones for compacting.

    Higher score means more relevant.
    """
    fname = f.get("filename") or ""
    score = 0
    try:
        if project_root and fname and os.path.abspath(fname).startswith(os.path.abspath(project_root)):
            score += 100
    except Exception:
        pass

    if not _is_stdlib_path(fname):
        score += 10

    # favor later frames (closer to error) - higher raw_index = more recent in traceback
    score += int(f.get("raw_index", 0))
    return score


def compact_traceback_block(block: str, *, max_frames: int = 4, project_root: Optional[str] = None) -> str:
    """Compact a single traceback block (string) into a short tagged summary.

    This function intentionally avoids filesystem access and locals capture so it is
    suitable to run in a fast in-flight hook.
    """
    parsed = parse_traceback_text(block)
    frames = parsed["frames"]
    exception_lines = parsed["exception_lines"]

    if not frames:
        # Not a recognized traceback; return original block
        return block

    # pick candidate frames by score
    scored = sorted(frames, key=lambda f: _frame_score(f, project_root=project_root), reverse=True)
    chosen: List[Dict[str, Any]] = []
    chosen_keys = set()
    for f in scored:
        key = (f.get("filename"), f.get("lineno"), f.get("name"))
        if key in chosen_keys:
            continue
        chosen.append(f)
        chosen_keys.add(key)
        if len(chosen) >= max_frames:
            break

    # preserve original ordering (earliest->latest)
    chosen_set = set(id(f) for f in chosen)
    ordered = [f for f in frames if id(f) in chosen_set]

    # build fingerprint (short)
    fp_src = json.dumps([{"f": (f.get("filename"), f.get("lineno"), f.get("name"))} for f in ordered], sort_keys=True)
    fingerprint = hashlib.sha1(fp_src.encode("utf-8")).hexdigest()[:10]

    # build compact text
    primary_exc = exception_lines[-1] if exception_lines else "<unknown exception>"

    lines = [COMPACT_OPEN.format(fp=fingerprint), f"Exception: {primary_exc}", "", "Relevant frames:"]
    for f in ordered:
        fn = f.get("filename") or "<unknown>"
        base = fn.rsplit("/", 1)[-1]
        ln = f.get("lineno")
        name = f.get("name") or "<unknown>"
        code = f.get("code_line") or ""
        if code:
            lines.append(f"- {base}:{ln} in {name} → {code}")
        else:
            lines.append(f"- {base}:{ln} in {name}")

    lines.append(COMPACT_CLOSE)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt rewrite hook
# ---------------------------------------------------------------------------

def rewrite_prompt_for_claude(prompt: str, *, max_frames: int = 4, project_root: Optional[str] = None) -> str:
    """Detect traceback blocks in `prompt` and replace them with compact summaries.

    Safe to call on arbitrary text. Deterministic and idempotent: already-compact blocks
    (those starting with <COMPACT_PY_TRACEBACK) are left untouched.
    """
    # do not re-process already compacted blocks
    if "<COMPACT_PY_TRACEBACK" in prompt:
        return prompt

    def _repl(m: re.Match) -> str:
        block = m.group(1)
        try:
            return compact_traceback_block(block, max_frames=max_frames, project_root=project_root)
        except Exception:
            # on failure, return original block to avoid data loss
            return block

    return TRACEBACK_BLOCK_RE.sub(_repl, prompt)


# ---------------------------------------------------------------------------
# CLI for testing
# ---------------------------------------------------------------------------

def _cli_main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="claude_trace_compactor")
    parser.add_argument("--stdin", action="store_true", help="read prompt from stdin")
    parser.add_argument("--file", type=str, help="read prompt from file")
    parser.add_argument("--project-root", type=str, default=None, help="path to bias towards user code")
    parser.add_argument("--max-frames", type=int, default=4)
    parser.add_argument("--json", action="store_true", help="output JSON with structured fields")

    ns = parser.parse_args(argv)

    if ns.stdin:
        text = sys.stdin.read()
    elif ns.file:
        with open(ns.file, "r", encoding="utf-8") as fh:
            text = fh.read()
    else:
        parser.error("either --stdin or --file is required")

    compacted = rewrite_prompt_for_claude(text, max_frames=ns.max_frames, project_root=ns.project_root)

    if ns.json:
        # return a small structured payload: replace compact blocks with JSON entries
        parsed = parse_traceback_text(compacted)
        out = {
            "original_preview": text[:400],
            "compacted_preview": compacted[:400],
            "frames_found": len(parsed.get("frames", [])),
        }
        print(json.dumps(out, indent=2))
    else:
        print(compacted)

    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_main())
