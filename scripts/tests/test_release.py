"""Tests for scripts/release.py."""

import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import release  # noqa: E402
from release import Commit  # noqa: E402


def apm_yml(name: str, version: str, paths: list[str]) -> str:
    """Builds a collection's `apm.yml`.

    The version line has trailing spaces and is followed by a comment, so tests
    also cover that version edits keep the rest of the file intact.

    Args:
        name: The collection name.
        version: The collection version.
        paths: The `git: parent` dependency paths.

    Returns:
        The file content.
    """
    deps = "".join(f"  - git: parent\n    path: {p}\n" for p in paths)
    return (
        f"name: {name}\n"
        f"version: {version}  \n"
        f"# A comment that must survive version edits.\n"
        f"dependencies:\n  apm:\n{deps}  mcp: []\n"
    )


class TempRepo:
    """A throwaway git repository with a bare `origin` to push to."""

    def __init__(self, test: unittest.TestCase):
        """Creates the repositories and removes them when `test` finishes.

        Args:
            test: The test case that owns the repository.
        """
        tmp = tempfile.TemporaryDirectory()
        test.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, "work")
        origin = os.path.join(tmp.name, "origin.git")
        subprocess.run(["git", "init", "-q", "--bare", origin], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", self.path], check=True)
        self.git = release.Git(self.path)
        self.git.run("config", "user.name", "Test")
        self.git.run("config", "user.email", "test@example.com")
        self.git.run("config", "commit.gpgsign", "false")
        self.git.run("config", "tag.gpgsign", "false")
        self.git.run("remote", "add", "origin", origin)

    def write(self, path: str, content: str) -> "TempRepo":
        """Writes a file in the working tree.

        Args:
            path: The repository path.
            content: The file content.

        Returns:
            This repository, for chaining.
        """
        full = os.path.join(self.path, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return self

    def commit(self, subject: str) -> str:
        """Commits every change in the working tree.

        Args:
            subject: The commit subject.

        Returns:
            The new commit's SHA.
        """
        self.git.run("add", "-A")
        self.git.run("commit", "-q", "-m", subject)
        return self.git.rev_parse("HEAD")

    def tag(self, tag: str) -> None:
        """Creates an annotated tag at `HEAD`."""
        self.git.create_tag(tag, "HEAD", tag)

    def tag_commit(self, tag: str) -> str:
        """Returns the SHA of the commit `tag` points to."""
        return self.git.rev_parse(tag)

    def set_common_version(self, version: str, subject: str) -> str:
        """Commits a new version for the `common` collection.

        Args:
            version: The new version.
            subject: The commit subject.

        Returns:
            The new commit's SHA.
        """
        with open(os.path.join(self.path, "collections/common/apm.yml"), encoding="utf-8") as f:
            text = f.read()
        return self.write("collections/common/apm.yml", release.set_version(text, version)).commit(subject)


class FakeGitHub:
    """Stands in for `release.GitHub`, keeping open PRs and published releases in memory.

    Attributes:
        prs: Open PRs as `{number, title, body}`, by head branch.
        releases: Release notes by tag.
        next_number: The number the next PR gets.
    """

    def __init__(self):
        """Starts with no PRs and no releases."""
        self.prs = {}
        self.releases = {}
        self.next_number = 1

    @property
    def pr(self):
        """The open release PR, or None."""
        return self.prs.get(release.RELEASE_BRANCH)

    def repo(self):
        """Returns the repository as `owner/name`."""
        return "owner/repo"

    def find_pr(self, branch):
        """Returns the number of the open PR from `branch`, if any."""
        pr = self.prs.get(branch)
        return pr["number"] if pr else None

    def create_pr(self, branch, title, body):
        """Opens a PR from `branch`."""
        self.prs[branch] = {"number": self.next_number, "title": title, "body": body}
        self.next_number += 1

    def edit_pr(self, number, title, body):
        """Replaces a PR's title and body."""
        branch = next(b for b, pr in self.prs.items() if pr["number"] == number)
        self.prs[branch] = {"number": number, "title": title, "body": body}

    def close_pr(self, number, comment):
        """Closes a PR."""
        self.prs = {b: pr for b, pr in self.prs.items() if pr["number"] != number}

    def create_release(self, tag, notes):
        """Records a published release."""
        self.releases[tag] = notes


def common_repo(test: unittest.TestCase) -> TempRepo:
    """Creates a repository with an untagged `common` collection at 0.1.0.

    `common` covers `.apm/skills/to-file` and `.apm/agents/product-owner.agent.md`;
    `.github/pull_request_template.md` is not covered.

    Args:
        test: The test case that owns the repository.

    Returns:
        The repository.
    """
    repo = TempRepo(test)
    repo.write(".apm/skills/to-file/SKILL.md", "to-file\n")
    repo.write(".apm/agents/product-owner.agent.md", "po\n")
    repo.write(".github/pull_request_template.md", "template\n")
    repo.write(
        "collections/common/apm.yml",
        apm_yml("common", "0.1.0", [".apm/skills/to-file", ".apm/agents/product-owner.agent.md"]),
    )
    repo.commit("feat: add common")
    return repo


class ParseSubjectTest(unittest.TestCase):
    """Tests for `parse_subject`."""

    def test_parses_valid_and_rejects_unknown_types_and_breaking_chore(self):
        """A full subject is parsed; unknown types and `chore!` are rejected."""
        self.assertEqual(
            release.parse_subject("feat(to-file)!: x (#21)"),
            Commit("feat", "to-file", True, "x", 21),
        )
        self.assertIsNone(release.parse_subject("chore!: x"))
        self.assertIsNone(release.parse_subject("docs: x"))


class CheckPrTest(unittest.TestCase):
    """Tests for the type rule in `check_pr`."""

    def test_covered_change_requires_feat_or_fix(self):
        """A PR changing a covered primitive can't be a chore."""
        # GIVEN a PR that changes a skill covered by `common`.
        repo = common_repo(self)
        base = repo.git.rev_parse("HEAD")
        head = repo.write(".apm/skills/to-file/SKILL.md", "changed\n").commit("wip")

        # WHEN/THEN a chore title fails and a fix title passes.
        self.assertTrue(release.check_pr(repo.git, base, head, "chore: update skill"))
        self.assertEqual(release.check_pr(repo.git, base, head, "fix: update skill"), [])

    def test_uncovered_change_requires_chore(self):
        """A PR changing only uncovered files must be a chore."""
        # GIVEN a PR that changes only `.github/`.
        repo = common_repo(self)
        base = repo.git.rev_parse("HEAD")
        head = repo.write(".github/pull_request_template.md", "changed\n").commit("wip")

        # WHEN/THEN a feat title fails and a chore title passes.
        self.assertTrue(release.check_pr(repo.git, base, head, "feat: update template"))
        self.assertEqual(release.check_pr(repo.git, base, head, "chore: update template"), [])

    def test_version_bump_allows_any_type(self):
        """A PR changing only a collection's version may be a chore, feat or fix."""
        # GIVEN a PR that changes only `common`'s version, like the release PR.
        repo = common_repo(self)
        base = repo.git.rev_parse("HEAD")
        head = repo.set_common_version("0.2.0", "wip")

        # WHEN/THEN the release PR's chore title and a graduation's feat! title both pass.
        self.assertEqual(release.check_pr(repo.git, base, head, "chore(release): common 0.2.0"), [])
        self.assertEqual(release.check_pr(repo.git, base, head, "feat!: declare common stable"), [])

    def test_version_bump_with_content_requires_feat_or_fix(self):
        """A PR changing a version and other `apm.yml` fields can't be a chore."""
        # GIVEN a PR that changes `common`'s version and its dependencies.
        repo = common_repo(self)
        base = repo.git.rev_parse("HEAD")
        repo.write("collections/common/apm.yml", apm_yml("common", "0.2.0", [".apm/skills/to-file"]))
        head = repo.commit("wip")

        # WHEN/THEN a chore title fails and a feat title passes.
        self.assertTrue(release.check_pr(repo.git, base, head, "chore: bump common"))
        self.assertEqual(release.check_pr(repo.git, base, head, "feat: bump common"), [])

    def test_deleting_a_collection_is_covered_at_base(self):
        """Deleting a collection counts as a covered change."""
        # GIVEN a PR that deletes the `foo` collection.
        repo = common_repo(self)
        repo.write("collections/foo/apm.yml", apm_yml("foo", "0.1.0", []))
        base = repo.commit("feat: add foo")
        repo.git.run("rm", "-q", "-r", "collections/foo")
        head = repo.commit("wip")

        # WHEN/THEN a chore title fails and a feat title passes.
        self.assertTrue(release.check_pr(repo.git, base, head, "chore: remove foo"))
        self.assertEqual(release.check_pr(repo.git, base, head, "feat: remove foo"), [])


class BumpTest(unittest.TestCase):
    """Tests for version bumps and which commits count towards them."""

    def test_bump_table(self):
        """The highest-impact commit wins, and chores alone don't release."""
        fix = Commit("fix", None, False, "x", None)
        feat_breaking = Commit("feat", None, True, "x", None)
        chore = Commit("chore", None, False, "x", None)
        chore_release = Commit("chore", "release", False, "x", None)
        self.assertEqual(release.compute_bump((0, 2, 0), [fix, feat_breaking]), (0, 3, 0))
        self.assertEqual(release.compute_bump((1, 2, 0), [feat_breaking]), (2, 0, 0))
        self.assertIsNone(release.compute_bump((0, 2, 0), [chore, chore_release]))

    def test_coverage_is_read_at_each_commit(self):
        """Shared changes count for every collection; earlier changes to a primitive don't."""
        # GIVEN collections `a` (uses `shared`) and `b` (uses `shared` and `p`), both tagged.
        repo = TempRepo(self)
        repo.write(".apm/skills/shared/SKILL.md", "s\n").write(".apm/skills/p/SKILL.md", "p\n")
        repo.write("collections/a/apm.yml", apm_yml("a", "0.1.0", [".apm/skills/shared"]))
        repo.write("collections/b/apm.yml", apm_yml("b", "0.1.0", [".apm/skills/shared", ".apm/skills/p"]))
        repo.commit("feat: add a and b")
        repo.tag("a-v0.1.0")
        repo.tag("b-v0.1.0")
        # AND a fix to `p`, then `p` added to `a`, then a fix to `shared`.
        repo.write(".apm/skills/p/SKILL.md", "p2\n").commit("fix(p): fix p (#2)")
        repo.write(
            "collections/a/apm.yml", apm_yml("a", "0.1.0", [".apm/skills/shared", ".apm/skills/p"])
        ).commit("feat(p): add p to a (#3)")
        repo.write(".apm/skills/shared/SKILL.md", "s2\n").commit("fix(shared): fix shared (#4)")

        # WHEN the commits for each collection are collected.
        r = release.Repo(repo.git)
        a_prs = [c.pr for c in r.commits("a", "a-v0.1.0..HEAD")]
        b_prs = [c.pr for c in r.commits("b", "b-v0.1.0..HEAD")]

        # THEN the `shared` fix is in both, and the earlier `p` fix is only in `b`.
        self.assertEqual(a_prs, [3, 4])
        self.assertEqual(b_prs, [2, 4])


class NotesTest(unittest.TestCase):
    """Tests for release notes."""

    def setUp(self):
        """Creates `common` tagged at 0.1.0."""
        self.repo = common_repo(self)
        self.repo.tag("common-v0.1.0")

    def notes(self):
        """Returns the notes for `common-v0.1.0..HEAD`."""
        return release.render_notes(release.Repo(self.repo.git).commits("common", "common-v0.1.0..HEAD"))

    def test_groups_scopes_and_exclusions(self):
        """Notes are grouped, keep scopes and PR numbers, and skip chores and uncovered commits."""
        # GIVEN a mix of covered, uncovered and release commits since the tag.
        repo = self.repo
        repo.write(".apm/skills/to-file/SKILL.md", "1\n").commit(
            "feat(to-file): support a custom artifact directory (#12)"
        )
        repo.write(".github/pull_request_template.md", "2\n").commit("chore: update CI (#13)")
        repo.write(".apm/agents/product-owner.agent.md", "3\n").commit(
            "fix(product-owner): stop repeating answered questions (#14)"
        )
        repo.write(".apm/agents/product-owner.agent.md", "4\n").commit(
            "fix: correct a typo in the architect prompt (#16)"
        )
        repo.set_common_version("0.2.0", "chore(release): common 0.2.0")
        repo.write(".apm/skills/to-file/SKILL.md", "6\n").commit(
            "feat(to-file)!: drop the legacy directory layout (#21)"
        )

        # WHEN/THEN the notes match exactly.
        self.assertEqual(
            self.notes(),
            "### Breaking Changes\n"
            "- **to-file:** drop the legacy directory layout (#21)\n"
            "### Features\n"
            "- **to-file:** support a custom artifact directory (#12)\n"
            "### Fixes\n"
            "- **product-owner:** stop repeating answered questions (#14)\n"
            "- correct a typo in the architect prompt (#16)",
        )

    def test_omits_empty_groups(self):
        """Groups without entries have no heading."""
        # GIVEN a single fix since the tag.
        self.repo.write(".apm/agents/product-owner.agent.md", "3\n").commit(
            "fix(product-owner): stop repeating answered questions (#14)"
        )

        # WHEN/THEN the notes have only the Fixes group.
        self.assertEqual(
            self.notes(), "### Fixes\n- **product-owner:** stop repeating answered questions (#14)"
        )


class ReleaseTest(unittest.TestCase):
    """Tests for `release` and `plan` against a fake GitHub."""

    def test_initial_release_tags_head(self):
        """An untagged collection is tagged at HEAD with an annotated tag."""
        # GIVEN an untagged collection.
        repo = common_repo(self)
        github = FakeGitHub()

        # WHEN `release` runs.
        errors = release.release(repo.git, github)

        # THEN an annotated tag at HEAD is pushed and released as "Initial release."
        self.assertEqual(errors, [])
        self.assertEqual(repo.tag_commit("common-v0.1.0"), repo.git.rev_parse("HEAD"))
        self.assertEqual(repo.git.run("cat-file", "-t", "common-v0.1.0").strip(), "tag")
        self.assertEqual(github.releases, {"common-v0.1.0": "Initial release."})
        self.assertIn("refs/tags/common-v0.1.0", repo.git.run("ls-remote", "--tags", "origin"))

    def test_tags_the_release_commit_not_head(self):
        """A re-run after more merges tags the commit that changed the version."""
        # GIVEN a merged release commit, followed by another merge before tagging.
        repo = common_repo(self)
        repo.tag("common-v0.1.0")
        repo.write(".apm/skills/to-file/SKILL.md", "1\n").commit("feat(to-file): x (#12)")
        release_commit = repo.set_common_version("0.2.0", "chore(release): common 0.2.0 (#15)")
        repo.write(".github/pull_request_template.md", "2\n").commit("chore: y (#20)")
        github = FakeGitHub()

        # WHEN `release` runs at the later HEAD.
        errors = release.release(repo.git, github)

        # THEN the release commit is tagged, with notes up to it.
        self.assertEqual(errors, [])
        self.assertEqual(repo.tag_commit("common-v0.2.0"), release_commit)
        self.assertEqual(github.releases, {"common-v0.2.0": "### Features\n- **to-file:** x (#12)"})

    def test_version_below_computed_bump_is_not_tagged(self):
        """A manual bump smaller than the commits require is rejected."""
        # GIVEN a feat followed by a manual patch bump.
        repo = common_repo(self)
        repo.tag("common-v0.1.0")
        repo.write(".apm/skills/to-file/SKILL.md", "1\n").commit("feat(to-file): x (#12)")
        repo.set_common_version("0.1.1", "fix: bump common (#13)")
        github = FakeGitHub()

        # WHEN `release` runs.
        errors = release.release(repo.git, github)

        # THEN it fails and nothing is tagged or released.
        self.assertEqual(len(errors), 1)
        self.assertIn("require at least 0.2.0", errors[0])
        self.assertEqual(repo.git.tags("common"), [(0, 1, 0)])
        self.assertEqual(github.releases, {})

    def test_stale_release_pr_is_corrected_by_plan(self):
        """An out-of-date release PR isn't tagged, and the next release PR corrects it."""
        # GIVEN a fix and a feat, then a stale release PR merged with the fix-only version.
        repo = common_repo(self)
        repo.tag("common-v0.2.0")
        repo.write(".apm/skills/to-file/SKILL.md", "1\n").commit("fix(to-file): x (#3)")
        repo.write(".apm/skills/to-file/SKILL.md", "2\n").commit("feat(to-file): y (#4)")
        repo.set_common_version("0.2.1", "chore(release): common 0.2.1 (#5)")
        github = FakeGitHub()

        # WHEN `release` and then `plan` run.
        errors = release.release(repo.git, github)
        release.plan(repo.git, github)

        # THEN nothing is tagged, and the release PR proposes 0.3.0 with the file otherwise intact.
        self.assertTrue(errors)
        self.assertEqual(repo.git.tags("common"), [(0, 2, 0)])
        self.assertEqual(github.pr["title"], "chore(release): common 0.3.0")
        proposed = repo.git.show(f"origin/{release.RELEASE_BRANCH}", "collections/common/apm.yml")
        self.assertIn("version: 0.3.0\n# A comment", proposed)

        # WHEN the corrected release PR is merged and the workflow runs again.
        repo.git.run("fetch", "-q", "origin")
        repo.git.run("merge", "-q", "--ff-only", f"origin/{release.RELEASE_BRANCH}")
        errors = release.release(repo.git, github)
        release.plan(repo.git, github)

        # THEN 0.3.0 is tagged and the release PR is closed.
        self.assertEqual(errors, [])
        self.assertEqual(repo.tag_commit("common-v0.3.0"), repo.git.rev_parse("HEAD"))
        self.assertIsNone(github.pr)

    def test_manual_bump_to_1_0_0_is_tagged(self):
        """A manual bump above the computed one is tagged and replaces the release PR."""
        # GIVEN a fix with an open release PR for 0.3.1.
        repo = common_repo(self)
        repo.tag("common-v0.3.0")
        repo.write(".apm/skills/to-file/SKILL.md", "1\n").commit("fix(to-file): x (#7)")
        github = FakeGitHub()
        release.plan(repo.git, github)
        self.assertEqual(github.pr["title"], "chore(release): common 0.3.1")
        # AND a PR that sets the version to 1.0.0.
        repo.set_common_version("1.0.0", "feat!: declare the collection stable (#8)")

        # WHEN `release` and then `plan` run.
        errors = release.release(repo.git, github)
        release.plan(repo.git, github)

        # THEN 1.0.0 is tagged with both commits in its notes, and the release PR is closed.
        self.assertEqual(errors, [])
        self.assertEqual(
            github.releases["common-v1.0.0"],
            "### Breaking Changes\n- declare the collection stable (#8)\n### Fixes\n- **to-file:** x (#7)",
        )
        self.assertIsNone(github.pr)


class DevPinsTest(unittest.TestCase):
    """Tests for reading and rewriting the pins in `dev/apm.yml`."""

    TEXT = (
        "dependencies:\n"
        "  apm:\n"
        "  - owner/repo/collections/common#common-v0.3.1\n"
        "  # A comment that must survive pin edits.\n"
        "  - owner/repo/collections/python#python-v0.1.0\n"
        "  - other/repo/collections/common#common-v0.1.0\n"
    )

    def test_repins_only_the_given_collections_of_this_repository(self):
        """Pins to other repositories, unlisted pins and other lines are kept as they are."""
        # WHEN `common` is repinned to 0.4.0.
        text = release.set_dev_pins(self.TEXT, "owner/repo", {"common": (0, 4, 0)})

        # THEN only this repository's `common` pin changes.
        self.assertEqual(release.dev_pins(text, "owner/repo"), {"common": (0, 4, 0), "python": (0, 1, 0)})
        self.assertEqual(release.dev_pins(text, "other/repo"), {"common": (0, 1, 0)})
        self.assertEqual(text, self.TEXT.replace("common#common-v0.3.1", "common#common-v0.4.0"))


class UpgradeDevTest(unittest.TestCase):
    """Tests for `upgrade_dev` against a fake GitHub and a fake `apm install`."""

    def setUp(self):
        """Creates a repository whose `dev/apm.yml` pins `common` to its only tag, 0.1.0."""
        self.repo = common_repo(self)
        self.repo.write("dev/apm.yml", "dependencies:\n  apm:\n  - owner/repo/collections/common#common-v0.1.0\n")
        self.repo.write("apm.lock.yaml", "stale\n")
        self.repo.commit("chore: pin common for development")
        self.repo.tag("common-v0.1.0")
        self.github = FakeGitHub()
        self.installs = 0

    def install(self):
        """Writes a lockfile from `dev/apm.yml`, failing if the old lockfile is still there."""
        lockfile = os.path.join(self.repo.path, "apm.lock.yaml")
        self.assertFalse(os.path.exists(lockfile), "the lockfile must be regenerated from scratch")
        with open(os.path.join(self.repo.path, "dev/apm.yml"), encoding="utf-8") as f:
            manifest = f.read()
        with open(lockfile, "w", encoding="utf-8") as f:
            f.write(f"installed from:\n{manifest}")
        self.installs += 1

    def upgrade_dev(self):
        """Runs `upgrade_dev` and returns the open upgrade PR, or None."""
        release.upgrade_dev(self.repo.git, self.github, self.install)
        return self.github.prs.get(release.UPGRADE_BRANCH)

    def test_opens_updates_and_closes_one_upgrade_pr(self):
        """Each new tag updates the same PR, and the PR closes once the pins are current."""
        # GIVEN pins that are current.
        # WHEN/THEN no PR opens and nothing is installed.
        self.assertIsNone(self.upgrade_dev())
        self.assertEqual(self.installs, 0)

        # GIVEN a release of `common` 0.2.0.
        self.repo.set_common_version("0.2.0", "chore(release): common 0.2.0")
        self.repo.tag("common-v0.2.0")

        # WHEN/THEN a PR opens that repins `common` and regenerates the lockfile.
        pr = self.upgrade_dev()
        self.assertEqual(pr["title"], "chore: upgrade dev pins to common 0.2.0")
        self.assertEqual(release.check_message(pr["title"]), [])
        branch = f"origin/{release.UPGRADE_BRANCH}"
        manifest = self.repo.git.show(branch, "dev/apm.yml")
        self.assertIn("#common-v0.2.0", manifest)
        self.assertEqual(self.repo.git.show(branch, "apm.lock.yaml"), f"installed from:\n{manifest}")

        # GIVEN another release before the PR merges.
        self.repo.git.run("checkout", "-q", "--", ".")
        self.repo.set_common_version("0.3.0", "chore(release): common 0.3.0")
        self.repo.tag("common-v0.3.0")

        # WHEN/THEN the same PR is updated to the newer tag.
        updated = self.upgrade_dev()
        self.assertEqual(updated["number"], pr["number"])
        self.assertEqual(updated["title"], "chore: upgrade dev pins to common 0.3.0")

        # WHEN the PR is merged and the workflow runs again.
        self.repo.git.run("checkout", "-q", "--", ".")
        self.repo.git.run("fetch", "-q", "origin")
        self.repo.git.run("merge", "-q", "--ff-only", branch)

        # THEN the PR is closed without another install.
        self.assertIsNone(self.upgrade_dev())
        self.assertEqual(self.installs, 2)


if __name__ == "__main__":
    unittest.main()
