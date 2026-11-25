# workshop

A [Workshop](https://ubuntu.com/workshop/docs/) template that sandboxes Claude Code with the GitHub CLI and the APM CLI, and a `bootstrap` skill that sets up a new project inside it. The host needs only `curl` and Workshop; APM is installed and run inside the Workshop.

## Setting up a project

### 1. Fetch the template

In the project directory on the host, which may be empty:

```bash
tag=$(curl -fsSL https://api.github.com/repos/mertalpt/agent-collections/git/matching-refs/tags/workshop-v \
  | grep -o '"refs/tags/workshop-v[^"]*"' | tr -d '"' | sed 's|refs/tags/||' | sort -V | tail -n 1)
curl -fsSL "https://raw.githubusercontent.com/mertalpt/agent-collections/$tag/.apm/skills/bootstrap/scripts/fetch-workshop.sh" \
  | sh -s -- "$tag" claude-code
```

The first command finds the latest `workshop-v*` release tag; to pin an older one, set `tag` yourself. The script creates `.workshop/<directory name>.yaml` and the in-project SDK `.workshop/apm/`, which installs the APM CLI. The directory name must be a valid workshop name: a lowercase letter, then lowercase letters and digits with single hyphens between them, up to 40 characters. The script refuses to overwrite existing files.

### 2. Launch and enter the Workshop

From a terminal:

```bash
workshop launch
workshop run -- claude-auth
workshop shell
```

From VS Code on the same Linux machine, install the [Workshop extension](https://ubuntu.com/workshop/docs/how-to/develop-with-workshops/connect-vscode/) and use **Reopen in Workshop**. The window opens `/project` inside the Workshop, and GitHub Copilot works in it. VS Code connected through Remote-SSH to another machine that runs Workshop is unsupported; see [canonical/vscode-workshop#49](https://github.com/canonical/vscode-workshop/issues/49).

### 3. Install this collection

Inside the Workshop, in `/project`:

```bash
apm install --target claude "mertalpt/agent-collections/collections/workshop#$tag"
```

Use the same tag as in step 1. `--target claude` records the harness in `apm.yml`, since an empty project has nothing APM can detect it from.

### 4. Run the skill

Start Claude Code with `claude`, or with the `claude-skip-permissions` action from the host, and run `/bootstrap`. It sets up the git repository, GitHub authentication, git identity, and the collections you choose, and tells you which Workshop actions to run when it needs you.

Commit `.workshop/`, `apm.yml`, and `apm.lock.yaml` with the project.

## Actions

Run an action from the host with `workshop run -- <action>`.

| Action | Does |
| --- | --- |
| `status` | Shows the GitHub, Claude, git identity, and APM status, and whether `/project` is empty, a repository without a remote, or a clone. |
| `gh-auth` | Logs in to GitHub and sets up git to use the login. |
| `git-identity` | Prompts for the git `user.name` and `user.email`. |
| `claude-auth` | Logs in to Claude. |
| `claude-skip-permissions` | Starts Claude Code with `--dangerously-skip-permissions`. |
