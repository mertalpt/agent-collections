# agent-collections

This repository contains my collections for agent customizations based on [APM](https://microsoft.github.io/apm/) conventions.

## Repository Structure

| Directory | Description |
| --- | --- |
| `.apm/` | Holds customization files based on APM conventions. |
| `.claude/`| Holds Claude Code configurations used to develop the repository. |
| `.github/` | Hold GitHub configurations. |
| `.workshop/` | Holds [Workshop](https://ubuntu.com/workshop) files used to sandbox agents used to develop the repository. |
| `collections/` | Holds "virtual" APM packages built from grouping base files in `.apm/`. |
| `docs/` | Holds documentation for the repository. |
| `scripts/` | Holds scripts used to manage the repository itself. |


## Installing a Collection

Install a released collection by its tag:

```bash
apm install mertalpt/agent-collections/collections/<name>#<name>-vX.Y.Z
```

Check for newer releases with `apm outdated`. Release notes are on the [GitHub Releases](https://github.com/mertalpt/agent-collections/releases) page.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for commit conventions and [`docs/releasing.md`](docs/releasing.md) for how releases work.
