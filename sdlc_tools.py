"""
Real implementations of the tools Claude Code provides natively (Read, Write,
Edit, Bash, Grep, Glob). Each is exposed as an OpenAI-style function-calling
tool. An agent's frontmatter `tools:` list (Claude Code names) is mapped to
the subset it's allowed to call.

Kept deliberately simple and dependency-light — this is a simulation
harness, not a hardened sandbox. Don't point it at anything you don't trust
the model with; PROJECT_ROOT below is your only real safety boundary and
even that is a soft one (Bash can escape it).
"""
from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path

# All file tool paths are resolved relative to this. Set via run_sdlc.py.
PROJECT_ROOT = Path(".").resolve()


def _resolve(path: str) -> Path:
    p = (PROJECT_ROOT / path).resolve()
    if PROJECT_ROOT not in p.parents and p != PROJECT_ROOT:
        raise PermissionError(f"Path '{path}' escapes project root {PROJECT_ROOT}")
    return p


def read_file(path: str) -> str:
    p = _resolve(path)
    if not p.exists():
        return f"ERROR: {path} does not exist"
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"ERROR: {path} is not a text file"


def write_file(path: str, content: str) -> str:
    p = _resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} chars to {path}"


def edit_file(path: str, old_str: str, new_str: str) -> str:
    p = _resolve(path)
    if not p.exists():
        return f"ERROR: {path} does not exist"
    text = p.read_text(encoding="utf-8")
    count = text.count(old_str)
    if count == 0:
        return f"ERROR: old_str not found in {path}"
    if count > 1:
        return (
            f"ERROR: old_str appears {count} times in {path} — "
            "must be unique. Include more surrounding context."
        )
    p.write_text(text.replace(old_str, new_str, 1), encoding="utf-8")
    return f"Edited {path}"


def run_bash(command: str, timeout: int = 120) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        out = result.stdout[-6000:]
        err = result.stderr[-3000:]
        return f"exit_code={result.returncode}\nstdout:\n{out}\nstderr:\n{err}"
    except subprocess.TimeoutExpired:
        return f"ERROR: command timed out after {timeout}s"


def grep_files(pattern: str, glob: str = "**/*") -> str:
    matches = []
    for p in PROJECT_ROOT.glob(glob):
        if not p.is_file():
            continue
        try:
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if pattern in line:
                    matches.append(f"{p.relative_to(PROJECT_ROOT)}:{i}: {line.strip()}")
        except (UnicodeDecodeError, PermissionError):
            continue
        if len(matches) >= 200:
            break
    return "\n".join(matches) if matches else "no matches"


def glob_files(pattern: str) -> str:
    matches = [
        str(p.relative_to(PROJECT_ROOT))
        for p in PROJECT_ROOT.glob(pattern)
        if p.is_file()
    ]
    return "\n".join(sorted(matches)) if matches else "no matches"


# --- OpenAI-style tool schemas, keyed by our internal tool name ------------

_SCHEMAS = {
    "read_file": {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file's contents given a path relative to the project root.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    "write_file": {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with the given content. Creates parent directories as needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    "edit_file": {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace an exact, unique substring in a file with a new string. old_str must match exactly once.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_str": {"type": "string"},
                    "new_str": {"type": "string"},
                },
                "required": ["path", "old_str", "new_str"],
            },
        },
    },
    "run_bash": {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": "Run a shell command in the project root and return exit code, stdout, stderr.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    "grep_files": {
        "type": "function",
        "function": {
            "name": "grep_files",
            "description": "Search for a literal substring across files matching a glob pattern (default all files).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "glob": {"type": "string", "description": "e.g. '**/*.py'"},
                },
                "required": ["pattern"],
            },
        },
    },
    "glob_files": {
        "type": "function",
        "function": {
            "name": "glob_files",
            "description": "List files matching a glob pattern, e.g. 'backend/**/*.py'.",
            "parameters": {
                "type": "object",
                "properties": {"pattern": {"type": "string"}},
                "required": ["pattern"],
            },
        },
    },
}

_IMPLS = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "run_bash": run_bash,
    "grep_files": grep_files,
    "glob_files": glob_files,
}

# Claude Code frontmatter tool name -> our internal tool name(s)
_CLAUDE_TOOL_MAP = {
    "Read": ["read_file"],
    "Write": ["write_file"],
    "Edit": ["edit_file"],
    "Bash": ["run_bash"],
    "Grep": ["grep_files"],
    "Glob": ["glob_files"],
    # Agent/Task tool is meaningless here — the Python driver does the
    # spawning directly instead of the model calling a tool for it.
}


def resolve_tools(claude_tool_names: list[str]) -> tuple[list[dict], dict]:
    """Given a subagent's frontmatter `tools:` list, return the OpenAI tool
    schemas and callable implementations it's allowed to use."""
    internal_names: list[str] = []
    for name in claude_tool_names:
        internal_names.extend(_CLAUDE_TOOL_MAP.get(name, []))
    schemas = [_SCHEMAS[n] for n in internal_names if n in _SCHEMAS]
    impls = {n: _IMPLS[n] for n in internal_names if n in _IMPLS}
    return schemas, impls
