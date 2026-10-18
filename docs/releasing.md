# Releasing

Each collection is versioned and tagged independently. Tags are `<name>-v<version>`, e.g. `common-v0.2.0`. The work is done by [`.github/workflows/release.yaml`](../.github/workflows/release.yaml) running [`scripts/release.py`](../scripts/release.py) on every push to `main`.

## How a release happens

1. Merge `feat` and `fix` PRs as usual.
2. After each merge, the workflow works out every collection's next version from the commits since its latest tag that touch its coverage:

   | Commits | Version `0.x.y` | Version `>= 1.0.0` |
   | --- | --- | --- |
   | any `feat!` / `fix!` | minor | major |
   | any `feat` | minor | minor |
   | any `fix` | patch | patch |
   | `chore` only | no release | no release |

   It then opens or updates one release PR from the `release/pending` branch, titled `chore(release): <name> <version>[, …]`. The PR only changes `version` lines, and its body previews the release notes. If nothing is pending, it closes the release PR.
3. Merge the release PR when you want to release. The workflow tags the commit that changed each version and publishes a GitHub Release with the notes.

A new collection is tagged with its current version on the first push to `main` that contains it, with the notes "Initial release."

`0.x` versions never reach `1.0.0` on their own.

## Graduating a collection (manual version bump)

Open a normal PR that sets `version` in the collection's `apm.yml`, e.g. `feat!: declare common stable` with `version: 1.0.0`. When it merges, the workflow tags it. The version must be at least what the commits since the latest tag require.

## Recovery

- **The workflow failed temporarily** (network, GitHub outage): re-run it. Even if more PRs merged in the meantime, it tags the commit that changed the version, not the latest commit.
- **A release commit set too low a version.** For example, an out-of-date release PR merged after a `feat` landed, or a manual bump was too small. Nothing is tagged and the job fails. The same run regenerates the release PR with the correct version from the latest tag. Merge it, and the job goes green.
- **A bad tag or release needs to go:** delete it by hand with `gh release delete <tag> --cleanup-tag`. Then fix `version` with a PR.
- **The workflow fails for a collection whose name was used before:** see [Limitations](#limitations).

## Limitations

### Don't reuse a deleted collection's name

> [!WARNING]
> Reusing a deleted collection's name is unsupported; the release workflow will fail or never release it.

Tags outlive the collections they belong to, so a new collection with an old name inherits the old `<name>-v*` tags. Depending on its `version` compared with the latest old tag:

- **Higher:** the workflow finds no commit that released it and fails with "no commit after … changes the version".
- **Lower:** it fails with "version … is lower than the latest tag".
- **Equal:** it's treated as already released and never tagged; the old tag points at the old collection's content.

Pick a new name instead.
