---
name: intent-decisions
description: >-
  Use when adding, changing, or deleting a decision record under `intent/`,
  when finding the records that govern a change, when reconstructing a
  record's history, or when setting up the `intent-decisions` hook in a
  repository.
---

# Intent Decisions

A decision record states the current decision on one topic. It is edited in
place; its changelog indexes the commits that hold its earlier versions. The
`intent-decisions` instruction has the rules for when to read and change
records; this skill has the format, the commands, and the setup.

## Commands

`scripts/adr.py` in this skill's directory needs Python 3.11 or newer and
`git`. Run it from anywhere in the repository; paths are relative to the
working directory. Every command exits with 1 and an explanation when it
fails.

| Command | Does |
| --- | --- |
| `adr.py affected [PATH ...]` | Lists the records whose `Governs` globs match the paths, or the files changed since the base when no path is given. |
| `adr.py row RECORD --summary TEXT` | Writes this change set's changelog row, or replaces it when the change set already has one. |
| `adr.py check` | Checks every record against the base of the change set. The pre-commit hook runs it. |
| `adr.py audit` | Checks every committed record's changelog against the record's whole first-parent history at `HEAD`. Not part of the hook. |

The base is `git merge-base HEAD <canonical branch>`. A change set is
everything between the base and `HEAD`, working tree included.

## Template

```markdown
# <Topic>

Facing <concern>, we <decision> rather than <alternative>, to achieve
<quality>, accepting <downside>.

## Governs

- `<glob>`

## Context

<The forces and constraints that hold now.>

## Decision

<What we do, specific enough to check a change against.>

## Consequences

<What becomes easier, harder, or required.>

## Alternatives

<Rejected options that are still tempting, and why each was rejected.>

## Revisit when

<Conditions that would invalidate this decision.>
```

Name the file after the topic, such as `packaging.md`.

## Format

`adr.py` reads only `## Governs` and `## Changelog`; the other sections are
for readers.

* **Governs:** one or more lines of the form ``- `glob` ``, nothing else. A
glob is a path from the repository root: `*` and `?` match within one path
segment, and a `**` segment matches any number of segments. Use `**` for a
decision that applies everywhere. Each glob must match at least one file.
* **Changelog:** absent until the first change to a record. Then it goes at
the end of the record and holds exactly this table, newest row first:

  ```markdown
  ## Changelog

  | Previous version | Change |
  | --- | --- |
  | <full commit hash> | <one-line summary> |
  ```

  A row's hash is the commit that holds the record as it was before the
  change. Write rows with `adr.py row` only.
* **References:** `check` fails when a file refers to a record that does not
exist. A reference is a path ending in `.md` that resolves, relative to the
referring file or to the repository root, to a file in the decisions
directory. In Markdown files, text inside inline code and fenced code blocks
does not count, so write example paths as code and real references as links
or plain text. In other files, such as source code, every path counts. A
record's own changelog does not count, so its summaries may name deleted
records.

## Procedures

**Add a record:** write it from the template, without a changelog, under a
slug that was never used. Run `adr.py check`.

**Change a record:** edit it, then run `adr.py row RECORD --summary TEXT`.
If you edit it again before the change set lands, rerun `row` with a summary
that covers the whole change. The summary says what changed and why, in one
line, so a reader can skip trivial rows when reconstructing history. Run
`adr.py check`.

**Delete a record:** find what refers to it, such as links, code comments,
and other records, and update those. Delete the file. Run `adr.py check`,
which fails on references that still point to it, as described under
**References**.

**Rename a topic:** delete the record and add one under a new slug. Renames
are not supported because git cannot follow them reliably.

**Reconstruct history:** read the changelog from the top. For each row of
interest, `git show <hash>:<record path>` prints the version the row's change
replaced. For a deleted record, `git log -1 --format=%H -- <record path>`
finds the commit that deleted it, and `git show <commit>^:<record path>`
prints its last version.

## Configuration

The config file is `intent/config.toml`, or the path in the `INTENT_CONFIG`
environment variable, relative to the repository root. It is optional:

```toml
# The ref where change sets become final. Default: the branch origin/HEAD
# points to.
canonical_branch = "origin/develop"

[decisions]
# Default: intent/decisions
path = "intent/decisions"
```

`check` fails when the decisions directory holds no records, so a missing or
wrong `INTENT_CONFIG` fails instead of checking nothing. Choose the location
before adding records: `check` rejects moving it while it holds records.

## Setting up a repository

1. Add the hook to `.pre-commit-config.yaml`, with `rev` set to the `intent`
   collection's release tag, such as `intent-v0.1.0`:

   ```yaml
   - repo: https://github.com/mertalpt/agent-collections
     rev: intent-v<version>
     hooks:
       - id: intent-decisions
   ```

2. Make sure the canonical branch is known locally: `git remote set-head
   origin --auto`, or set `canonical_branch`.
3. In CI, check out the full history and the canonical branch, such as with
   `fetch-depth: 0` for `actions/checkout`, and run the hook against the pull
   request. CI is where the check cannot be skipped with `--no-verify`.
4. Optionally, run `adr.py audit` in a CI job on the canonical branch, such
   as after each push, to find rows that bypassed the check.
5. Add the first record.

## Limits

* Rewriting the canonical branch's history invalidates the hashes in every
changelog.
* A record changed outside a change set that targets the canonical branch,
such as on a gitflow hotfix branch or by a direct push, is not checked, and
its row may be wrong. `check` only compares a change set with its base, so
it does not catch such a row later; `audit` does, but only when someone runs
it.
* A wrong row cannot be repaired without bypassing the hook, because `check`
rejects changes to rows below the newest.
* `INTENT_CONFIG` is not versioned. Every environment that runs the hook
must set it the same way.
* `check` does not catch a reference to a missing record written as code in
a Markdown file, nor prose that relies on an old decision without naming the
record's path.
