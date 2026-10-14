"""ToolTranslator — translate external tool names to OpenJarvis equivalents.

External skill libraries (Hermes Agent, OpenClaw) reference tools by Claude
Code's standard tool names (Bash, Read, Write, etc.).  OpenJarvis uses
different names (shell_exec, file_read, file_write).  This module translates
those references in skill markdown bodies and ``allowed-tools`` fields.

The translation table is small (~10 entries) covering Claude Code's standard
tools and grows as we encounter new vendor tools.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Translation table — external name → OpenJarvis name
# ---------------------------------------------------------------------------

TOOL_TRANSLATION: Dict[str, str] = {
    "Bash": "shell_exec",
    "Read": "file_read",
    "Write": "file_write",
    "Edit": "file_edit",
    "Glob": "file_glob",
    "Grep": "file_grep",
    "WebSearch": "web_search",
    "Task": "delegate_agent",
    "NotebookEdit": "notebook_edit",
}

ADAPTED_TOOLS = {"terminal": "shell_exec", "read_file": "file_read"}
KNOWN_INTERNAL_TOOLS = set(TOOL_TRANSLATION.values()) | {
    "memory_search",
    "retrieval",
    "web_search",
    "think",
    "calculator",
    "git_status",
    "git_diff",
    "machine_inventory",
    "drive_inventory",
    "project_registry",
    "apply_patch",
}


def declared_tools(value):
    """Normalize string/list declarations while retaining scoped arguments."""
    values = value if isinstance(value, list) else [value]
    return [
        token
        for item in values
        if isinstance(item, str)
        for token in re.findall(r"[^\s,()]+(?:\([^)]*\))?", item)
    ]


class ToolTranslator:
    """Rewrite tool references in markdown bodies and allowed-tools fields.

    Uses a word-boundary regex so partial matches like 'Reader' or
    'Reading' are not rewritten.
    """

    def __init__(
        self,
        translation_table: Dict[str, str] | None = None,
    ) -> None:
        self._table = dict(translation_table or TOOL_TRANSLATION)
        # Word-boundary pattern matching any external name
        names = sorted(self._table.keys(), key=len, reverse=True)
        if names:
            self._pattern = re.compile(
                r"\b(" + "|".join(re.escape(n) for n in names) + r")\b"
            )
        else:
            self._pattern = None

    def translate_markdown(self, body: str) -> Tuple[str, List[str]]:
        """Translate tool references in a markdown body.

        Returns
        -------
        tuple[str, list[str]]
            (rewritten body, list of untranslated tool names found)
        """
        if not body or self._pattern is None:
            return body, []

        def _sub(match: re.Match) -> str:
            return self._table.get(match.group(1), match.group(1))

        new_body = self._pattern.sub(_sub, body)

        # Find untranslated tool-like references (CamelCase words that look
        # like tool names but aren't in the table).  Conservative heuristic:
        # words with internal uppercase (true CamelCase) followed by ' tool'
        # or a word boundary, length 3-30, not in the translation table.
        untranslated: List[str] = []
        # Require at least one uppercase letter after position 0 (true CamelCase)
        candidate_pattern = re.compile(r"\b([A-Z][a-z]+[A-Z][a-zA-Z]*)(?:\s+tool|\b)")
        candidates = candidate_pattern.findall(body) + re.findall(
            r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b", body
        )
        for cand in candidates:
            if cand not in self._table and cand not in untranslated:
                if 3 <= len(cand) <= 60 and cand not in KNOWN_INTERNAL_TOOLS:
                    untranslated.append(cand)
        return new_body, untranslated

    def translate_allowed_tools(self, allowed: str) -> Tuple[str, List[str]]:
        """Translate the space-delimited allowed-tools field.

        Tokens may have parenthesized arguments like ``Bash(git:*)``.  Only
        the prefix before the first ``(`` is translated.
        """
        if not allowed:
            return allowed, []

        out_tokens: List[str] = []
        untranslated: List[str] = []
        for token in declared_tools(allowed):
            # Split off any (args) suffix
            if "(" in token:
                head, _, tail = token.partition("(")
                tail = "(" + tail
            else:
                head, tail = token, ""

            if head in self._table:
                out_tokens.append(self._table[head] + tail)
            else:
                out_tokens.append(token)
                if head not in untranslated:
                    untranslated.append(head)

        return " ".join(out_tokens), untranslated


__all__ = ["TOOL_TRANSLATION", "ToolTranslator"]
