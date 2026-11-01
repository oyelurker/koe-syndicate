"""Scan local Git history without printing secret values or matching lines."""
import json
from pathlib import Path
import re
import subprocess
from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]


def git(*args, data=None):
    return subprocess.check_output(["git", *args], cwd=root, input=data)


patterns = [
    re.compile(rb"AIza[0-9A-Za-z_-]{35}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    re.compile(rb"ya29\.[A-Za-z0-9_-]{30,}"),
]
local_secrets = []
for name, value in dotenv_values(root / ".env").items():
    if value and len(value) >= 24 and re.search(r"KEY|SECRET|TOKEN|PASSWORD", name):
        if not value.lower().startswith(("your_", "replace", "change", "example")):
            local_secrets.append(value.encode())
    if name == "SERVICE_AUTH_KEYS" and value:
        local_secrets.extend(v.encode() for v in json.loads(value).values() if len(v) >= 24)
objects = git("rev-list", "--objects", "--all")
metadata = git("cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize) %(rest)", data=objects)
blobs, skipped = [], []
for line in metadata.decode().splitlines():
    sha, kind, size, *name = line.split(" ", 3)
    if kind == "blob":
        if int(size) <= 1_048_576:
            blobs.append((sha, name[0] if name else "unknown"))
        else:
            skipped.append({"blob": sha, "path": name[0] if name else "unknown", "bytes": int(size)})
payload = git("cat-file", "--batch", data="".join(sha + "\n" for sha, _ in blobs).encode())
offset, findings = 0, []
for sha, path in blobs:
    end = payload.index(b"\n", offset)
    size = int(payload[offset:end].split()[2])
    content = payload[end + 1:end + 1 + size]
    offset = end + size + 2
    if any(p.search(content) for p in patterns) or any(v in content for v in local_secrets):
        findings.append({"blob": sha, "path": path})
report = {"commits_scanned": len(git("rev-list", "--all").splitlines()),
          "blobs_scanned": len(blobs), "oversized_blobs_skipped": skipped,
          "scope": "all local refs; Google/GitHub/OAuth/private-key patterns and configured local secret values; no values emitted",
          "matches": findings}
(root / "docs/p0-history-scan.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print("Scanned", len(blobs), "history blobs; matching locations:", len(findings), "; oversized skipped:", len(skipped))
raise SystemExit(bool(findings))
