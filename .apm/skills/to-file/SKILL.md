---
name: to-file
description: >-
  Use when the user or a workflow wants to save a durable session artifact,
  such as a plan, specification, task, or handoff, that must outlive the
  session but does not belong in the repository.
---

## Motivation

Many sessions produce artifacts such as plans, specifications, and handoffs
that do not belong in the repository but need to be shared across sessions.
The purpose of this skill is to save them into standardized locations on the
file system.

## Workflow

### 1. Identify the artifact

If you are following a workflow that instructs you to save its deliverable,
that deliverable is the artifact. Otherwise, infer the artifact from the
request that invoked this skill and the recent conversation.

Stop and ask the user if:

- More than one artifact plausibly matches the request.
- The artifact has not reached the completion or approval point defined by
  the instructions that produced it. Offer to save the latest draft.
- The artifact is no longer available verbatim, e.g. only a summary of it
  survives in context. Do not reconstruct it.

### 2. Extract file contents

Save the artifact verbatim, in its final form:

- If the instructions that produced it define an output format, the format
  defines its boundaries. Include every section the format requires, even
  ones that read "None".
- If those instructions define a completion or approval point, save the
  latest version that reached it. Never save a version the user rejected.
- If the artifact was revised in later turns without being re-presented in
  full, apply every accepted revision and tell the user you did so.
- Exclude everything outside the artifact: preambles, status updates,
  questions, review prompts, tool output.
- Remove a code fence that wraps the whole artifact; keep inner fences.
- Do not reword, summarize, or fix the content.

### 3. Prepare file location

Files are placed in a common location in the user's home directory,
parametrized by the name of the working directory:
`~/.agent-artifacts/<working-dir-name>`. For example, if you are on
`~/workspaces/foo/bar`, the location is `~/.agent-artifacts/bar`.

Run the following to create the location and print its absolute path and the
next file number:

```bash
dir="$HOME/.agent-artifacts/$(basename "$PWD")"
mkdir -p "$dir"
last=$(ls "$dir" | grep -oE '^[0-9]+' | sort -n | tail -n 1)
printf '%s\n%04d\n' "$dir" $((10#${last:-0} + 1))
```

Numbers start at `0001` and increment from the highest existing number. When
the four digits are exhausted, the digit count grows, e.g. `10000` follows
`9999`.

### 4. Write the file

Write the contents to `<dir>/<number>-<descriptive-slug>.md`, using the
absolute path printed in the previous step. Do not use `~` in the path.

The descriptive slug is a few lowercase, hyphenated words that hint at the
contents of the file. It does not have to be a full title.

### 5. Report

Return to the user a report in the following format:

```md
Path: <file-path>
Contents:
<first five lines of the file>
...
<last five lines of the file>
```

Write the path in `~/...` form, e.g.
`~/.agent-artifacts/bar/0001-auth-tasks.md`. If the file has ten lines or
fewer, show the whole file instead.
