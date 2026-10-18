# Contributing

## Setup

Install [pre-commit](https://pre-commit.com/) and PyYAML (`scripts/requirements.txt`), then enable the commit message hook:

```bash
pre-commit install --hook-type commit-msg
```

## Commit messages and PR titles

PRs are squash-merged and the squash commit on `main` is the PR title, so the PR title is what counts. The hook checks local commits for the same format, but only the PR title affects releases.

Format: `<type>[(<scope>)][!]: <subject>`

| Type | Use for | Release effect |
| --- | --- | --- |
| `feat` | New or changed behavior in a collection | minor bump |
| `fix` | Corrected behavior in a collection | patch bump |
| `chore` | Anything outside collection content: CI, scripts, docs, config | none |

- **Type rule:** if a PR changes any file covered by a collection (see below), its type must be `feat` or `fix`. Otherwise it must be `chore`. CI enforces this.
- **Scope** is optional but preferred. Use the primitive's name, e.g. `feat(to-file): …`.
- **Breaking changes** add `!` after the type or scope, e.g. `feat(to-file)!: …`. Only `feat` and `fix` can be breaking.
- **Subjects** are written for whoever installs the collection: say what changed for them, not how it was done. They become release notes as-is.
- Only the subject line is read. Bodies and footers are ignored.

## Collections

A collection lives in `collections/<name>/apm.yml` and pulls primitives from `.apm/` through `git: parent` dependencies.

- The `name` in `apm.yml` must equal the directory name. APM finds a collection's tags (`<name>-v<version>`) from its directory name.
- A collection **covers** its own directory and every `path` of its `git: parent` dependencies. A change to a shared primitive counts for every collection that uses it.
- Adding or removing a primitive edits the collection's `apm.yml`, so it's always covered and needs `feat` or `fix`.
- Deleting a collection is covered too, so it needs `feat` or `fix`. Existing tags stay, so pinned installs keep working. **Never reuse a deleted collection's name**; see [Limitations](docs/releasing.md#limitations).
- A new collection picks its own starting `version`. It's tagged as-is on the first push to `main` after it's merged.

## Releases

Releases are automatic. See [`docs/releasing.md`](docs/releasing.md). Don't change `version` in a PR, except to graduate a collection on purpose (e.g. to `1.0.0`).
