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

## Repository settings

Change these by hand, in this order:

1. **Before merging the PR that adds this workflow:** Settings → General → Pull Requests → squash merging: default commit message **Pull request title** (`PR_TITLE`) and commit message **Blank** (`BLANK`). This makes the squash commit equal to the PR title.
2. **After that PR merges, before any `feat` or `fix` PR merges:**
   - Settings → Actions → General: allow GitHub Actions to create and approve pull requests. The release PR needs this.
   - A tag ruleset for `*-v*` that restricts updates and deletions. If the ruleset can give GitHub Actions a bypass for creation, restrict creation too.
3. **Don't** enable required status checks on `main`. The release PR is created with `GITHUB_TOKEN`, so PR checks never run on it, and it would be blocked.

## Recovery

- **The workflow failed temporarily** (network, GitHub outage): re-run it. Even if more PRs merged in the meantime, it tags the commit that changed the version, not the latest commit.
- **A release commit set too low a version.** For example, an out-of-date release PR merged after a `feat` landed, or a manual bump was too small. Nothing is tagged and the job fails. The same run regenerates the release PR with the correct version from the latest tag. Merge it, and the job goes green.
- **A bad tag or release needs to go:** delete it by hand with `gh release delete <tag> --cleanup-tag` (the tag ruleset must let you through). Then fix `version` with a PR.
- Reusing a deleted collection's name is unsupported; the release workflow will fail.
