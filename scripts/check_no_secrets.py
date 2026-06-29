from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


BLOCKED_PATHS = (
    ".env",
    "config.yaml",
    "user_data/",
    "output/",
    "data/chroma/",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".docx",
)

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_-]{30,}\b"),
    re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token|cookie)\b\s*[:=]\s*['\"]?(?!your|test|fake|key|\$\{)[A-Za-z0-9_./+=-]{24,}"),
)


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]


def blocked_tracked_path(path: Path) -> str:
    normalized = path.as_posix()
    for marker in BLOCKED_PATHS:
        if marker.endswith("/"):
            if normalized == marker.rstrip("/") or normalized.startswith(marker):
                return marker
        elif normalized == marker or normalized.endswith(marker):
            return marker
    return ""


def scan_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    findings = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(f"{path}:{lineno}: possible secret-like value")
                break
    return findings


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        marker = blocked_tracked_path(path)
        if marker:
            findings.append(f"{path}: tracked local secret/runtime path matches {marker}")
            continue
        findings.extend(scan_file(path))
    if findings:
        print("Sensitive data scan failed:", file=sys.stderr)
        for item in findings:
            print(f"- {item}", file=sys.stderr)
        return 1
    print("Sensitive data scan passed: no tracked secrets or local runtime artifacts found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
