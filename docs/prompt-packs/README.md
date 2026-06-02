# Prompt Packs

Prompt packs are versioned, community-extensible benchmark collections. Each pack contains a set of prompts targeting a specific technology or workflow.

---

## Pack format

```yaml
# pack.json
name: react-native
version: 1.0.0
category: coding
description: React Native debugging and refactoring challenges

prompts:
  - prompts/debug-navigation.md
  - prompts/refactor-component.md
  - prompts/state-management.md
```

### Field reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique pack identifier (kebab-case) |
| `version` | Yes | Semver (e.g., `1.0.0`) |
| `category` | Yes | `coding`, `reasoning`, `math`, `instruction`, `debugging`, `agentic` |
| `description` | No | One-line summary |
| `prompts` | Yes | Array of relative paths to prompt files |

---

## Prompt file format

Each prompt file is a JSON document:

```json
{
  "id": "debug-navigation-1",
  "prompt": "Fix the navigation bug in this React Native app:\n\n```tsx\n// ...component code...\n```",
  "category": "debugging",
  "expected_keywords": ["useNavigation", "reset"],
  "constraints": {
    "json_only": false,
    "no_markdown": false,
    "max_length": 2000
  },
  "expected_answer": null,
  "difficulty": "medium"
}
```

### Prompt fields

| Field | Description |
|-------|-------------|
| `id` | Unique identifier within the pack |
| `prompt` | The full prompt text (may include markdown, code blocks) |
| `category` | `code`, `frontend`, `reasoning`, `math`, `instruction` |
| `expected_keywords` | Key concepts the response should include |
| `constraints` | Formatting rules: `json_only`, `no_markdown`, `max_length`, `bullet_count` |
| `expected_answer` | For math prompts: the numerical answer (with ±tolerance) |
| `difficulty` | `easy`, `medium`, `hard` |

---

## Built-in packs

Model Lens ships with 4 prompt packs:

| Pack | Category | Prompt count | Focus |
|------|----------|-------------|-------|
| **React** | Coding | 4 | Hooks, state, components, animations |
| **NestJS** | Coding | 4 | DI, services, gateways, auth |
| **Debugging** | Debugging | 5 | Type errors, race conditions, DI bugs, Prisma, stale closures |
| **NestJS Agentic** | Agentic | 5 | Kafka, pipes, Prisma, cache, auth (tool-use format) |

### Pack structure

```
packages/prompt_packs/
  react-pack/
    pack.json              ← Pack manifest
    prompts/
      hooks.json           ← Prompt: "Implement a custom useDebounce hook"
      state.json           ← Prompt: "Add state management for a shopping cart"
      components.json      ← Prompt: "Build a responsive data table component"
      animations.json      ← Prompt: "Create a page transition animation"
  nestjs-pack/
    pack.json
    prompts/
      di.json, service.json, gateway.json, auth.json
  debugging-pack/
    pack.json
    prompts/
      type_errors.json, race_condition.json, di_bugs.json,
      prisma.json, stale_closure.json
  nestjs-agentic-pack/
    pack.json
    prompts/
      kafka.json, pipes.json, prisma.json, cache.json, auth.json
```

---

## Prompt generation

Model Lens can generate prompt variants automatically to reduce overfitting and increase diversity.

### Techniques

- **Paraphrasing** — Reword the prompt while preserving intent
- **Variable substitution** — Replace function names, types, and identifiers
- **Contextual mutation** — Change context (e.g., swap React for Vue)

### Example

```python
from prompt_generator import PromptGenerator

pg = PromptGenerator()
prompts = pg.generate_default_batch(
    total_prompts=20,
    categories=["code", "frontend", "reasoning", "math", "instruction"],
)

for p in prompts:
    print(f"[{p.category.value}] {p.prompt[:80]}...")
```

---

## Creating a custom pack

1. Create a directory in `packages/prompt_packs/`
2. Add `pack.json` with metadata
3. Create `prompts/` subdirectory with JSON prompt files
4. Reference in benchmark config:
   ```json
   {
     "prompt_sets": ["my-custom-pack"]
   }
   ```
5. Run benchmarks:
   ```bash
   python apps/cli/modellens.py run --models my-model
   ```

### Guidelines

- Prompts should reflect **real developer workflows** — not synthetic puzzles
- Include `expected_keywords` for automated scoring
- Add `constraints` for instruction-following evaluation
- Test prompts manually before contributing
- Keep packs focused on a single technology or problem domain

---

## Contributing packs

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for PR guidelines. Community packs are reviewed for:

- Prompt quality and realism
- Appropriate difficulty level
- Correct `expected_keywords` and `constraints`
- No duplicates with existing packs
