import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import release  # noqa: E402
from release import Commit  # noqa: E402


def apm_yml(name: str, version: str, paths: list[str]) -> str:
    deps = "".join(f"  - git: parent\n    path: {p}\n" for p in paths)
    return (
        f"name: {name}\n"
        f"version: {version}  \n"
        f"# A comment that must survive version edits.\n"
        f"dependencies:\n  apm:\n{deps}  mcp: []\n"
    )


class TempRepo:
    """A throwaway git repository with a bare `origin`."""

    def __init__(self, test: unittest.TestCase):
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
        full = os.path.join(self.path, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return self

    def commit(self, subject: str) -> str:
        self.git.run("add", "-A")
        self.git.run("commit", "-q", "-m", subject)
        return self.git.rev_parse("HEAD")

    def tag(self, tag: str) -> None:
        self.git.create_tag(tag, "HEAD", tag)

    def tag_commit(self, tag: str) -> str:
        return self.git.rev_parse(tag)


class FakeGitHub:
    def __init__(self):
        self.pr = None
        self.releases = {}

    def find_release_pr(self):
        return self.pr["number"] if self.pr else None

    def create_pr(self, title, body):
        self.pr = {"number": 1, "title": title, "body": body}

    def edit_pr(self, number, title, body):
        self.pr = {"number": number, "title": title, "body": body}

    def close_pr(self, number):
        self.pr = None

    def create_release(self, tag, notes):
        self.releases[tag] = notes


def common_repo(test: unittest.TestCase) -> TempRepo:
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
    def test_parses_valid_and_rejects_unknown_types_and_breaking_chore(self):
        self.assertEqual(
            release.parse_subject("feat(to-file)!: x (#21)"),
            Commit("feat", "to-file", True, "x", 21),
        )
        self.assertIsNone(release.parse_subject("chore!: x"))
        self.assertIsNone(release.parse_subject("docs: x"))


class CheckPrTest(unittest.TestCase):
    def test_covered_change_requires_feat_or_fix(self):
        repo = common_repo(self)
        base = repo.git.rev_parse("HEAD")
        head = repo.write(".apm/skills/to-file/SKILL.md", "changed\n").commit("wip")
        self.assertTrue(release.check_pr(repo.git, base, head, "chore: update skill"))
        self.assertEqual(release.check_pr(repo.git, base, head, "fix: update skill"), [])

    def test_uncovered_change_requires_chore(self):
        repo = common_repo(self)
        base = repo.git.rev_parse("HEAD")
        head = repo.write(".github/pull_request_template.md", "changed\n").commit("wip")
        self.assertTrue(release.check_pr(repo.git, base, head, "feat: update template"))
        self.assertEqual(release.check_pr(repo.git, base, head, "chore: update template"), [])

    def test_deleting_a_collection_is_covered_at_base(self):
        repo = common_repo(self)
        repo.write("collections/foo/apm.yml", apm_yml("foo", "0.1.0", []))
        base = repo.commit("feat: add foo")
        repo.git.run("rm", "-q", "-r", "collections/foo")
        head = repo.commit("wip")
        self.assertTrue(release.check_pr(repo.git, base, head, "chore: remove foo"))
        self.assertEqual(release.check_pr(repo.git, base, head, "feat: remove foo"), [])


class BumpTest(unittest.TestCase):
    def test_bump_table(self):
        fix = Commit("fix", None, False, "x", None)
        feat_breaking = Commit("feat", None, True, "x", None)
        chore = Commit("chore", None, False, "x", None)
        chore_release = Commit("chore", "release", False, "x", None)
        self.assertEqual(release.compute_bump((0, 2, 0), [fix, feat_breaking]), (0, 3, 0))
        self.assertEqual(release.compute_bump((1, 2, 0), [feat_breaking]), (2, 0, 0))
        self.assertIsNone(release.compute_bump((0, 2, 0), [chore, chore_release]))

    def test_coverage_is_read_at_each_commit(self):
        repo = TempRepo(self)
        repo.write(".apm/skills/shared/SKILL.md", "s\n").write(".apm/skills/p/SKILL.md", "p\n")
        repo.write("collections/a/apm.yml", apm_yml("a", "0.1.0", [".apm/skills/shared"]))
        repo.write("collections/b/apm.yml", apm_yml("b", "0.1.0", [".apm/skills/shared", ".apm/skills/p"]))
        repo.commit("feat: add a and b")
        repo.tag("a-v0.1.0")
        repo.tag("b-v0.1.0")
        repo.write(".apm/skills/p/SKILL.md", "p2\n").commit("fix(p): fix p (#2)")
        repo.write(
            "collections/a/apm.yml", apm_yml("a", "0.1.0", [".apm/skills/shared", ".apm/skills/p"])
        ).commit("feat(p): add p to a (#3)")
        repo.write(".apm/skills/shared/SKILL.md", "s2\n").commit("fix(shared): fix shared (#4)")

        r = release.Repo(repo.git)
        self.assertEqual([c.pr for c in r.commits("a", "a-v0.1.0..HEAD")], [3, 4])
        self.assertEqual([c.pr for c in r.commits("b", "b-v0.1.0..HEAD")], [2, 4])


class NotesTest(unittest.TestCase):
    def setUp(self):
        self.repo = common_repo(self)
        self.repo.tag("common-v0.1.0")

    def notes(self):
        return release.render_notes(release.Repo(self.repo.git).commits("common", "common-v0.1.0..HEAD"))

    def test_groups_scopes_and_exclusions(self):
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
        repo.write(
            "collections/common/apm.yml",
            apm_yml("common", "0.2.0", [".apm/skills/to-file", ".apm/agents/product-owner.agent.md"]),
        ).commit("chore(release): common 0.2.0")
        repo.write(".apm/skills/to-file/SKILL.md", "6\n").commit(
            "feat(to-file)!: drop the legacy directory layout (#21)"
        )
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
        self.repo.write(".apm/agents/product-owner.agent.md", "3\n").commit(
            "fix(product-owner): stop repeating answered questions (#14)"
        )
        self.assertEqual(
            self.notes(), "### Fixes\n- **product-owner:** stop repeating answered questions (#14)"
        )


class ReleaseTest(unittest.TestCase):
    def set_common_version(self, repo: TempRepo, version: str, subject: str) -> str:
        path = os.path.join(repo.path, "collections/common/apm.yml")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        return repo.write("collections/common/apm.yml", release.set_version(text, version)).commit(subject)

    def test_initial_release_tags_head(self):
        repo = common_repo(self)
        github = FakeGitHub()
        self.assertEqual(release.release(repo.git, github), [])
        self.assertEqual(repo.tag_commit("common-v0.1.0"), repo.git.rev_parse("HEAD"))
        self.assertEqual(repo.git.run("cat-file", "-t", "common-v0.1.0").strip(), "tag")
        self.assertEqual(github.releases, {"common-v0.1.0": "Initial release."})
        self.assertIn("refs/tags/common-v0.1.0", repo.git.run("ls-remote", "--tags", "origin"))

    def test_tags_the_release_commit_not_head(self):
        repo = common_repo(self)
        repo.tag("common-v0.1.0")
        repo.write(".apm/skills/to-file/SKILL.md", "1\n").commit("feat(to-file): x (#12)")
        release_commit = self.set_common_version(repo, "0.2.0", "chore(release): common 0.2.0 (#15)")
        repo.write(".github/pull_request_template.md", "2\n").commit("chore: y (#20)")

        github = FakeGitHub()
        self.assertEqual(release.release(repo.git, github), [])
        self.assertEqual(repo.tag_commit("common-v0.2.0"), release_commit)
        self.assertEqual(github.releases, {"common-v0.2.0": "### Features\n- **to-file:** x (#12)"})

    def test_version_below_computed_bump_is_not_tagged(self):
        repo = common_repo(self)
        repo.tag("common-v0.1.0")
        repo.write(".apm/skills/to-file/SKILL.md", "1\n").commit("feat(to-file): x (#12)")
        self.set_common_version(repo, "0.1.1", "fix: bump common (#13)")

        github = FakeGitHub()
        errors = release.release(repo.git, github)
        self.assertEqual(len(errors), 1)
        self.assertIn("require at least 0.2.0", errors[0])
        self.assertEqual(repo.git.tags("common"), [(0, 1, 0)])
        self.assertEqual(github.releases, {})

    def test_stale_release_pr_is_corrected_by_plan(self):
        repo = common_repo(self)
        repo.tag("common-v0.2.0")
        repo.write(".apm/skills/to-file/SKILL.md", "1\n").commit("fix(to-file): x (#3)")
        repo.write(".apm/skills/to-file/SKILL.md", "2\n").commit("feat(to-file): y (#4)")
        self.set_common_version(repo, "0.2.1", "chore(release): common 0.2.1 (#5)")

        github = FakeGitHub()
        self.assertTrue(release.release(repo.git, github))
        self.assertEqual(repo.git.tags("common"), [(0, 2, 0)])

        release.plan(repo.git, github)
        self.assertEqual(github.pr["title"], "chore(release): common 0.3.0")
        proposed = repo.git.show(f"origin/{release.RELEASE_BRANCH}", "collections/common/apm.yml")
        self.assertIn("version: 0.3.0\n# A comment", proposed)

        # Merge the corrected release PR.
        repo.git.run("fetch", "-q", "origin")
        repo.git.run("merge", "-q", "--ff-only", f"origin/{release.RELEASE_BRANCH}")
        self.assertEqual(release.release(repo.git, github), [])
        self.assertEqual(repo.tag_commit("common-v0.3.0"), repo.git.rev_parse("HEAD"))

        release.plan(repo.git, github)
        self.assertIsNone(github.pr)

    def test_manual_bump_to_1_0_0_is_tagged(self):
        repo = common_repo(self)
        repo.tag("common-v0.3.0")
        repo.write(".apm/skills/to-file/SKILL.md", "1\n").commit("fix(to-file): x (#7)")
        github = FakeGitHub()
        release.plan(repo.git, github)
        self.assertEqual(github.pr["title"], "chore(release): common 0.3.1")

        self.set_common_version(repo, "1.0.0", "feat!: declare the collection stable (#8)")
        self.assertEqual(release.release(repo.git, github), [])
        self.assertEqual(
            github.releases["common-v1.0.0"],
            "### Breaking Changes\n- declare the collection stable (#8)\n### Fixes\n- **to-file:** x (#7)",
        )
        release.plan(repo.git, github)
        self.assertIsNone(github.pr)


if __name__ == "__main__":
    unittest.main()
