#!/usr/bin/env python3
"""
Skill Pack SDK — npm-like system for building, sharing, and installing
benchmark packs.

Each pack bundles:
  - pack.json (metadata + dependencies)
  - prompts/ (parameterized prompt templates)
  - skills/ (optional: custom agentic skills)
  - evaluators/ (optional: custom scoring modules)

Workflow:
  1. scaffold — create a new pack from template
  2. develop — add prompts, skills, evaluators
  3. validate — check schema compliance
  4. publish — tag and share
  5. install — discover and use community packs

Usage:
  python -m skill_pack_sdk scaffold my-pack
  python -m skill_pack_sdk validate prompt-packs/my-pack
  python -m skill_pack_sdk list
  python -m skill_pack_sdk install ./community-packs/react-pack
"""

import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ── Schema Constants ─────────────────────────────────────────────

PACK_JSON_SCHEMA = {
    "type": "object",
    "required": ["name", "version", "description", "tags", "generator"],
    "properties": {
        "name": {"type": "string", "pattern": "^[a-z0-9_-]+$"},
        "version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
        "description": {"type": "string", "maxLength": 200},
        "tags": {"type": "array", "items": {"type": "string"}},
        "generator": {"type": "string"},
        "author": {"type": "string"},
        "license": {"type": "string", "default": "MIT"},
        "repository": {"type": "string"},
        "dependencies": {
            "type": "object",
            "additionalProperties": {"type": "string"},
        },
        "categories": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "label", "difficulty", "count"],
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "difficulty": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["easy", "medium", "hard"]},
                    },
                    "count": {"type": "integer", "minimum": 0},
                },
            },
        },
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "version"],
                "properties": {
                    "name": {"type": "string"},
                    "version": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
        "total_prompts": {"type": "integer", "minimum": 0},
        "min_benchmark_version": {"type": "string"},
    },
}

PACK_TEMPLATE = {
    "name": "my-pack",
    "version": "0.1.0",
    "description": "A custom benchmark pack",
    "tags": [],
    "generator": "v1",
    "author": "",
    "license": "MIT",
    "categories": [
        {
            "id": "general",
            "label": "General Prompts",
            "difficulty": ["easy", "medium"],
            "count": 2,
        }
    ],
    "skills": [],
    "total_prompts": 0,
    "min_benchmark_version": "1.0.0",
}

PROMPT_TEMPLATE = {
    "id": "general",
    "prompts": [
        {
            "id": "my_pack_general_001",
            "task": "Example task description",
            "difficulty": "medium",
            "template": "Solve this {problem_type} using {language}",
            "params": {
                "problem_type": ["sorting", "searching", "parsing"],
                "language": ["TypeScript", "Python", "Go"],
            },
            "constraints": ["Use proper types", "Include error handling"],
            "expected_keywords": ["function", "return", "type"],
        }
    ],
}


# ── Registry ──────────────────────────────────────────────────────

@dataclass
class RegistryEntry:
    """A pack entry in the registry."""
    name: str
    version: str
    description: str
    tags: List[str]
    path: str  # local path or URL
    installed_at: str = ""
    author: str = ""
    license_: str = "MIT"
    dependencies: Dict[str, str] = field(default_factory=dict)
    skills_count: int = 0
    prompts_count: int = 0

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "tags": self.tags,
            "path": self.path,
            "installed_at": self.installed_at,
            "author": self.author,
            "license": self.license_,
            "dependencies": self.dependencies,
            "skills_count": self.skills_count,
            "prompts_count": self.prompts_count,
        }


