# Contributing to Tooli

Thank you for your interest in contributing to Tooli!

## Getting Started

1. Fork the repository and clone your fork
2. Create a virtual environment and install dev dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```
3. Create a branch for your change:
   ```bash
   git checkout -b my-feature
   ```

## Development Workflow

### Running Tests

```bash
pytest
```

### Linting and Type Checking

```bash
ruff check .
mypy tooli
```

### Code Style

- We use **ruff** for linting and import sorting
- We use **mypy** in strict mode for type checking
- All public functions should have type annotations
- Follow existing patterns in the codebase

## Pull Requests

1. Ensure all tests pass and linting is clean
2. Write tests for new functionality
3. Keep PRs focused — one feature or fix per PR
4. Write a clear description of what changed and why

## Reporting Issues

- Use [GitHub Issues](https://github.com/weisberg/tooli/issues)
- Include a minimal reproducible example when possible
- Specify your Python version and tooli version

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
