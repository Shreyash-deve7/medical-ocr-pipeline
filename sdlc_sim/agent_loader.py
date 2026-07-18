"""
Parses Claude-Code-style subagent files (.claude/agents/*.md) into plain
Python config objects, so we can reuse the exact same agent definitions
without Claude Code itself.

A subagent file looks like:

    ---
    name: coder
    description: ...
    tools: Read, Write, Edit, Bash, Grep, Glob
    model: sonnet
    ---

    <system prompt in markdown>

We only care about `name`, `tools`, and the body (system prompt). `model`
and `description` are read too but `model` gets overridden by whatever NIM
model you configure per-role, since Claude model aliases (sonnet/opus/haiku)
mean nothing on NIM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class AgentConfig:
    name: str
    description: str
    tools: list[str]
    system_prompt: str
    raw_frontmatter: dict = field(default_factory=dict)


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _split_tools(tools_field: str) -> list[str]:
    """Splits a comma-separated `tools:` string on top-level commas only,
    so 'Read, Agent(coder, reviewer), Bash' -> ['Read', 'Agent(coder, reviewer)', 'Bash']
    instead of breaking apart the parenthesized allowlist."""
    tools: list[str] = []
    depth = 0
    current = ""
    for ch in tools_field:
        if ch == "(":
            depth += 1
            current += ch
        elif ch == ")":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            if current.strip():
                tools.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        tools.append(current.strip())
    return tools


def load_agent(path: str | Path) -> AgentConfig:
    path = Path(path)
    text = path.read_text(encoding="utf-8")

    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(
            f"{path} doesn't look like a subagent file "
            "(expected '---' frontmatter block at the top)"
        )

    frontmatter_raw, body = m.group(1), m.group(2)
    frontmatter = yaml.safe_load(frontmatter_raw) or {}

    tools_field = frontmatter.get("tools", "")
    if isinstance(tools_field, str):
        tools = _split_tools(tools_field)
    elif isinstance(tools_field, list):
        tools = [str(t).strip() for t in tools_field]
    else:
        tools = []

    return AgentConfig(
        name=frontmatter.get("name", path.stem),
        description=frontmatter.get("description", ""),
        tools=tools,
        system_prompt=body.strip(),
        raw_frontmatter=frontmatter,
    )


def load_agents_dir(agents_dir: str | Path) -> dict[str, AgentConfig]:
    agents_dir = Path(agents_dir)
    agents = {}
    for md_file in sorted(agents_dir.glob("*.md")):
        cfg = load_agent(md_file)
        agents[cfg.name] = cfg
    return agents
