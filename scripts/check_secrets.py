"""Fail CI on credential patterns in tracked text. Never print matching content."""
import argparse
from pathlib import Path
import re
import subprocess

PATTERNS = {
    "Google API key": re.compile(rb"AIza[0-9A-Za-z_-]{35}"),
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    "Google OAuth token": re.compile(rb"ya29\.[A-Za-z0-9_-]{30,}"),
    "AWS access key": re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    "Slack token": re.compile(rb"xox[baprs]-[0-9A-Za-z-]{25,}"),
}


def scan_tracked(root):
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    findings = []
    for name in filter(None, names):
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_048_576:
            continue
        content = path.read_bytes()
        findings.extend((name, rule) for rule, pattern in PATTERNS.items() if pattern.search(content))
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    findings = scan_tracked(args.root.resolve())
    for path, rule in findings:
        print(f"Credential pattern detected: {path} ({rule}); content omitted")
    print(f"Tracked-file secret check: {len(findings)} matching locations")
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
