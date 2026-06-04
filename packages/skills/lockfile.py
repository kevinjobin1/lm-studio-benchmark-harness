#!/usr/bin/env python3
"""
Skill Lock File System

CRITICAL for reproducibility:
- modellens.lock locks skill versions
- Benchmark MUST fail if lock mismatch
- No silent version drift allowed
- Ensures reproducibility across machines
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field


@dataclass
class LockEntry:
    """Single skill entry in the lockfile."""

    name: str
    version: str
    checksum: str = ""


@dataclass
class SkillLockFile:
    """Represents a modellens.lock file.

    The lockfile ensures deterministic evaluation by pinning exact
    skill versions. Any mismatch causes the benchmark to fail.

    Modes:
    - strict: fail on any mismatch (default, required for benchmark)
    - warn: log warning but continue (dev only)
    - ignore: skip lock checking entirely (NOT for benchmarks)
    """

    skills: Dict[str, LockEntry] = field(default_factory=dict)
    mode: str = "strict"  # strict | warn | ignore
    _checksums: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str = "modellens.lock") -> "SkillLockFile":
        """Load a skill lockfile from disk."""
        lock_path = Path(path)
        if not lock_path.exists():
            raise FileNotFoundError(
                f"Skill lockfile not found: {lock_path}. "
                "Create one with: python skills/lockfile.py --generate"
            )

        with open(lock_path) as f:
            data = json.load(f)

        skills = {}
        for name, info in data.get("skills", {}).items():
            if isinstance(info, str):
                # Simple format: "skill_name": "version"
                skills[name] = LockEntry(name=name, version=info)
            else:
                # Full format with checksum
                skills[name] = LockEntry(
                    name=name,
                    version=info.get("version", ""),
                    checksum=info.get("checksum", ""),
                )

        return cls(
            skills=skills,
            mode=data.get("mode", "strict"),
        )

    def save(self, path: str = "modellens.lock"):
        """Save the lockfile to disk."""
        data = {
            "skills": {
                name: {
                    "version": entry.version,
                    "checksum": entry.checksum,
                }
                for name, entry in sorted(self.skills.items())
            },
            "mode": self.mode,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def verify(self, skill_manifest: Dict[str, str]) -> List[str]:
        """Verify that loaded skills match the lockfile.

        Args:
            skill_manifest: Dict mapping skill name -> version

        Returns:
            List of error messages. Empty = all good.
        """
        if self.mode == "ignore":
            return []

        errors = []
        lock_names = set(self.skills.keys())
        manifest_names = set(skill_manifest.keys())

        # Check for missing skills in lockfile
        for name in manifest_names - lock_names:
            msg = f"Skill '{name}' v{skill_manifest[name]} not in lockfile"
            if self.mode == "strict":
                errors.append(f"LOCK ERROR: {msg}")
            elif self.mode == "warn":
                print(f"LOCK WARNING: {msg}")

        # Check for version mismatches
        for name in manifest_names & lock_names:
            lock_version = self.skills[name].version
            manifest_version = skill_manifest[name]
            if lock_version != manifest_version:
                msg = (
                    f"Skill '{name}' version mismatch: "
                    f"lockfile={lock_version}, actual={manifest_version}"
                )
                if self.mode == "strict":
                    errors.append(f"LOCK ERROR: {msg}")
                elif self.mode == "warn":
                    print(f"LOCK WARNING: {msg}")

        # Check for extra skills in lockfile not in manifest
        for name in lock_names - manifest_names:
            msg = f"Skill '{name}' v{self.skills[name].version} in lockfile but not loaded"
            if self.mode == "strict":
                errors.append(f"LOCK ERROR: {msg}")
            elif self.mode == "warn":
                print(f"LOCK WARNING: {msg}")

        return errors

    def add_skill(self, name: str, version: str, source_code: str = ""):
        """Add or update a skill in the lockfile."""
        checksum = hashlib.sha256(source_code.encode()).hexdigest()[:16] if source_code else ""
        self.skills[name] = LockEntry(name=name, version=version, checksum=checksum)

    def get_version(self, name: str) -> Optional[str]:
        """Get the locked version of a skill."""
        entry = self.skills.get(name)
        return entry.version if entry else None

    def list_skills(self) -> List[str]:
        """List all locked skill names."""
        return sorted(self.skills.keys())

    @classmethod
    def generate_default(cls) -> "SkillLockFile":
        """Generate a default lockfile with built-in skills."""
        return cls(
            skills={
                "read_file": LockEntry(name="read_file", version="1.0.0"),
                "write_file": LockEntry(name="write_file", version="1.0.0"),
                "json_parse": LockEntry(name="json_parse", version="1.0.0"),
                "diff": LockEntry(name="diff", version="1.0.0"),
            },
            mode="strict",
        )


def compute_skill_checksum(skill_module_path: str) -> str:
    """Compute a SHA-256 checksum of a skill's source code for the lockfile."""
    try:
        with open(skill_module_path) as f:
            source = f.read()
        return hashlib.sha256(source.encode()).hexdigest()
    except Exception:
        return ""


# ── CLI ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if "--generate" in sys.argv or "-g" in sys.argv:
        lockfile = SkillLockFile.generate_default()
        lockfile.save("modellens.lock")
        print("Generated modellens.lock with built-in skills:")
        for name in lockfile.list_skills():
            print(f"  {name} v{lockfile.skills[name].version}")
    elif "--verify" in sys.argv:
        try:
            lockfile = SkillLockFile.load("modellens.lock")
            print(f"Lockfile loaded: {len(lockfile.skills)} skills, mode={lockfile.mode}")
            for name, entry in sorted(lockfile.skills.items()):
                print(f"  {name} v{entry.version} (checksum: {entry.checksum or 'none'})")
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        print("Usage: python skills/lockfile.py [--generate|-g] [--verify]")
