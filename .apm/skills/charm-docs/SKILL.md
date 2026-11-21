---
name: charm-docs
description: >-
  Write or review user documentation for a Juju charm under `docs/`, following
  the Diataxis framework. Use when asked to write, restructure, or review
  charm documentation.
---

Charm documentation describes a stable target. Work against committed
behavior, not changes still in progress. If the documented behavior is not
committed yet, say so before writing.

## Structure

Documentation lives in `docs/`. The top level has an overview page,
`index.md`, that describes the project, the needs it serves, and its primary
users.

The rest follows the Diataxis framework. Every document belongs to exactly one
category; do not mix categories in one document, propose a split instead.

| Category    | Directory           | Purpose                                                  |
| ----------- | ------------------- | -------------------------------------------------------- |
| Tutorial    | `docs/tutorial/`    | A learning experience that walks the user end to end    |
| How-to      | `docs/how-to/`      | Practical directions for a real-world goal or problem    |
| Reference   | `docs/reference/`   | Technical descriptions                                   |
| Explanation | `docs/explanation/` | Context and background for the bigger picture            |

Follow the repository's existing structure where it differs.

## Tutorials

A tutorial usually walks the user through a basic deployment of the charm. It
contains, in order:

* **Title:** what the user will accomplish, more specific than "Getting
started".
* **Introduction:** a couple of sentences on the charm and what the tutorial
does. Focus on what the user will do, not on what they will learn.
* **What you'll do:** a short summary of the steps.
* **What you'll need:** software, tools, supported architectures, and
significant resource requirements. An isolated VM may be suggested.
* **Set up the model:** create a Juju model with a fixed name used throughout.
* **Deploy:** the charm and its dependencies, with any required
configuration. Explain what each additional charm or option is for. Split
commands into separate blocks with explanations between them.
* **Check the deployment:** `juju status`, and `kubectl get pods -n <model>`
where relevant, with example output and how to tell it succeeded.
* **Checkpoint:** a visible result, such as visiting a page, changing a
configuration, or running an action, and how to confirm it worked.
* **Tear down:** destroy the model and any VM created for the tutorial.

## How-to Guides

* The title has the form `# How to ...` and names the goal.
* Include at least one command that achieves the goal.
* Give instructions, not descriptions. Tell the user how, not why not.

## Style

* US English. Sentence case headings without punctuation; do not skip heading
levels or stack headings without text between them.
* No prompt marks (`$`, `#`) and no comments in code examples. Put
explanations in the text, with one command per block where practical.
* Numbered lists only when order matters.
* Avoid Latin words and abbreviations such as "e.g.", "i.e.", "etc.", "via",
and "versus".
* Do not describe tasks as "easy" or "simple".
* Accompany "this", "these", "that", and "those" with a noun when they could
be ambiguous.
* Preserve link targets. When renaming a file, update every relative link to
it.

## Changelog

If `docs/changelog.md` exists, add a short note for every user-facing change,
such as a changed procedure or a new document.
