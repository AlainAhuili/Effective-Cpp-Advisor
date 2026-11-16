"""Loads the curated knowledge base: one SKILL.md per Effective C++ principle.

Each file has a small YAML-like front matter (skill_id, title, source,
related) and markdown sections (`## Rule`, `## Why it matters`, ...).
Parsing is deliberately simple and dependency-free; the format is ours.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills" / "effective_cpp"


@dataclass(frozen=True)
class Skill:
    skill_id: str
    title: str
    source: str
    related: tuple[str, ...]
    sections: dict[str, str] = field(hash=False)
    path: Path = field(hash=False)

    @property
    def text(self) -> str:
        """The whole entry as markdown."""
        return self.text_for(tuple(self.sections))

    def text_for(self, section_names: tuple[str, ...]) -> str:
        """Only the named sections (in file order), e.g. without example code."""
        parts = [f"# {self.title}", f"Source: {self.source}"]
        parts += [
            f"## {name}\n{body}" for name, body in self.sections.items() if name in section_names
        ]
        return "\n\n".join(parts)


class KnowledgeBaseError(ValueError):
    pass


def load_skills(skills_dir: Path = DEFAULT_SKILLS_DIR) -> dict[str, Skill]:
    """All skills by skill_id. Folders starting with `_` (the template) are skipped."""
    skills: dict[str, Skill] = {}
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        if path.parent.name.startswith("_"):
            continue
        skill = parse_skill(path.read_text(encoding="utf-8"), path)
        if skill.skill_id in skills:
            raise KnowledgeBaseError(f"duplicate skill_id {skill.skill_id} in {path}")
        skills[skill.skill_id] = skill
    return skills


def parse_skill(markdown: str, path: Path = Path("<memory>")) -> Skill:
    match = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", markdown, re.DOTALL)
    if not match:
        raise KnowledgeBaseError(f"{path}: missing front matter between --- lines")
    meta = _parse_front_matter(match.group(1), path)
    for key in ("skill_id", "title", "source"):
        if not meta.get(key):
            raise KnowledgeBaseError(f"{path}: front matter needs '{key}'")
    return Skill(
        skill_id=meta["skill_id"],
        title=meta["title"],
        source=meta["source"],
        related=tuple(_parse_list(meta.get("related", "[]"))),
        sections=_parse_sections(match.group(2)),
        path=path,
    )


def _parse_front_matter(block: str, path: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in block.splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise KnowledgeBaseError(f"{path}: bad front matter line {line!r}")
        meta[key.strip()] = value.strip()
    return meta


def _parse_list(value: str) -> list[str]:
    inner = value.strip().removeprefix("[").removesuffix("]")
    return [item.strip() for item in inner.split(",") if item.strip()]


def _parse_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    lines: list[str] = []
    in_code = False
    for line in body.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        if not in_code and line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(lines).strip()
            current, lines = line[3:].strip(), []
        elif current is not None:
            lines.append(line)
    if current is not None:
        sections[current] = "\n".join(lines).strip()
    return sections
