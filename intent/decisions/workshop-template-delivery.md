# Workshop template delivery

Facing APM's inability to deploy files outside agent harness directories, we
ship Workshop templates as files alongside the `bootstrap` skill in the
`workshop` collection, fetched with `curl` from a release tag, rather than as
plain files outside any collection, to keep templates versioned, released,
and pinnable, accepting a fetch step on the host before APM is available.

## Governs

- `.apm/skills/bootstrap/**`
- `collections/workshop/**`

## Context

- Workshop reads a project's definitions from `.workshop/<name>.yaml`. Its
  file format has no include, extend, or remote-template mechanism, and no
  key that runs commands at launch; software gets into a workshop through
  SDKs, whose hooks run while it is set up.
- APM deploys only typed primitives (instructions, prompts, agents, skills,
  commands, hooks, MCP servers) into harness directories such as `.claude/`
  and `.github/`. It deploys a skill's directory with its extra files, but
  cannot place a file in `.workshop/`.
- The `workshop` CLI runs only on the host, so an agent that drives it runs
  on the host too. The point of the template is that no agent does.

## Decision

- Templates live in `assets/workshops/` of the `bootstrap` skill, covered by
  the `workshop` collection, together with `scripts/fetch-workshop.sh`.
- On the host, the user fetches a template with `curl` from a `workshop-v*`
  release tag, never from `main`. The host needs only `curl` and Workshop.
- Software that the template needs and the SDK Store does not provide is
  installed by in-project SDKs in `assets/sdks/`, one `sdk.yaml` and one
  `setup-base` hook each. The fetch script copies every `project-<name>` SDK
  the template lists to `.workshop/<name>/`. The `apm` SDK installs a pinned
  APM release and verifies its checksum; the `pre-commit` SDK installs
  pre-commit from the Ubuntu archive.

## Consequences

- The documented fetch commands, the fetch script's arguments, and existing
  Workshops are an interface: adding a harness or template must keep them
  working.
- Upgrading an in-project SDK in an existing project means replacing its
  directory under `.workshop/` with the one from a newer tag.

## Alternatives

- Plain template files outside any collection, copied by hand: simplest, but
  not versioned, without release notes, and not pinnable.
- The skill in `common`: `common` is meant for any project and targets Claude
  and Copilot, while the template is specific to Claude Code and gh, and every
  template change would release `common`.
- A skill that writes the template without a fetch: the skill is available
  only after APM runs inside a Workshop, which needs the template first.
- Installing APM on the host: adds a host dependency.
- A host script that launches the Workshop and installs APM with
  `workshop exec`: the install is lost on `workshop refresh` and skipped
  when VS Code launches the Workshop, and the definition alone no longer
  reproduces the environment.
- Canonical's `use-workshop-skill` (`onboard-workshop`): it drives the
  `workshop` CLI, so it needs an agent on the host.

## Revisit when

- APM can deploy files to arbitrary project paths, such as `.workshop/`.
- Workshop can include, extend, or fetch definitions from a remote source.
- The Workshop SDK Store offers an SDK for software that an in-project SDK
  installs, such as APM or pre-commit.
