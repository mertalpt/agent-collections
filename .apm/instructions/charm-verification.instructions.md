---
description: "When integration tests may run in Juju charm repositories."
applyTo: "**"
---

# Charm Verification

Before committing, run the non-integration checks as described in the
`python-tooling` instruction.

When the work has a planning step and the rules below leave the integration
test strategy unclear, agree on it there: which modules to run, and whether
to run them locally or only in CI.

Integration tests deploy real applications and take a long time:

* Do not run integration tests unless the user explicitly requests or permits
it, or delegates a long-running implementation task.
* For a delegated long-running task, run only the integration modules
relevant to the changed behavior. Rely on CI for the full suite.
* Run the full suite locally only when the user explicitly requests it or
grants several hours of unattended autonomy.
* Whenever integration tests are permitted, follow the
`run-integration-tests` skill.
