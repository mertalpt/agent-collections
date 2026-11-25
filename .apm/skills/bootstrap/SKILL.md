---
name: bootstrap
description: >-
  Use when setting up a new project inside a Workshop created from the
  `workshop` collection's template: the git repository, GitHub
  authentication, git identity, agent collections from
  mertalpt/agent-collections, the decision-record hook, the GitHub
  repository, and the first commit.
---

# Bootstrap

Sets up the project mounted at `/project` inside a Workshop created from a
template in `assets/workshops/`. The host-side steps before this skill,
fetching the template, launching the Workshop, and installing the `workshop`
collection, are in the
[collection's README](https://github.com/mertalpt/agent-collections/tree/main/collections/workshop).

The skill works whether `/project` is empty, a git repository without a
remote, or a clone. It does not install or configure anything that
mertalpt/agent-collections and the template do not provide, such as other
pre-commit hooks or starter files.

## Who runs each step

- **Credentials are the user's.** Logins are interactive and handle secrets,
  so the user runs them as the Workshop's actions from a terminal on the
  host: `workshop run <workshop> -- <action>`, where `<workshop>` is the
  `name` in the project's `.workshop/<name>.yaml`. Tell the user the exact
  command, wait until they say it is done, then check again.
- **Everything else is offered.** Before each step marked "offer", say what
  it will do and run it only if the user accepts. Ask for any input the step
  needs only after they accept. When they decline, tell them how to do it
  themselves and move on.

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

If `/project` is not a git repository, create one on the configured default
branch, or `main`:

```bash
git init -b "$(git config init.defaultBranch || echo main)"
```

### 3. GitHub authentication

If `gh auth status` reports no login to github.com, have the user run the
`gh-auth` action. If gh is logged in but the credential helper for
`https://github.com` does not run `gh auth git-credential`, offer to run
`gh auth setup-git`.

If the token line starts with `github_pat_`, the token is a fine-grained PAT,
which reaches only the repositories it lists. Remember this for step 7.

### 4. Git identity

If `user.name` or `user.email` is not set, offer to set them. If the user
accepts, ask for the missing values and set them with `git config --global`.
If they decline, point them to the `git-identity` action.

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
- Set `canonical_branch` in `intent/config.toml`: `origin/<branch>` when
  that ref exists, otherwise the local branch. Step 7 updates it after the
  first push. The explicit setting also works in CI, where
  `actions/checkout` does not set `origin/HEAD`.
- Offer to run `pre-commit install`. The template provides `pre-commit`.
- Offer to add `assets/ci/decision-records.yaml` from this skill as
  `.github/workflows/decision-records.yaml`, which runs the hook on pull
  requests.

### 7. First commit and GitHub repository

Offer each of these on its own, in the order the user prefers; each one
lists what it needs.

- **First commit.** Show `git status` and ask what to include and for the
  message. When `pre-commit install` has run and the canonical branch has no
  commit yet, commit with `SKIP=intent-decisions`, since the hook cannot
  find a base until then.
- **GitHub repository.** Ask for the owner, name, and visibility, then run
  `gh repo create <owner>/<name> --<visibility> --source . --remote origin`.
  A fine-grained PAT limited to selected repositories cannot create one; if
  creation fails for that reason, explain it and offer to add an existing
  repository as `origin` instead.
- **Remote.** When the user created the repository elsewhere, ask for its
  URL and run `git remote add origin <url>`.
- **Push.** Needs a commit and a remote. With a fine-grained PAT, first ask
  the user to edit it to include the repository, since the push fails
  otherwise. Then run `git push -u origin <branch>` and, with `intent`, set
  `canonical_branch` to `origin/<branch>` and offer to commit that
  change.

### 8. Report

Summarize the state of each step, then list what is left for the user.
