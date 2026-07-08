#!/usr/bin/env python3
"""Markdown structure analysis for SKILL.md files.

Provides deterministic, rule-based parsing of Markdown documents so that
dimension evaluators can move beyond naive substring matching.  The helpers here
are intentionally lightweight and do not require an LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


@dataclass
class Header:
    """A Markdown ATX header."""

    level: int
    title: str
    line_start: int  # 0-based index of the header line
    line_end: int  # one past the last line belonging to this section


@dataclass
class CodeBlock:
    """A fenced code block."""

    language: Optional[str]
    content: str
    line_start: int
    line_end: int


@dataclass
class Table:
    """A Markdown table."""

    rows: List[List[str]]
    line_start: int
    line_end: int


@dataclass
class MarkdownStructure:
    """Structured representation of a SKILL.md document."""

    frontmatter: Dict[str, Any] = field(default_factory=dict)
    has_frontmatter: bool = False
    headers: List[Header] = field(default_factory=list)
    code_blocks: List[CodeBlock] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    raw: str = ""
    lines: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Header helpers
    # ------------------------------------------------------------------ #
    def header_titles(self) -> List[str]:
        return [h.title for h in self.headers]

    def has_header(self, pattern: str) -> bool:
        """Return True if any header title matches ``pattern`` (case-insensitive)."""
        pat = pattern.lower()
        return any(pat in t.lower() for t in self.header_titles())

    def max_header_level(self) -> int:
        if not self.headers:
            return 0
        return max(h.level for h in self.headers)

    def header_hierarchy_ok(self, max_skips: int = 1) -> bool:
        """Check that header levels do not jump too aggressively (e.g. # -> ###)."""
        levels = [h.level for h in self.headers]
        if not levels:
            return True
        skips = 0
        for prev, cur in zip(levels, levels[1:]):
            if cur > prev + 1:
                skips += 1
                if skips > max_skips:
                    return False
        return True

    # ------------------------------------------------------------------ #
    # Section-aware text extraction
    # ------------------------------------------------------------------ #
    def section_text(self, title_pattern: str) -> str:
        """Return text under the first header matching ``title_pattern``."""
        for header in self.headers:
            if title_pattern.lower() in header.title.lower():
                return "\n".join(self.lines[header.line_start : header.line_end])
        return ""

    def section_contains(
        self,
        title_pattern: str | List[str],
        keywords: List[str],
        *,
        match_all: bool = False,
    ) -> bool:
        """Check whether any matching section contains any (or all) keywords."""
        patterns = [title_pattern] if isinstance(title_pattern, str) else title_pattern
        for pattern in patterns:
            text = self.section_text(pattern).lower()
            if not keywords:
                return False
            checks = [k.lower() in text for k in keywords]
            if match_all:
                if all(checks):
                    return True
            elif any(checks):
                return True
        return False

    def any_section_contains(self, keywords: List[str]) -> bool:
        """Check whether any header-led section contains any of the keywords."""
        return any(self.section_contains(h.title, keywords) for h in self.headers)

    # ------------------------------------------------------------------ #
    # Structural element helpers
    # ------------------------------------------------------------------ #
    def has_code_blocks(self) -> bool:
        return bool(self.code_blocks)

    def has_tables(self) -> bool:
        return bool(self.tables)

    def code_languages(self) -> List[str]:
        return [cb.language for cb in self.code_blocks if cb.language]

    def has_frontmatter_key(self, key: str) -> bool:
        return key in self.frontmatter

    # ------------------------------------------------------------------ #
    # Convenience scoring helpers
    # ------------------------------------------------------------------ #
    def document_length_ok(self, min_chars: int = 500) -> bool:
        return len(self.raw.strip()) >= min_chars

    def has_required_sections(self, required: List[str]) -> Tuple[bool, List[str]]:
        missing = [r for r in required if not self.has_header(r)]
        return not missing, missing


def _parse_frontmatter(text: str) -> Tuple[Dict[str, Any], bool]:
    match = re.search(r"(?m)^---\r?\n(.*?)\r?\n---", text, re.DOTALL)
    if not match:
        return {}, False
    try:
        fm = yaml.safe_load(match.group(1)) or {}
        return (fm, True) if isinstance(fm, dict) else ({}, False)
    except yaml.YAMLError:
        return {}, False


def _parse_headers(lines: List[str]) -> List[Header]:
    headers: List[Header] = []
    for i, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if not match:
            continue
        level = len(match.group(1))
        title = match.group(2).strip()
        headers.append(Header(level=level, title=title, line_start=i, line_end=len(lines)))

    # Compute section boundaries: each section ends at the next header of
    # equal or higher precedence (smaller/equal level number).
    for idx, header in enumerate(headers):
        for later in headers[idx + 1 :]:
            if later.level <= header.level:
                header.line_end = later.line_start
                break
    return headers


def _parse_code_blocks(lines: List[str]) -> List[CodeBlock]:
    blocks: List[CodeBlock] = []
    i = 0
    while i < len(lines):
        match = re.match(r"^```\s*(\S*)\s*$", lines[i])
        if not match:
            i += 1
            continue
        language = match.group(1) or None
        start = i
        i += 1
        content_lines: List[str] = []
        while i < len(lines) and not lines[i].startswith("```"):
            content_lines.append(lines[i])
            i += 1
        end = i + 1 if i < len(lines) else len(lines)
        blocks.append(
            CodeBlock(
                language=language,
                content="\n".join(content_lines).strip(),
                line_start=start,
                line_end=end,
            )
        )
        i += 1
    return blocks


def _is_table_row(line: str) -> bool:
    return line.startswith("|") and "|" in line[1:]


def _is_separator_row(line: str) -> bool:
    parts = [p.strip() for p in line.split("|")]
    return all(p == "" or set(p) <= {"-", ":", " "} for p in parts)


def _parse_table_row(line: str) -> List[str]:
    return [cell.strip() for cell in line.split("|")[1:-1]]


def _parse_tables(lines: List[str]) -> List[Table]:
    tables: List[Table] = []
    i = 0
    while i < len(lines):
        if not _is_table_row(lines[i]):
            i += 1
            continue
        start = i
        rows = [_parse_table_row(lines[i])]
        i += 1
        # Optional separator row
        if i < len(lines) and _is_table_row(lines[i]) and _is_separator_row(lines[i]):
            i += 1
        # Body rows
        while i < len(lines) and _is_table_row(lines[i]):
            rows.append(_parse_table_row(lines[i]))
            i += 1
        tables.append(Table(rows=rows, line_start=start, line_end=i))
    return tables


def parse_markdown_structure(text: str) -> MarkdownStructure:
    """Parse raw Markdown text into a structured representation."""
    lines = text.splitlines()
    frontmatter, has_frontmatter = _parse_frontmatter(text)
    return MarkdownStructure(
        frontmatter=frontmatter,
        has_frontmatter=has_frontmatter,
        headers=_parse_headers(lines),
        code_blocks=_parse_code_blocks(lines),
        tables=_parse_tables(lines),
        raw=text,
        lines=lines,
    )


def parse_skill_markdown(skill_path: Path) -> MarkdownStructure:
    """Parse ``SKILL.md`` inside a skill directory."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return MarkdownStructure(raw="", lines=[])
    return parse_markdown_structure(skill_md.read_text(encoding="utf-8", errors="replace"))