class PackRegistry:
    """Local registry of installed packs (like package.json for packs).

    Maintains ~/.lmbench/pack-registry.json tracking all installed packs
    with versions, dependencies, and metadata.
    """

    REGISTRY_FILE = Path.home() / ".lmbench" / "pack-registry.json"

    def __init__(self):
        self.entries: Dict[str, RegistryEntry] = {}
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        self._loaded = True

        if self.REGISTRY_FILE.exists():
            try:
                with open(self.REGISTRY_FILE) as f:
                    data = json.load(f)
                for entry_data in data.get("packs", []):
                    entry = RegistryEntry(
                        name=entry_data["name"],
                        version=entry_data["version"],
                        description=entry_data.get("description", ""),
                        tags=entry_data.get("tags", []),
                        path=entry_data["path"],
                        installed_at=entry_data.get("installed_at", ""),
                        author=entry_data.get("author", ""),
                        license_=entry_data.get("license", "MIT"),
                        dependencies=entry_data.get("dependencies", {}),
                        skills_count=entry_data.get("skills_count", 0),
                        prompts_count=entry_data.get("prompts_count", 0),
                    )
                    self.entries[entry.name] = entry
            except Exception:
                pass

    def save(self):
        self.REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0.0",
            "updated_at": datetime.now().isoformat(),
            "packs": [e.to_dict() for e in self.entries.values()],
        }
        with open(self.REGISTRY_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    def register(self, entry: RegistryEntry):
        self._ensure_loaded()
        self.entries[entry.name] = entry
        self.save()

    def unregister(self, name: str) -> bool:
        self._ensure_loaded()
        if name in self.entries:
            del self.entries[name]
            self.save()
            return True
        return False

    def get(self, name: str) -> Optional[RegistryEntry]:
        self._ensure_loaded()
        return self.entries.get(name)

    def list_all(self) -> List[RegistryEntry]:
        self._ensure_loaded()
        return sorted(self.entries.values(), key=lambda e: e.name)

    def is_installed(self, name: str, version: Optional[str] = None) -> bool:
        self._ensure_loaded()
        entry = self.entries.get(name)
        if not entry:
            return False
        if version:
            return entry.version == version
        return True


# ── Scaffolder ────────────────────────────────────────────────────

class PackScaffolder:
    """Generate a new pack from template."""

    def __init__(self, packs_root: Path):
        self.packs_root = packs_root

    def scaffold(self, name: str, description: str = "",
                 author: str = "", tags: Optional[List[str]] = None) -> Path:
        """Create a new pack directory with template files.

        Args:
            name: Pack name (kebab-case, e.g. 'my-react-pack')
            description: Short description
            author: Author name
            tags: List of tags
        """
        pack_dir = self.packs_root / name

        if pack_dir.exists():
            raise FileExistsError(f"Pack directory already exists: {pack_dir}")

        # Create directory structure
        pack_dir.mkdir(parents=True)
        (pack_dir / "prompts").mkdir()
        (pack_dir / "skills").mkdir()
        (pack_dir / "skills" / ".gitkeep").touch()
        (pack_dir / "evaluators").mkdir()
        (pack_dir / "evaluators" / ".gitkeep").touch()

        # Create pack.json
        pack_json = dict(PACK_TEMPLATE)
        pack_json["name"] = name
        pack_json["description"] = description or f"A {name} benchmark pack"
        pack_json["author"] = author
        pack_json["tags"] = tags or []
        pack_json["categories"] = [
            {
                "id": "general",
                "label": "General Prompts",
                "difficulty": ["easy", "medium", "hard"],
                "count": 1,
            }
        ]

        with open(pack_dir / "pack.json", 'w') as f:
            json.dump(pack_json, f, indent=2)

        # Create example prompt
        prompt_data = dict(PROMPT_TEMPLATE)
        with open(pack_dir / "prompts" / "general.json", 'w') as f:
            json.dump(prompt_data, f, indent=2)

        # Create README
        readme = f"""# {name}

{pack_json['description']}

## Prompts

Edit `prompts/general.json` to add your own prompts.

## Skills (Optional)

Add custom agentic skills in `skills/`. Each skill is a Python module
implementing the `Skill` interface from `skills.types`.

## Evaluators (Optional)

Add custom scoring evaluators in `evaluators/`.

## Publishing

```bash
python -m skill_pack_sdk validate {name}
python -m skill_pack_sdk publish {name}
```
"""
        with open(pack_dir / "README.md", 'w') as f:
            f.write(readme)

        return pack_dir


# ── Validator ─────────────────────────────────────────────────────

class PackValidator:
    """Validate packs against the SDK schema."""

    @staticmethod
    def validate_pack(pack_dir: Path) -> Tuple[bool, List[str]]:
        """Validate a complete pack. Returns (valid, errors)."""
        errors = []

        pack_json_path = pack_dir / "pack.json"
        if not pack_json_path.exists():
            return False, [f"No pack.json found in {pack_dir}"]

        try:
            with open(pack_json_path) as f:
                pack_data = json.load(f)
        except json.JSONDecodeError as e:
            return False, [f"Invalid pack.json JSON: {e}"]
        except Exception as e:
            return False, [f"Cannot read pack.json: {e}"]

        # Validate required fields
        for field in PACK_JSON_SCHEMA["required"]:
            if field not in pack_data:
                errors.append(f"pack.json: missing required field '{field}'")

        # Validate name format
        name = pack_data.get("name", "")
        if name and not all(c.isalnum() or c in "_-" for c in name):
            errors.append(f"pack.json: invalid name '{name}' — use kebab-case (a-z, 0-9, -, _)")

        # Validate version format
        version = pack_data.get("version", "")
        if version:
            parts = version.split(".")
            if len(parts) != 3 or not all(p.isdigit() for p in parts):
                errors.append(f"pack.json: invalid version '{version}' — use semver (X.Y.Z)")

        # Validate categories
        categories = pack_data.get("categories", [])
        for i, cat in enumerate(categories):
            for field in ["id", "label", "difficulty", "count"]:
                if field not in cat:
                    errors.append(f"pack.json: category[{i}] missing '{field}'")

        # Check prompts directory
        prompts_dir = pack_dir / "prompts"
        if not prompts_dir.exists():
            errors.append("Missing prompts/ directory")
        else:
            prompt_files = list(prompts_dir.glob("*.json"))
            if not prompt_files:
                errors.append("No prompt files in prompts/ directory")

            total_prompts = 0
            for pf in prompt_files:
                try:
                    with open(pf) as f:
                        pdata = json.load(f)
                    prompts = pdata.get("prompts", [])
                    total_prompts += len(prompts)

                    # Check each prompt has required fields
                    for j, p in enumerate(prompts):
                        for field in ["id", "task", "difficulty"]:
                            if field not in p:
                                errors.append(f"{pf.name}: prompt[{j}] missing '{field}'")

                    # Check for duplicate IDs
                    ids = [p.get("id") for p in prompts]
                    dupes = [pid for pid in ids if ids.count(pid) > 1]
                    for d in set(dupes):
                        errors.append(f"{pf.name}: duplicate prompt ID '{d}'")

                except json.JSONDecodeError as e:
                    errors.append(f"{pf.name}: invalid JSON: {e}")

            # Verify count matches
            declared = pack_data.get("total_prompts", 0)
            if total_prompts != declared:
                errors.append(
                    f"pack.json total_prompts={declared} but found {total_prompts} prompts"
                )

        # Check skills directory (optional)
        skills_dir = pack_dir / "skills"
        if skills_dir.exists():
            skill_files = [
                f for f in skills_dir.glob("*.py")
                if not f.name.startswith("_") and not f.name.startswith(".")
            ]
            declared_skills = pack_data.get("skills", [])
            if skill_files and not declared_skills:
                errors.append("skills/ directory has Python files but pack.json has no 'skills' declared")
            if declared_skills:
                declared_names = {s["name"] for s in declared_skills}
                actual_names = {f.stem for f in skill_files}
                for name in declared_names - actual_names:
                    errors.append(f"Declared skill '{name}' has no module in skills/")
                for name in actual_names - declared_names:
                    errors.append(f"Module skills/{name}.py not declared in pack.json")

        return len(errors) == 0, errors

    @staticmethod
    def validate_all(packs_root: Path) -> Tuple[List[str], List[str]]:
        """Validate all packs in a directory. Returns (valid_packs, invalid_packs)."""
        valid = []
        invalid = []

        for pack_dir in sorted(packs_root.iterdir()):
            if not pack_dir.is_dir() or pack_dir.name.startswith('.') or pack_dir.name.startswith('__'):
                continue
            if not (pack_dir / "pack.json").exists():
                continue

            ok, errors = PackValidator.validate_pack(pack_dir)
            if ok:
                valid.append(pack_dir.name)
            else:
                invalid.append(f"{pack_dir.name}: {'; '.join(errors)}")

        return valid, invalid


# ── Installer ─────────────────────────────────────────────────────

class PackInstaller:
    """Install and uninstall packs with dependency resolution."""

    def __init__(self, packs_root: Path):
        self.packs_root = packs_root
        self.registry = PackRegistry()

    def install(self, source_path: str, force: bool = False) -> RegistryEntry:
        """Install a pack from a local path.

        Args:
            source_path: Path to the pack directory
            force: Overwrite existing installation
        """
        source = Path(source_path).resolve()

        if not source.exists():
            raise FileNotFoundError(f"Pack not found: {source_path}")

        pack_json = source / "pack.json"
        if not pack_json.exists():
            raise ValueError(f"No pack.json in {source_path}")

        with open(pack_json) as f:
            pack_data = json.load(f)

        name = pack_data["name"]
        version = pack_data["version"]

        # Check if already installed
        if self.registry.is_installed(name) and not force:
            existing = self.registry.get(name)
            raise ValueError(
                f"Pack '{name}' v{existing.version} is already installed. "
                "Use --force to overwrite."
            )

        # Validate
        ok, errors = PackValidator.validate_pack(source)
        if not ok:
            raise ValueError(f"Pack validation failed:\n  " + "\n  ".join(errors))

        # Copy to packs root
        dest = self.packs_root / name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source, dest)

        # Count skills and prompts
        skills_count = len(list((dest / "skills").glob("*.py"))) if (dest / "skills").exists() else 0
        prompts_count = 0
        prompts_dir = dest / "prompts"
        if prompts_dir.exists():
            for pf in prompts_dir.glob("*.json"):
                try:
                    with open(pf) as f:
                        pdata = json.load(f)
                    prompts_count += len(pdata.get("prompts", []))
                except Exception:
                    pass

        # Register
        entry = RegistryEntry(
            name=name,
            version=version,
            description=pack_data.get("description", ""),
            tags=pack_data.get("tags", []),
            path=str(dest),
            installed_at=datetime.now().isoformat(),
            author=pack_data.get("author", ""),
            license_=pack_data.get("license", "MIT"),
            dependencies=pack_data.get("dependencies", {}),
            skills_count=skills_count,
            prompts_count=prompts_count,
        )
        self.registry.register(entry)

        print(f"✓ Installed '{name}' v{version} ({prompts_count} prompts, {skills_count} skills)")
        return entry

    def uninstall(self, name: str) -> bool:
        """Uninstall a pack by name."""
        entry = self.registry.get(name)
        if not entry:
            print(f"Pack '{name}' is not installed.")
            return False

        # Remove directory
        pack_dir = Path(entry.path)
        if pack_dir.exists() and pack_dir.parent == self.packs_root:
            shutil.rmtree(pack_dir)

        # Unregister
        self.registry.unregister(name)
        print(f"✓ Uninstalled '{name}' v{entry.version}")
        return True

    def list_installed(self) -> List[Dict]:
        """List all installed packs with details."""
        result = []
        for entry in self.registry.list_all():
            pack_dir = Path(entry.path)
            exists = pack_dir.exists()
            result.append({
                "name": entry.name,
                "version": entry.version,
                "description": entry.description,
                "installed_at": entry.installed_at,
                "prompts": entry.prompts_count,
                "skills": entry.skills_count,
                "path": entry.path,
                "exists": exists,
                "status": "✓" if exists else "✗ (missing)",
            })
        return result


