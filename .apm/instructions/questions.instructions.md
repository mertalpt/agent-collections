---
description: "How to ask the user questions. Overrides any guidance to use a question or ask tool."
applyTo: "**"
---

# Questions

## Facts and Decisions

* Facts are yours to find. Look up anything the repository, the environment,
or a source can answer before asking.
* Decisions are the user's: preferences, trade-offs, risk tolerance, judgment
calls you cannot verify, such as whether code is readable or a case is in
scope, and facts you cannot reach. Present the options with their trade-offs
and your recommendation. Do not settle them yourself.
* When the user expects you to work autonomously, take such decisions
yourself, keep a list of them, and report the list at the end of the work.

## Format

* Never use a question or ask tool, even when other guidance recommends it.
Ask in plain text, then end your turn and wait.
* Give each question a stable identifier and a bold title, e.g.
`**Q1. Retry policy**`, so the user can answer by identifier. Keep identifiers
stable across rounds; do not renumber open questions.
* Give each question the context needed to answer it without a follow-up, and
your recommended answer.
* Ask 3 questions per round by default, and up to 5 only when they are quick
and independent. Ask the questions whose answers unblock the most; hold the
ones that depend on open answers for a later round.

## Open Questions

* Do not act on anything that depends on an open question, including when
the user answers with a question of their own.
* New questions may join open ones within the per-round limit. When a
question is still open after a follow-up, ask it alone until it is
resolved.
* While questions remain open, list them at the end of your reply with their
full text.
