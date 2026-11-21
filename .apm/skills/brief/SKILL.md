---
name: brief
description: >-
  Write a brief so that a fresh session can continue the current work, replay
  it in another repository, or review it. Use when the user asks for a brief,
  a handoff, or a prompt to start a new session.
argument-hint: "What will the next session be used for?"
---

## Motivation

Long sessions accumulate context that a fresh session does not have. A brief
captures what the next session needs so that the user does not have to
redefine the problem for it.

## Workflow

### 1. Determine the purpose

If the user passed arguments, treat them as the purpose of the next session
and tailor the brief to it. Otherwise, the purpose is to continue the current
work.

When the next session will repeat the work in another repository, leave out
what is specific to this repository and add what you wish you had known when
this session started.

### 2. Write the brief

Use the format below. Include only what the next session needs for its
purpose.

* Do not duplicate content already captured in durable artifacts such as
specs, plans, decision records, issues, commits, or diffs. Reference them by
path or URL instead.
* Leave out trial and error. State the conclusions and what was ruled out,
not the path to them.
* Follow the `documentation-standards` and `secrets` instructions.

### 3. Save the brief

Save the brief with the `to-file` skill. The brief is complete once written;
do not present a draft for approval unless the user asks for one.

## Output

```md
# BRIEF - <Title>
_Repository, branch, and commit, if in a Git repository._

## Purpose
_What the next session is for, in one or two sentences._

## Motivation
_Why the work is being done._

## Current State
_What is done, what is in progress, and where things stand._

## Decisions and Constraints
_Decisions made with the user, constraints on the work, and how the user wants
to work, e.g. permissions and review points._

## Learnings
_Gotchas and facts that were costly to establish._

## Next Steps
_Ordered list of what to do next._

## Open Questions
_Questions left for the user or the next session._

## References
_Durable artifacts and files the next session should read._

## Suggested Skills
_Skills the next session should load, and when._
```

For each section, write "None" if there is nothing to include.
