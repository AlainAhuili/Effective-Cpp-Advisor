"""Versioned prompt templates stored as markdown, rendered with string.Template.

A prompt file has front matter (id, version) and two parts: `# system` and
`# user`. Placeholders use `$name`; a missing value is an error, so a renamed
placeholder can't silently produce an empty prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class PromptTemplate:
    id: str
    version: int
    system: str
    user: str

    def render(self, **values: str) -> tuple[str, str]:
        return Template(self.system).substitute(values), Template(self.user).substitute(values)


def load_prompt(name: str, prompts_dir: Path = PROMPTS_DIR) -> PromptTemplate:
    text = (prompts_dir / f"{name}.prompt.md").read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", text, re.DOTALL)
    if not match:
        raise ValueError(f"{name}: missing front matter")
    meta = dict(line.split(":", 1) for line in match.group(1).splitlines() if ":" in line)
    parts = re.split(r"^# (system|user)\s*$", match.group(2), flags=re.MULTILINE)
    sections = dict(zip(parts[1::2], (p.strip() for p in parts[2::2]), strict=True))
    return PromptTemplate(
        id=meta["id"].strip(),
        version=int(meta["version"]),
        system=sections["system"],
        user=sections["user"],
    )
