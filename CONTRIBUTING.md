# Contributing to ModelLens

Thanks for your interest in contributing!

---

## Development setup

```bash
# Clone and install
git clone https://github.com/kevinjobin1/lm-studio-benchmark-harness.git
cd lm-studio-benchmark-harness
pip install -r requirements.txt

# Dashboard
cd apps/dashboard
npm install
npm run dev
```

---

## Commit convention

We follow conventional commits:

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation
- `refactor:` — Code restructuring
- `test:` — Tests
- `chore:` — Maintenance

Example: `feat: add Ollama provider adapter`

---

## Pull requests

- Keep changes focused on a single feature or fix
- Update relevant documentation
- Dashboard changes must pass `npx tsc --noEmit` and `npm run build`
- Python changes should maintain existing code style (4-space indents, dataclasses, type hints)

---

## What to contribute

### Prompt packs

The easiest way to contribute. Create a new pack with real-world prompts:

```yaml
# prompt_packs/my-pack/pack.json
{
  "name": "my-framework",
  "version": "1.0.0",
  "category": "coding",
  "description": "Prompts for My Framework"
}
```

### Provider adapters

Implement the `ProviderAdapter` interface (see `packages/providers/base.py`):

```python
class MyProvider(ProviderAdapter):
    name = "my-provider"
    default_port = 8080

    def health_check(self) -> bool: ...
    def list_models(self) -> List[Model]: ...
    def run_prompt(self, request: RunRequest) -> RunResult: ...
    def chat_completion(self, messages, ...) -> Tuple[str, object]: ...
```

### Skills

Create extensible benchmark logic in `packages/skills/builtins/`.

---

## Code style

- Python: 4-space indentation, dataclasses for data, type hints
- TypeScript: Follow existing Astro/React patterns
- All new code should reuse existing helpers and classes

---

## Questions?

Open an issue or discussion on GitHub.
