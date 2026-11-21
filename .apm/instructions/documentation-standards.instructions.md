---
description: "What to document and how, for every artifact that outlives the session: code comments, commits, pull requests, issues, decision records, docs, and saved session artifacts."
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

Every artifact stands alone: its readers understand it from what they can
follow, never from the process that produced it. A reference is followable
when every reader of the artifact can reach its target for as long as the
artifact is in use:

* **Reach:** an artifact's readers are those who can reach the place that
holds it. Refer only to targets those readers can reach. A repository's
files, commits, and pull requests may refer to the repository, its tracker,
and public sources, but not to local files or a private artifact store.
When you cannot tell whether the readers can reach a target, ask.
* **Lifetime:** durable artifacts last as long as the place that holds
them, such as committed files, decision records, issues, and pull requests.
Semi-durable artifacts outlive the session but may be removed, such as
files saved with the `to-file` skill. Ephemeral artifacts may not outlive
the session, such as the conversation, review rounds, earlier attempts, and
temporary files. Refer only to targets that live at least as long as the
artifact, except as follows.

An artifact may refer to a shorter-lived target, such as a log dump under
`/tmp` or a CI run whose logs expire, when it says the target may be gone and
states the facts it needs from it, such as the error line.

State a why as the mechanism itself, not the story of discovering it: cut
experiential provenance ("confirmed the hard way", "turns out", "we hit
this"); keep the fact, drop the witness. Explain by linking to the fact's
owner rather than reproducing it; naming a path or identifier is fine, but a
pasted block of code or output is not the explanation. An exact identifier or
error string may be quoted when it is itself the fact.

Each fact has one home; the rest link to it. A link may target only an owner
of the fact that is followable as described above, such as a decision record,
a doc, or an upstream identifier or path, never a peer source file or a symbol
defined in one: the fact does not belong there, and the name rots
independently. A pointer to a symbol in the same file is fine, since the
referent travels with it. When a short fact recurs across structurally
identical peers, duplicate it tersely rather than cross-reference it:
duplication is local and honest; cross-file coupling rots.

Prefer ASCII.

Do not audit existing code for missing docs unless asked, but document a
hard-won gotcha when you hit one in code the task changes; otherwise,
propose it.

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
* **Template:** write each section for the reader it addresses, as its
heading and guidance define it. A "Test instructions" section tells a
reviewer how to test the change; it is not a report of how you tested it.
When a section's purpose is unclear, it is the user's decision.
* **Agent instruction:** state each rule with its scope and its reason, so
an agent can tell where it holds. A rule without either reads as universal.
* **Decision record:** why the system is shaped as it is. The decision body is
immutable. A correction to a still-valid decision is a dated append; a
refinement or reversal is a new record that marks the old one as superseded.
* **Issue:** a problem or goal, not a fix.
* **Prose doc:** opens with a title and a short abstract, in a formal tone.
* **Operational runbook:** its verbatim commands, configuration, paths, and
output are the point; it may relax ASCII and formal tone. The why stays
inline, linking a durable reference when there is one.
