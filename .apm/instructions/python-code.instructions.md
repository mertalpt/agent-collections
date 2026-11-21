---
description: "How to shape data, structure, and document code in Python."
applyTo: "**"
---

# Python Code

## Data

* Use a `dict` for a homogeneous mapping, whose values share one type, such
as `items_by_id: dict[str, Item]`. Use a dataclass for a record whose keys
have different meanings or types.
* Use dataclasses for data that stays inside the application. Use Pydantic
models for data parsed from outside it, such as configuration, files,
network messages, and other processes. Whether other data crosses the
boundary, such as a file the application wrote itself, is the user's
decision.

## Structure

* Keep decisions in a functional core and I/O in an imperative shell. The
core is pure functions that take and return plain values, such as computing
a configuration from inputs. The shell is thin: it gathers inputs, calls the
core, and applies the result, such as writing files or calling services.
Test the core with plain values, without mocks.

## Types

* Annotate function and method signatures and class attributes. Annotate
local variables only where the type checker cannot infer them.

## Docstrings

* Write docstrings in Google style. Where the repository lints with ruff and
does not enforce a docstring convention, propose setting
`[tool.ruff.lint.pydocstyle] convention` to the style the repository uses,
or to `"google"` when it has none.
