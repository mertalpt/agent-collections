---
description: "What to document and how, for every durable artifact: code comments, commits, pull requests, issues, decision records, and docs."
applyTo: "**"
---

# Documentation Standards

## Guiding Principles

Document only facts with a high cost of derivation: facts you did not already
know, that took multiple lookups outside the repository or long reasoning to
synthesize. What a little legwork recovers is not written down, and neither is
what something is not, when the correct state is recoverable. A fact also
earns its place by consequence, not only by cost: record it when getting it
wrong breaks something or wastes real time, not when the worst case is
cosmetic or a matter of taste.

Prefer self-documenting code to a comment. Document only what the code cannot
say, and document a quirk once, at the interface that owns it.

Every artifact stands alone: understandable from durable artifacts (committed
files, decision records, issues), never from the process that produced it.
Do not refer to the conversation, review rounds, earlier attempts, or
documents that will not outlive the session. State a why as the mechanism
itself, not the story of discovering it: cut experiential provenance
("confirmed the hard way", "turns out", "we hit this"); keep the fact, drop
the witness. Explain by linking to a durable artifact rather than reproducing
it; naming a path or identifier is fine, but a pasted block of code or output
is not the explanation. An exact identifier or error string may be quoted when
it is itself the fact.

Each fact has one home; the rest link to it. A link may target only a durable
owner of the fact, such as a decision record, a doc, or an upstream identifier
or path, never a peer source file or a symbol defined in one: the fact does
not belong there, and the name rots independently. A pointer to a symbol in
the same file is fine, since the referent travels with it. When a short fact
recurs across structurally identical peers, duplicate it tersely rather than
cross-reference it: duplication is local and honest; cross-file coupling rots.

Prefer ASCII. Pad Markdown table cells so every column aligns in the raw
source, including the delimiter row; a table is read unrendered as often as
rendered.

Do not audit existing code for missing docs unless asked, but document a
hard-won gotcha when you hit one.

## Per-Artifact Rules

* **Code comment:** why this line is as it is, economical, for a competent
reader. Rename before you comment: a better name often removes the need. No
commented-out code, no change history, and no decorative dividers. A
localized detail is a comment; a choice that locks in an architecture is a
decision record.
* **Commit:** what changed, high-level, describing the present state. The
subject follows Conventional Commits, in the imperative, at most 72
characters. The body is optional and absent by default; when present, it is a
few lines of what the subject cannot carry. No rationale, which belongs to the
pull request, no process story, no file-by-file lists, and no test results.
Keep trailers added by tools, such as `Co-Authored-By`, unless the repository
says otherwise.
* **Pull request:** why the change was made, and what is useful to know for
future changes. Use the repository's pull request template when it has one,
and keep its sections.
* **Decision record:** why the system is shaped as it is. The decision body is
immutable. A correction to a still-valid decision is a dated append; a
refinement or reversal is a new record that marks the old one as superseded.
* **Issue:** a problem or goal, not a fix.
* **Prose doc:** opens with a title and a short abstract, in a formal tone.
* **Operational runbook:** its verbatim commands, configuration, paths, and
output are the point; it may relax ASCII and formal tone. The why stays
inline, linking a durable reference when there is one.

Repository conventions for any of these artifacts take precedence.
