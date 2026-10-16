from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable
import json


IGNORED_DIRECTORY_NAMES = {
    ".git",
    ".idea",
    ".pytest_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "outputs",
}


@dataclass(frozen=True)
class TextDocument:
    text: str
    encoding: str
    newline: str


@dataclass(frozen=True)
class FileRecord:
    path: str
    sha256: str
    size: int
    kind: str
    encoding: str | None
    newline: str | None


def iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRECTORY_NAMES for part in path.relative_to(root).parts):
            continue
        yield path


def detect_newline(data: bytes) -> str:
    crlf_count = data.count(b"\r\n")
    lf_count = data.count(b"\n") - crlf_count
    if crlf_count and lf_count:
        return "mixed"
    if crlf_count:
        return "crlf"
    if lf_count:
        return "lf"
    return "none"


def read_text_document(path: Path) -> TextDocument | None:
    data = path.read_bytes()
    if b"\x00" in data:
        return None

    candidates = []
    if data.startswith(b"\xef\xbb\xbf"):
        candidates.append("utf-8-sig")
    candidates.extend(["utf-8", "cp1251"])

    for encoding in candidates:
        try:
            return TextDocument(data.decode(encoding), encoding, detect_newline(data))
        except UnicodeDecodeError:
            continue
    return None


def write_text_document(path: Path, document: TextDocument, text: str) -> None:
    newline = "\r\n" if document.newline == "crlf" else "\n"
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(normalized.replace("\n", newline).encode(document.encoding))


def file_record(root: Path, path: Path) -> FileRecord:
    data = path.read_bytes()
    document = read_text_document(path)
    relative_path = path.relative_to(root).as_posix()
    return FileRecord(
        path=relative_path,
        sha256=sha256(data).hexdigest(),
        size=len(data),
        kind="text" if document else "binary",
        encoding=document.encoding if document else None,
        newline=document.newline if document else None,
    )


def build_manifest(root: Path) -> dict[str, Any]:
    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        raise ValueError(f"Directory does not exist: {resolved_root}")
    return {
        "schemaVersion": 1,
        "root": ".",
        "files": [asdict(file_record(resolved_root, path)) for path in iter_files(resolved_root)],
    }


def save_manifest(manifest: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compare_manifests(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[str]]:
    before_files = {item["path"]: item for item in before["files"]}
    after_files = {item["path"]: item for item in after["files"]}
    before_paths = set(before_files)
    after_paths = set(after_files)
    common_paths = before_paths & after_paths

    modified = sorted(
        path for path in common_paths if before_files[path]["sha256"] != after_files[path]["sha256"]
    )
    return {
        "added": sorted(after_paths - before_paths),
        "deleted": sorted(before_paths - after_paths),
        "modified": modified,
    }
