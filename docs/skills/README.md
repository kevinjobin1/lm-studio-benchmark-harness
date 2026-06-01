# Skill System

ModelLens skills are **pure function tools** that benchmark logic can invoke. They are versioned, sandboxed, and validated against a lockfile for deterministic, reproducible evaluation.

---

## Philosophy

Benchmark logic should be extensible without bloating core. Skills provide:

- **Determinism** — Same input always produces same output
- **Sandboxing** — No filesystem/network access outside the sandbox
- **Versioning** — Changes require version bumps + lockfile updates
- **Immutability** — Cannot be modified at runtime once registered

---

## Built-in skills

Four built-in skills ship with ModelLens (see `packages/skills/builtins/`):

| Skill | Description | Input | Output |
|-------|-------------|-------|--------|
| `read_file` | Read file contents within sandbox | `path` | File text or error |
| `write_file` | Write content to file within sandbox | `path`, `content` | Success/error |
| `json_parse` | Parse and validate JSON | `content`, `schema` | Parsed data or validation errors |
| `diff` | Compute text diff between two strings | `original`, `modified` | Unified diff output |

---

## Lockfile system

The `skill-lock.json` file ensures reproducibility across machines:

```json
{
  "skills": {
    "read_file": {
      "version": "1.0.0",
      "checksum": "a1b2c3d4e5f6..."
    },
    "write_file": {
      "version": "1.0.0",
      "checksum": "b2c3d4e5f6a1..."
    }
  },
  "mode": "strict"
}
```

### Lock modes

| Mode | Behavior |
|------|----------|
| `strict` | **Fail** on any version mismatch (required for benchmarks) |
| `warn` | Log warning but continue (dev only) |
| `ignore` | Skip lock checking entirely (NOT for benchmarks) |

### CLI

```bash
# Generate lockfile from built-ins
python packages/skills/lockfile.py --generate

# Verify existing lockfile
python packages/skills/lockfile.py --verify
```

---

## Skill interface

Every skill extends the `Skill` abstract base class:

```python
from skills.types import Skill, SkillManifest, SkillInput, SkillOutput, SkillContext

class MySkill(Skill):
    def _create_manifest(self) -> SkillManifest:
        return SkillManifest(
            name="my_skill",
            version="1.0.0",
            description="What this skill does",
            input_schema={
                "type": "object",
                "required": ["input_field"],
                "properties": {
                    "input_field": {"type": "string"},
                },
            },
            tags=["utility"],
        )

    async def run(self, input_data: SkillInput, ctx: SkillContext) -> SkillOutput:
        value = input_data.get("input_field")
        # ... pure logic, no side effects ...
        return SkillOutput(
            success=True,
            data={"result": value.upper()},
        )
```

### Key types

| Type | Purpose |
|------|---------|
| `SkillManifest` | Static metadata: name, version, schemas, tags |
| `SkillInput` | Validated input with JSON schema checking |
| `SkillOutput` | Success/failure with data or error |
| `SkillContext` | Sandboxed environment (working directory, model name, run ID) |
| `Action` | A single tool invocation in an agentic sequence |
| `AgenticResponse` | Ordered list of actions for agentic benchmarks |
| `AgenticScore` | Multi-dimensional agentic evaluation score |

---

## Agentic scoring

For agentic/tool-use benchmarks, models are scored on:

| Dimension | Weight | What it measures |
|-----------|--------|-------------------|
| **Validity** | 25% | Is JSON well-formed? Schema-compliant? Using real skills? |
| **Planning** | 25% | Is the tool sequence correct and minimal? |
| **Skill correctness** | 30% | Correct tool chosen? Correct parameters? |
| **Constraint adherence** | 20% | Respects skill allowlist? No hallucinated skills? |

The `AgenticScore` type tracks hallucinated skills separately — tools the model invented that don't exist.

---

## Registry

The `SkillRegistry` manages all registered skills:

```python
from skills.registry import create_registry

# Auto-loads built-ins and validates against lockfile
registry = create_registry(lockfile_path="skill-lock.json")

# List registered skills
print(registry.list_names())  # ['diff', 'json_parse', 'read_file', 'write_file']

# Get a skill
skill = registry.get("json_parse")

# Skills CANNOT be registered after finalize()
registry.finalize()
```

---

## Creating a community skill pack

1. Create a directory in `packages/skills/community/`
2. Add a `pack.json` manifest:
   ```json
   {
     "name": "my-pack",
     "version": "1.0.0",
     "description": "Custom evaluation skills"
   }
   ```
3. Add skill Python modules
4. Load with: `registry.load_community_pack("packages/skills/community/my-pack")`

---

## Future: WASM sandbox

V3 of the roadmap plans to execute skills inside WASM for enhanced security and portability. Supported runtimes:

- **WASI** — WebAssembly System Interface
- **Javy** — JavaScript in WASM
- **Extism** — Universal plugin system

This will allow community skills to run in any language that compiles to WASM (Rust, Go, TypeScript, Python).
