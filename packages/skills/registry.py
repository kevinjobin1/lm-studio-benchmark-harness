#!/usr/bin/env python3
"""
Skill Registry

Central registry for loading, validating, and managing skills.
Skills are immutable at runtime and validated against the lockfile.
"""

from typing import Dict, List, Optional
from pathlib import Path

from .types import Skill, SkillManifest
from .lockfile import SkillLockFile


class SkillRegistry:
    """Immutable registry of skills.

    - Skills are registered once and never modified at runtime
    - Initialized from builtins + optional community packs
    - Validated against modellens.lock on initialization
    """

    def __init__(self, lockfile: Optional[SkillLockFile] = None):
        self._skills: Dict[str, Skill] = {}
        self._lockfile = lockfile
        self._initialized = False

    def register(self, skill: Skill) -> None:
        """Register a skill. Raises if already registered (immutability)."""
        if self._initialized:
            raise RuntimeError(
                f"Cannot register skill '{skill.manifest.name}' after initialization. "
                "Skills are immutable at runtime."
            )

        name = skill.manifest.name
        if name in self._skills:
            raise ValueError(
                f"Skill '{name}' already registered (v{self._skills[name].manifest.version}). "
                f"Remove duplicate or bump version."
            )

        self._skills[name] = skill

    def get(self, name: str) -> Skill:
        """Get a skill by name. Raises KeyError if not found."""
        if name not in self._skills:
            available = ", ".join(sorted(self._skills.keys()))
            raise KeyError(f"Skill '{name}' not found. Available: {available}")
        return self._skills[name]

    def has(self, name: str) -> bool:
        """Check if a skill is registered."""
        return name in self._skills

    def list_all(self) -> List[Skill]:
        """List all registered skills."""
        return sorted(self._skills.values(), key=lambda s: s.manifest.name)

    def list_names(self) -> List[str]:
        """List all registered skill names."""
        return sorted(self._skills.keys())

    def count(self) -> int:
        """Number of registered skills."""
        return len(self._skills)

    def finalize(self) -> List[str]:
        """Finalize the registry. Validates against lockfile.

        After this call, no more skills can be registered.
        Returns list of lock errors (empty = all good).
        """
        self._initialized = True

        if not self._lockfile:
            return []

        # Build manifest for lock verification
        manifest = {
            name: skill.manifest.version
            for name, skill in self._skills.items()
        }

        return self._lockfile.verify(manifest)

    def load_builtins(self) -> None:
        """Load built-in skills from skills/builtins/."""
        from .builtins.read_file import ReadFileSkill
        from .builtins.write_file import WriteFileSkill
        from .builtins.json_parse import JsonParseSkill
        from .builtins.diff import DiffSkill

        self.register(ReadFileSkill())
        self.register(WriteFileSkill())
        self.register(JsonParseSkill())
        self.register(DiffSkill())

    def load_community_pack(self, pack_path: str) -> int:
        """Load skills from a community pack directory.

        Args:
            pack_path: Path to a directory containing skill modules.

        Returns:
            Number of skills loaded.
        """
        pack_dir = Path(pack_path)
        if not pack_dir.is_dir():
            raise FileNotFoundError(f"Pack directory not found: {pack_path}")

        count = 0
        # Look for pack.json manifest
        pack_json = pack_dir / "pack.json"
        if pack_json.exists():
            import json
            with open(pack_json) as f:
                pack_data = json.load(f)
            print(f"Loading pack: {pack_data.get('name', pack_dir.name)} v{pack_data.get('version', 'unknown')}")

        # Load skill modules from the pack directory
        for py_file in sorted(pack_dir.glob("*.py")):
            if py_file.name.startswith("_") or py_file.name == "pack.json":
                continue

            # Import the module and look for Skill subclasses
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                f"skills.community.{py_file.stem}", str(py_file)
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Find all Skill subclasses
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, Skill)
                        and attr is not Skill
                    ):
                        try:
                            self.register(attr())
                            count += 1
                        except (ValueError, RuntimeError) as e:
                            print(f"  Skipping {attr_name}: {e}")

        return count

    def to_dict(self) -> Dict:
        """Serialize registry state for config snapshots."""
        return {
            "skills": {s.manifest.name: s.manifest.version for s in self.list_all()},
            "count": self.count(),
            "initialized": self._initialized,
        }


def create_registry(
    lockfile_path: str = "modellens.lock",
    load_builtins: bool = True,
) -> SkillRegistry:
    """Factory function to create and initialize a skill registry.

    Args:
        lockfile_path: Path to modellens.lock
        load_builtins: Whether to auto-load built-in skills

    Returns:
        Initialized SkillRegistry
    """
    # Load lockfile if it exists
    lockfile = None
    try:
        lockfile = SkillLockFile.load(lockfile_path)
    except FileNotFoundError:
        # Create default lockfile
        lockfile = SkillLockFile.generate_default()
        lockfile.save(lockfile_path)
        print(f"Created default {lockfile_path}")

    registry = SkillRegistry(lockfile=lockfile)

    if load_builtins:
        registry.load_builtins()

    # Verify against lockfile immediately
    lock_errors = registry.finalize()
    if lock_errors:
        raise RuntimeError(
            "Skill lockfile verification failed:\n  " +
            "\n  ".join(lock_errors)
        )

    return registry
