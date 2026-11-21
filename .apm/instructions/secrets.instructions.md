---
description: "Keep secrets and internal details out of context, output, and external services."
applyTo: "**"
---

# Secrets

When the user or the environment's instructions state that an environment
is local and disposable, its own secrets, such as generated test
passwords, are exempt from the first two rules. The other rules still
apply: files and commits outlive the environment.

* Do not read or print secret values, such as tokens, passwords, private keys,
and credential files. Redact any that appear in output you show.
* Never ask the user to paste a secret into the conversation. If a task needs
one, ask the user to make it available to the tool that needs it.
* Do not write secrets into code, configuration, commits, or logs.
* Do not send internal names, such as private project, team, or host names,
to external services, including web searches.
* Keep host names, IP addresses, and paths that identify a machine out of
anything posted publicly. Describe the result instead.
