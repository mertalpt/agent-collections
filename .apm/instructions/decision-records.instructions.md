---
description: "Read and follow the decision records a repository keeps before changing what they govern."
applyTo: "**"
---

# Decision Records

These rules apply in repositories that keep decision records, such as
architecture decision records (ADRs), in any format or location. Find them
through the contributor docs, or in conventional locations such as
`intent/decisions/`, `docs/adr/`, `docs/decisions/`, or `doc/adr/`.

* Before changing something, read the decision records that govern it. A
record states constraints the code does not show, so a change that breaks one
can look correct on its own.
* Follow them. When a change would contradict a record, or a record no longer
matches the code, stop and raise it instead of working around it: whether the
decision or the change gives way is the user's decision.
* Add, change, or remove records only as the repository's convention
describes, in its contributor docs, instructions, or the tooling that checks
them. Conventions differ, such as whether a record may be edited after it is
accepted, and breaking one corrupts the project's record of why.