# ── CLI ───────────────────────────────────────────────────────────

class PackSDK:
    """Main entry point for the Skill Pack SDK."""

    def __init__(self, packs_root: Optional[Path] = None):
        self.packs_root = packs_root or Path("prompt_packs")
        self.scaffolder = PackScaffolder(self.packs_root)
        self.validator = PackValidator()
        self.installer = PackInstaller(self.packs_root)

    def scaffold(self, name: str, description: str = "", author: str = "",
                 tags: Optional[List[str]] = None):
        path = self.scaffolder.scaffold(name, description, author, tags)
        print(f"✓ Created pack at: {path}")
        print(f"  Edit {path / 'pack.json'} to customize metadata")
        print(f"  Edit {path / 'prompts/general.json'} to add prompts")
        if (path / "skills").exists():
            print(f"  Add custom skills to {path / 'skills/'}")

    def validate(self, pack_name: str):
        # Handle both "nestjs-pack" and "prompt_packs/nestjs-pack"
        pack_path = Path(pack_name)
        if pack_path.is_absolute() or pack_path.parts[0] == self.packs_root.name:
            pack_dir = pack_path
        else:
            pack_dir = self.packs_root / pack_name
        ok, errors = self.validator.validate_pack(pack_dir)

        if ok:
            print(f"✓ Pack '{pack_name}' is valid")
        else:
            print(f"✗ Pack '{pack_name}' has errors:")
            for err in errors:
                print(f"  - {err}")

    def validate_all(self):
        valid, invalid = self.validator.validate_all(self.packs_root)
        print(f"\n✓ Valid packs ({len(valid)}): {', '.join(valid) if valid else 'none'}")
        if invalid:
            print(f"\n✗ Invalid packs ({len(invalid)}):")
            for msg in invalid:
                print(f"  - {msg}")

    def install(self, path: str, force: bool = False):
        self.installer.install(path, force)

    def uninstall(self, name: str):
        self.installer.uninstall(name)

    def list_packs(self):
        # First, auto-discover packs in packs_root that aren't in registry
        self._auto_discover()

        installed = self.installer.list_installed()
        if not installed:
            print("No packs found.")
            return

        print(f"\n📦 Available packs ({len(installed)}):\n")
        for p in installed:
            print(f"  {p['status']} {p['name']} v{p['version']} — {p['description']}")
            print(f"    Path: {p['path'][:60]}, {p['prompts']} prompts, {p['skills']} skills")
            print()

    def _auto_discover(self):
        """Auto-discover packs in packs_root and register them if not already."""
        if not self.packs_root.exists():
            return
        for pack_dir in self.packs_root.iterdir():
            if not pack_dir.is_dir() or pack_dir.name.startswith('.') or pack_dir.name.startswith('__'):
                continue
            pack_json = pack_dir / "pack.json"
            if not pack_json.exists():
                continue
            try:
                with open(pack_json) as f:
                    data = json.load(f)
                name = data.get("name", pack_dir.name)
                if not self.installer.registry.is_installed(name):
                    # Auto-register
                    entry = RegistryEntry(
                        name=name,
                        version=data.get("version", "0.1.0"),
                        description=data.get("description", ""),
                        tags=data.get("tags", []),
                        path=str(pack_dir),
                        installed_at="discovered",
                        author=data.get("author", ""),
                        license_=data.get("license", "MIT"),
                        dependencies=data.get("dependencies", {}),
                    )
                    self.installer.registry.register(entry)
            except Exception:
                pass

    def info(self, pack_name: str):
        entry = self.installer.registry.get(pack_name)
        if not entry:
            print(f"Pack '{pack_name}' is not installed.")
            return

        pack_dir = Path(entry.path)
        print(f"\n📦 {entry.name} v{entry.version}")
        print(f"   Description: {entry.description}")
        print(f"   Author: {entry.author or 'unknown'}")
        print(f"   License: {entry.license_}")
        print(f"   Tags: {', '.join(entry.tags) or 'none'}")
        print(f"   Installed: {entry.installed_at}")
        print(f"   Prompts: {entry.prompts_count}")
        print(f"   Skills: {entry.skills_count}")

        if entry.dependencies:
            print(f"   Dependencies:")
            for dep, ver in entry.dependencies.items():
                print(f"     - {dep} v{ver}")

        # Show categories if pack exists
        if pack_dir.exists():
            pack_json = pack_dir / "pack.json"
            if pack_json.exists():
                with open(pack_json) as f:
                    data = json.load(f)
                cats = data.get("categories", [])
                if cats:
                    print(f"   Categories:")
                    for cat in cats:
                        print(f"     - {cat['label']} ({', '.join(cat['difficulty'])})")


