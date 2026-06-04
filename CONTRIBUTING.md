# Contributing to Model Lens

Thanks for your interest in contributing!

---

## Development setup

```bash
# Clone and install
git clone https://github.com/kevinjobin1/model-lens.git
cd model-lens
pip install -r requirements.txt

# Install dev dependencies (ruff, mypy, pytest)
pip install ".[dev]"

# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Dashboard
cd apps/dashboard
npm install
npm run dev
```

### Pre-commit hooks

Pre-commit runs automatically on `git commit`. It will:

- **Ruff** — lint Python code (`ruff check --fix`)
- **Ruff format** — enforce consistent formatting (`ruff format`)
- **Mypy** — type-check Python code (`MYPYPATH=packages mypy packages/ apps/cli/`)
- **File hygiene** — trailing whitespace, YAML/JSON/TOML validation, large file detection

The same checks run in CI on every push. See `.pre-commit-config.yaml` for details.

To run manually without committing:

```bash
pre-commit run --all-files
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

- **Python**: 4-space indentation, dataclasses for data, type hints. Formatted with `ruff format` (see `pyproject.toml` for settings).
- **TypeScript**: Follow existing Astro/React patterns
- **URLs**: Use `urllib.parse.urljoin()` and the helpers in `providers.base` (`normalize_base_url`, `get_root_url`, `url_join`) rather than string concatenation or `rstrip`/`removesuffix`
- **Logging**: Use `from packages.logging import get_logger` instead of raw `print()` calls
- **Events**: Emit typed events via the `EventBus` instead of `print()` or logger for observability data (token streams, completions, metrics, lifecycle)
- All new code should reuse existing helpers and classes

---

## Questions?

Open an issue or discussion on GitHub.
