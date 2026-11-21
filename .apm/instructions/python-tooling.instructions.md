---
description: "Running checks with tox and managing dependencies in Python repositories."
applyTo: "**"
---

# Python Tooling

## tox

When the repository configures tox, in `tox.ini`, `tox.toml`, or a
`[tool.tox]` table in `pyproject.toml`:

* Use its environments for formatting, linting, static analysis, and tests.
Do not run the tools behind an environment directly.
* Discover environments with `tox list`, then inspect their definitions. Do
not rely on a remembered list of environments.
* Run `tox` directly. If it is missing, or an environment fails for reasons
unrelated to the change, such as a missing command or a plugin error, treat
it as a missing tool as described in the `working-agreement` instruction.
* Run formatting before linting, e.g. `tox -e format,lint`.
* Before committing, run the repository's non-integration environments, such
as format, lint, static analysis, and unit tests, for the active Python
version. They must pass. If one cannot run, report it and do not commit
until the user decides.
* For tests, run the environment for the active Python version rather than
the whole version matrix, unless asked otherwise.
* Run integration test environments only when the repository's instructions
or the user permit it.

## Dependencies

* Declare dependencies in `pyproject.toml`, in the dependency group that
matches their use. If the repository is managed with `uv`, manage
dependencies with `uv`.
* When setting up a new Python project, manage it with `uv`.
* Constrain versions to a range: from the oldest version of the currently
compatible release line, up to but excluding the next major version. For
packages still at major version 0, the upper bound is the next minor version.
* Use the same range for a package in every dependency group.
