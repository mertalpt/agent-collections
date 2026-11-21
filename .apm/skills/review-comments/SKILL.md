---
name: review-comments
description: >-
  Process the review comments on a pull request: give each a stable
  identifier, assess it according to its Conventional Comments label, and
  discuss the comments with the user in small batches. Use when the user asks
  to go through, process, assess, or answer review comments.
argument-hint: "Pull request URL or number"
---

## Motivation

Review comments mix change requests, questions, and passing thoughts. Handling
each comment by type, in a fixed template, with an identifier the user can
answer by, keeps a long review consistent across several rounds of discussion.

## Workflow

### 1. Collect the comments

Fetch every comment on the pull request: review bodies, top-level comments,
and inline threads. Leave out resolved threads unless the user asks for them.
If the pull request cannot be reached, work from comments the user pastes.

Save the comments to a temporary file and work from that file. Group related
comments: comments that share a topic, a root cause, or a likely fix, even
across files. Put groups that others depend on first; otherwise order them
by the location of their first comment. Order the comments within a group by
file and line. Assign `R1`, `R2`, ... in
that order, one identifier per thread. Record each comment's identifier,
group, location, link, and status alongside it.

Identifiers are stable. Never renumber them. When new comments arrive during
the discussion, append them to the file with the next numbers and assign each
to a group.

### 2. Classify

Read each comment's label and decorations as defined by
[Conventional Comments](https://conventionalcomments.org/):
`<label> [(decorations)]: <subject>`. Accept common abbreviations, such as `q`
for `question`. If a comment has no label, infer one and mark it as inferred.

A question can be a challenge in disguise. For example, "Is this warranted?"
needs both an answer and a verdict on whether the code should change.

### 3. Assess

Before assessing a comment, read the code it points at, at the revision the
comment was made on, and note whether that code has changed since. Answer
with evidence from the repository or a source, not from the comment alone.

When a fix has more than one reasonable option, it is a decision. Follow the
`questions` instruction.

### 4. Discuss in batches

Present 3 to 5 comments per batch, in identifier order, using the template
below. Keep a group in one batch where it fits, and split a group that is too
large. When the comments in a group share a fix, propose it once and
reference it from the others. Update each comment's status in the file as the
user answers: `open`, `agreed`, `applied`, or `dropped`.

Do not post replies, resolve threads, or apply fixes unless the user asks.

## Output

```md
### R<n>. <Short title>: `<label>` (<decorations>) · <status>
_<path:line, or "review" or "top-level"> · <link> · related: R4, R9_

**Summary:** <what the comment says or asks>
<fields for the label>

> **R<n>:** <question for the user, if any>
```

Fields that follow the summary, by label:

* `issue`, `suggestion`, `polish`, `todo`, `chore`, `nitpick`, `quibble`,
`typo`: **Validity**, **Feasibility**, **Proposed fix**.
* `question`: **Answer**, **Implication** (none, or the proposed fix).
* `thought`, `note`: **Response**, and a **Proposal** if there is one.
* `praise`: none.

Write an inferred label as `` `<label>` (inferred) ``. Leave out the
decorations when there are none, and "related" when the comment has no
related comments.
