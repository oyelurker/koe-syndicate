"""Check that each runtime lock contains its complete installed dependency closure."""
from importlib.metadata import distribution
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

root = Path(__file__).resolve().parents[1]
for service in ("ui_client", "lead_finder", "lead_manager", "sdr", "gmail_pubsub_listener"):
    locked = {}
    for line in (root / service / "requirements.txt").read_text().splitlines():
        line = line.split(" #", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        requirement = Requirement(line)
        if requirement.marker is None or requirement.marker.evaluate():
            locked[canonicalize_name(requirement.name)] = requirement
    for name, requirement in locked.items():
        installed = distribution(name)
        assert installed.version in requirement.specifier, (service, name, installed.version)
        for raw in installed.requires or []:
            dependency = Requirement(raw)
            if dependency.marker is None or dependency.marker.evaluate({"extra": ""}):
                child = canonicalize_name(dependency.name)
                assert child in locked, (service, name, "missing dependency", child)
                assert distribution(child).version in dependency.specifier, (service, name, child)
    print("PASS", service, len(locked), "locked packages", flush=True)
