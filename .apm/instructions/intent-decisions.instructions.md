---
description: "Keep mutable decision records under `intent/` current, with one checked changelog row per change set."
applyTo: "**"
---

# Intent Decisions

These rules apply in repositories that run the `intent-decisions` pre-commit
hook, listed in `.pre-commit-config.yaml`. There, a decision record is
mutable: it states the current decision on one topic, and git keeps its
earlier versions. The `intent-decisions` skill has the template, the file
format, and the `adr.py` commands named below.

* One record per topic, named by a topic slug, in the decisions directory
(`intent/decisions/` unless the config file says otherwise). A reader then
finds the current decision in one place instead of following a chain of
superseded records.
* Before changing files, run `adr.py affected` and read the records it lists.
When the change meets a record's "Revisit when" conditions or contradicts its
decision, propose updating the record in the same change set. Changing a
decision is the user's decision.
* Add a changelog row with `adr.py row` for every change to an existing
record, trivial ones included, and rerun it to replace the summary when the
record changes again in the same change set. Do not write rows by hand: the
row's hash must be the commit that holds the previous version, which only
the tool computes reliably.
* Delete a record that no longer applies instead of marking it obsolete; its
history stays in git. To rename a topic, delete the record and create one
under a new slug. Never reuse a slug, deleted or not: old references would
resolve to a different topic.
* Before deleting a record or changing its decision, find what refers to it
and update it. `adr.py check` catches paths to missing records, but not
paths written as code in Markdown, which it treats as examples, nor prose
that relies on the old decision.
* Keep rejected alternatives in a record while they are still tempting, so no
one proposes them again without knowing why they were rejected.
* Change records only in change sets that target the canonical branch. A
change that reaches it through another long-lived branch, such as a gitflow
hotfix, can get a changelog row that points at the wrong commit. Only
`adr.py audit` finds it later, and fixing it means bypassing the hook.
