from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
import re

from .manifest import iter_files, read_text_document


BSL_SUFFIXES = {".bsl", ".os"}
UNIX_HOME_PATTERN = re.compile(
    r"(?i)(?<![\w/])/" + r"home/(?!user(?:/|$)|example(?:/|$))[^/\s]+"
)
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?:password|passwd|pwd|token|secret|api[_-]?key|access[_-]?key|пароль)\b[\"']?"
    r"\s*[:=]\s*(?P<value>[\"'][^\"'\r\n]+[\"']|[A-Z0-9_./+=:-]+)\s*(?:[,;#]|$)"
)
PLACEHOLDER_PREFIXES = ("demo", "example", "sample", "test", "mock", "placeholder", "changeme", "redacted")
SECRET_PATTERNS = {
    "credential in URL": re.compile(r"https?://[^\s/:]+:[^\s/@]+@", re.IGNORECASE),
    "email address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Z0-9]{20,}|github_pat_[A-Z0-9_]{20,})\b", re.IGNORECASE),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "Windows user path": re.compile(r"(?i)\b[A-Z]:\\Users\\(?!Public(?:\\|$)|Default(?:\\|$))[^\\/\s]+"),
    "Unix user path": UNIX_HOME_PATTERN,
}


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int | None
    message: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def check_source_tree(root: Path, max_line_length: int = 120) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files(root):
        if path.suffix.casefold() not in BSL_SUFFIXES:
            continue
        document = read_text_document(path)
        if document is None:
            continue
        relative_path = path.relative_to(root).as_posix()
        for number, line in enumerate(document.text.splitlines(), start=1):
            if len(line) > max_line_length:
                findings.append(
                    Finding("line-length", relative_path, number, f"{len(line)} > {max_line_length}")
                )
            if line.rstrip(" \t") != line:
                findings.append(Finding("trailing-whitespace", relative_path, number, "trailing whitespace"))
            if "\t" in line:
                findings.append(Finding("tab-character", relative_path, number, "tab character"))
            if "\\t" in line or "\\n" in line:
                findings.append(
                    Finding("literal-escape", relative_path, number, "literal \\t or \\n sequence")
                )
    return findings


def load_denylist(path: Path | None) -> list[str]:
    if path is None:
        return []
    terms = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        value = raw_line.strip()
        if value and not value.startswith("#"):
            terms.append(value.casefold())
    return terms


def release_scan(
    root: Path,
    denied_terms: Iterable[str],
    excluded_paths: Iterable[Path] = (),
) -> list[Finding]:
    findings: list[Finding] = []
    normalized_terms = [term.casefold() for term in denied_terms]
    excluded = {path.resolve() for path in excluded_paths}
    for path in iter_files(root):
        if path.resolve() in excluded:
            continue
        document = read_text_document(path)
        if document is None:
            continue
        relative_path = path.relative_to(root).as_posix()
        for number, line in enumerate(document.text.splitlines(), start=1):
            folded_line = line.casefold()
            for term in normalized_terms:
                if term in folded_line:
                    findings.append(Finding("denylist", relative_path, number, f"forbidden term: {term}"))
            for rule, pattern in SECRET_PATTERNS.items():
                if pattern.search(line):
                    findings.append(Finding("secret-pattern", relative_path, number, rule))
            assignment = SECRET_ASSIGNMENT_PATTERN.search(line)
            if assignment and not is_placeholder_value(assignment.group("value")):
                findings.append(Finding("secret-pattern", relative_path, number, "secret assignment"))
    return findings


def is_placeholder_value(value: str) -> bool:
    normalized = value.strip("\"'").casefold()
    return normalized.startswith(PLACEHOLDER_PREFIXES)