# ── Convenience ────────────────────────────────────────────────────

def get_sdk(packs_root: Optional[Path] = None) -> PackSDK:
    """Get the Skill Pack SDK instance."""
    return PackSDK(packs_root)


# ── Main ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Skill Pack SDK")
        print("  scaffold <name>          Create a new pack")
        print("  validate [name]          Validate a pack (or all)")
        print("  install <path> [--force] Install a pack from path")
        print("  uninstall <name>         Uninstall a pack")
        print("  list                     List installed packs")
        print("  info <name>              Show pack details")
        sys.exit(0)

    sdk = PackSDK()
    cmd = sys.argv[1]

    if cmd == "scaffold" and len(sys.argv) >= 3:
        sdk.scaffold(sys.argv[2])
    elif cmd == "validate":
        if len(sys.argv) >= 3:
            sdk.validate(sys.argv[2])
        else:
            sdk.validate_all()
    elif cmd == "install" and len(sys.argv) >= 3:
        force = "--force" in sys.argv
        sdk.install(sys.argv[2], force=force)
    elif cmd == "uninstall" and len(sys.argv) >= 3:
        sdk.uninstall(sys.argv[2])
    elif cmd == "list":
        sdk.list_packs()
    elif cmd == "info" and len(sys.argv) >= 3:
        sdk.info(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
