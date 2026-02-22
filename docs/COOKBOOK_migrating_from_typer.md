# Cookbook: Migrating from Typer

Tooli v6.5.0 no longer uses backend switching. Migrate Typer-style command code to Tooli-native command definitions.

## Before

```python
import typer
app = typer.Typer()
```

## After

```python
from tooli import Tooli
app = Tooli(name="mytool", version="6.5.0")
```

## Parameter metadata

- prefer `from tooli import Annotated, Argument, Option`
- keep function signatures explicit and typed
- return plain Python objects; Tooli handles envelope formatting
