---
name: bootstrap
description: >-
  Use when setting up a new project inside a Workshop created from the
  `workshop` collection's template: the git repository, GitHub
  authentication, git identity, agent collections from
  mertalpt/agent-collections, and the decision-record hook.
---

# Bootstrap

Sets up the project mounted at `/project` inside a Workshop created from a
template in `assets/workshops/`. The host-side steps before this skill,
fetching the template, launching the Workshop, and installing the `workshop`
collection, are in the
[collection's README](https://github.com/mertalpt/agent-collections/tree/main/collections/workshop).

The skill works whether `/project` is empty, a git repository without a
remote, or a clone. It does not create a GitHub repository, add a remote,
commit, or install or configure anything that mertalpt/agent-collections
does not provide, such as other pre-commit hooks or starter files. Those
choices are the user's.

## Steps that need the user

Logins and identity prompts are interactive, so the user runs them as the
Workshop's actions from a terminal on the host:

```bash
workshop run <workshop> -- <action>
```

`<workshop>` is the `name` in the project's `.workshop/<name>.yaml`. Tell the
user the exact command, wait until they say it is done, then check again. If
the check still fails, show what failed and ask them to retry.

## Workflow

### 1. Inspect

Record the project's state; later steps depend on it:

```bash
cd /project
ls -A
git rev-parse --git-dir && git remote -v && git symbolic-ref --short HEAD
gh auth status
git config --global --get-all credential.https://github.com.helper
git config --global user.name; git config --global user.email
cat apm.yml
```

`gh auth status` masks the token; never pass `--show-token`.

### 2. Git repository

If `/project` is not a git repository, run `git init` and note the branch it
created.

### 3. GitHub authentication

Done when `gh auth status` reports a login to github.com and the credential
helper for `https://github.com` runs `gh auth git-credential`. Otherwise,
have the user run the `gh-auth` action.

If the token line starts with `github_pat_` and the repository has no remote,
tell the user that a fine-grained PAT reaches only the repositories it lists:
once they create the repository, they must edit the PAT to include it.

### 4. Git identity

Done when `user.name` and `user.email` are both set. Otherwise, have the user
run the `git-identity` action.

### 5. Collections

Install `common`, and ask the user which of these to add:

- `intent`: decision records under `intent/`, checked by a pre-commit hook.
- `python`: instructions for Python projects.
- `juju`: instructions and skills for Juju charm development; expects
  `python`.

`apm.yml` must list the harness you run in under `targets`, such as `claude`
for Claude Code; add it if it is missing. Skip collections already in
`apm.yml`. Install each one from its latest release tag:

```bash
tag=$(git ls-remote --tags --refs https://github.com/mertalpt/agent-collections "refs/tags/<name>-v*" \
  | sed 's|.*refs/tags/||' | sort -V | tail -n 1)
apm install "mertalpt/agent-collections/collections/<name>#$tag"
```

### 6. Decision records

Only when `intent` is installed. Follow "Setting up a repository" in the
`intent-decisions` skill, which the `intent` collection installs, with these
choices:

- Set the hook's `rev` to the installed `intent` tag. Create
  `.pre-commit-config.yaml` if it does not exist; otherwise add the entry and
  leave the others alone.
- Create the decisions directory with a `.gitkeep`.
- Canonical branch: if `origin` exists and has a default branch, run
  `git remote set-head origin --auto`. Otherwise, set `canonical_branch` to
  the local branch in `intent/config.toml`, and tell the user to remove it
  and run `git remote set-head origin --auto` once they push to a remote.
- Do not run `pre-commit install` or commit. Tell the user how to make the
  first commit: commit first, then run `pre-commit install`, or commit with
  `SKIP=intent-decisions`. If `pre-commit` is not installed, say that the
  hook needs it; the template does not provide it.
- Tell the user that the CI step of that section is theirs to add.

### 7. Report

Summarize the state of each step, then list what is left for the user, such
as creating the GitHub repository, adding the remote, editing the PAT, the
first commit, and CI for the decision-record hook.
