"""Tests for the `intent-decisions` skill's `adr.py`."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

ADR = os.path.join(
    os.path.dirname(__file__), "..", "..", ".apm", "skills", "intent-decisions", "scripts", "adr.py"
)
_spec = importlib.util.spec_from_file_location("adr", ADR)
adr = importlib.util.module_from_spec(_spec)
sys.modules["adr"] = adr
_spec.loader.exec_module(adr)

HASH_A = "a" * 40
HASH_B = "b" * 40


def record(governs: tuple[str, ...] = ("src/**",), rows: tuple[tuple[str, str], ...] = (), decision: str = "Use X.") -> str:
    """Builds a decision record.

    Args:
        governs: The globs under `## Governs`.
        rows: `(previous, summary)` changelog rows, newest first.
        decision: The decision's text, so tests can change a record.

    Returns:
        The record's content.
    """
    text = "# Topic\n\nFacing A, we do X, accepting B.\n\n## Governs\n\n"
    text += "".join(f"- `{glob}`\n" for glob in governs)
    text += f"\n## Decision\n\n{decision}\n"
    if rows:
        text += "\n## Changelog\n\n| Previous version | Change |\n| --- | --- |\n"
        text += "".join(f"| {previous} | {summary} |\n" for previous, summary in rows)
    return text


class ParseRecordTest(unittest.TestCase):
    def test_reads_governs_and_rows(self):
        parsed = adr.parse_record(record(("src/**", "**/*.py"), ((HASH_A, "Second."), (HASH_B, "First."))))
        self.assertEqual(parsed.governs, ["src/**", "**/*.py"])
        self.assertEqual(parsed.rows, [adr.Row(HASH_A, "Second."), adr.Row(HASH_B, "First.")])

    def test_rejects_malformed_sections(self):
        cases = {
            "missing governs": "# Topic\n\n## Decision\n\nX\n",
            "unquoted glob": record().replace("- `src/**`", "- src/**"),
            "empty governs": record(governs=()),
            "absolute glob": record(governs=("/src/**",)),
            "abbreviated hash": record(rows=(("abc1234", "Change."),)),
            "missing header": record(rows=((HASH_A, "Change."),)).replace("| Previous version | Change |\n", ""),
            "header without rows": record() + "\n## Changelog\n\n| Previous version | Change |\n| --- | --- |\n",
            "repeated commit": record(rows=((HASH_A, "Two."), (HASH_A, "One."))),
        }
        for name, text in cases.items():
            with self.subTest(name), self.assertRaises(adr.Error):
                adr.parse_record(text)

    def test_ignores_headings_in_code_blocks(self):
        text = record() + "\n## Notes\n\n```\n## Governs\n- nothing\n```\n"
        self.assertEqual(adr.parse_record(text).governs, ["src/**"])


class GlobTest(unittest.TestCase):
    def test_matches_like_repository_globs(self):
        paths = ["README.md", "src/app.py", "src/pkg/mod.py", "srcx/app.py", "tests/test_app.py"]
        cases = {
            "**": paths,
            "src/**": ["src/app.py", "src/pkg/mod.py"],
            "**/*.py": ["src/app.py", "src/pkg/mod.py", "srcx/app.py", "tests/test_app.py"],
            "src/*.py": ["src/app.py"],
            "src/**/mod.py": ["src/pkg/mod.py"],
            "?EADME.md": ["README.md"],
        }
        for glob, expected in cases.items():
            with self.subTest(glob):
                self.assertEqual(adr.governed([glob], paths), expected)


class WithRowTest(unittest.TestCase):
    def test_adds_a_changelog_to_a_record_without_one(self):
        text = adr.with_row(record(), [], adr.Row(HASH_A, "Change."))
        self.assertEqual(adr.parse_record(text).rows, [adr.Row(HASH_A, "Change.")])
        self.assertTrue(text.startswith(record().rstrip("\n")))

    def test_adds_on_top_then_replaces_its_own_row(self):
        base_rows = [adr.Row(HASH_B, "First.")]
        once = adr.with_row(record(rows=((HASH_B, "First."),)), base_rows, adr.Row(HASH_A, "Draft."))
        twice = adr.with_row(once, base_rows, adr.Row(HASH_A, "Final."))
        self.assertEqual(adr.parse_record(twice).rows, [adr.Row(HASH_A, "Final."), *base_rows])

    def test_keeps_sections_after_the_changelog(self):
        text = record(rows=((HASH_B, "First."),)) + "\n## Notes\n\nKept.\n"
        updated = adr.with_row(text, [adr.Row(HASH_B, "First.")], adr.Row(HASH_A, "Change."))
        self.assertTrue(updated.endswith("\n## Notes\n\nKept.\n"))
        self.assertEqual(len(adr.parse_record(updated).rows), 2)

    def test_refuses_a_changelog_edited_beyond_its_row(self):
        text = record(rows=((HASH_B, "Rewritten."),))
        with self.assertRaises(adr.Error):
            adr.with_row(text, [adr.Row(HASH_B, "First.")], adr.Row(HASH_A, "Change."))

    def test_escapes_pipes_in_summaries(self):
        row = adr.Row(HASH_A, adr.escape_summary("Use A | B."))
        self.assertEqual(adr.parse_record(adr.with_row(record(), [], row)).rows, [row])


class AuditErrorsTest(unittest.TestCase):
    def test_accepts_rows_that_follow_the_history(self):
        changes = ["c3", "c2", "c1"]
        for rows in (["c2", "c1"], ["c2"], ["c1"], []):
            with self.subTest(rows):
                self.assertEqual(adr.audit_errors([adr.Row(r, "Change.") for r in rows], changes), [])

    def test_rejects_rows_that_cannot_hold_a_previous_version(self):
        changes = ["c3", "c2", "c1"]
        cases = {
            "unknown commit": (["c9"], "not a first-parent commit"),
            "latest change": (["c3"], "is the last change"),
            "out of order": (["c1", "c2"], "out of order"),
        }
        for name, (rows, message) in cases.items():
            with self.subTest(name):
                errors = adr.audit_errors([adr.Row(r, "Change.") for r in rows], changes)
                self.assertEqual(len(errors), 1)
                self.assertIn(message, errors[0])


class DanglingTest(unittest.TestCase):
    def test_finds_references_to_missing_records(self):
        texts = {
            "README.md": "See intent/decisions/gone.md and intent/decisions/kept.md.",
            "docs/guide.md": "[x](../intent/decisions/gone.md)",
            "intent/decisions/kept.md": "Unlike [gone](gone.md)." + record(rows=((HASH_A, "Merged gone.md here."),)),
            "src/app.py": "# https://example.com/intent/decisions/gone.md",
        }
        found = adr.dangling(texts, "intent/decisions", {"intent/decisions/kept.md"})
        self.assertEqual(
            found,
            [
                ("README.md", "intent/decisions/gone.md"),
                ("docs/guide.md", "intent/decisions/gone.md"),
                ("intent/decisions/kept.md", "intent/decisions/gone.md"),
            ],
        )


    def test_ignores_code_in_markdown_but_not_in_other_files(self):
        example = "Use `intent/decisions/example.md`.\n\n  ```\n  intent/decisions/example.md\n  ```\n"
        texts = {
            "docs/guide.md": example + "But [this](../intent/decisions/real.md) is a link.\n",
            "src/app.py": "# See intent/decisions/real.md.\n",
        }
        self.assertEqual(
            adr.dangling(texts, "intent/decisions", set()),
            [("docs/guide.md", "intent/decisions/real.md"), ("src/app.py", "intent/decisions/real.md")],
        )

    def test_shipped_docs_refer_to_no_record(self):
        root = os.path.join(os.path.dirname(ADR), "..", "..", "..")
        shipped = {
            ".claude/skills/intent-decisions/SKILL.md": os.path.join(os.path.dirname(ADR), "..", "SKILL.md"),
            ".claude/rules/intent-decisions.md": os.path.join(root, "instructions", "intent-decisions.instructions.md"),
            ".claude/rules/decision-records.md": os.path.join(root, "instructions", "decision-records.instructions.md"),
        }
        texts = {}
        for deployed, source in shipped.items():
            with open(source, encoding="utf-8") as f:
                texts[deployed] = f.read()
        self.assertEqual(adr.dangling(texts, "intent/decisions", set()), [])


class ParseConfigTest(unittest.TestCase):
    def test_defaults_without_a_file(self):
        self.assertEqual(adr.parse_config(None), adr.Config("intent/decisions", None))

    def test_reads_settings(self):
        text = (
            'canonical_branch = "origin/develop"\n[decisions]\npath = "design/adr/"\n'
            '[references]\nexclude = ["tests/**"]\n'
        )
        self.assertEqual(adr.parse_config(text), adr.Config("design/adr", "origin/develop", ("tests/**",)))

    def test_rejects_invalid_settings(self):
        cases = {
            "unknown key": 'branch = "main"\n',
            "unknown nested key": '[decisions]\ndir = "x"\n',
            "outside the repository": '[decisions]\npath = "../x"\n',
            "absolute path": '[decisions]\npath = "/x"\n',
            "empty branch": 'canonical_branch = ""\n',
            "references not a table": 'references = ["tests/**"]\n',
            "unknown references key": '[references]\ninclude = ["tests/**"]\n',
            "exclude not a list": '[references]\nexclude = "tests/**"\n',
            "empty exclude glob": '[references]\nexclude = [""]\n',
        }
        for name, text in cases.items():
            with self.subTest(name), self.assertRaises(adr.Error):
                adr.parse_config(text)


class Repo:
    """A throwaway repository whose `origin` is a local bare repository."""

    def __init__(self, test: unittest.TestCase):
        """Creates the repositories with one governed file and one record on `main`.

        Args:
            test: The test case that owns the repositories.
        """
        tmp = tempfile.TemporaryDirectory()
        test.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, "work")
        origin = os.path.join(tmp.name, "origin.git")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", origin], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", self.path], check=True)
        for key, value in [
            ("user.name", "Test"),
            ("user.email", "test@example.com"),
            ("commit.gpgsign", "false"),
            ("merge.ff", "true"),
            ("pull.rebase", "false"),
        ]:
            self.git("config", key, value)
        self.git("remote", "add", "origin", origin)
        self.write("src/app.py", "print('hi')\n")
        self.write("intent/decisions/topic.md", record())
        self.created = self.commit("Add topic")
        self.git("push", "-q", "-u", "origin", "main")
        self.git("remote", "set-head", "origin", "main")

    def git(self, *args: str) -> str:
        """Runs git in the working repository and returns its output."""
        result = subprocess.run(["git", *args], cwd=self.path, check=True, capture_output=True, text=True)
        return result.stdout.strip()

    def write(self, path: str, content: str) -> None:
        """Writes a file in the working tree."""
        full = os.path.join(self.path, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)

    def read(self, path: str) -> str:
        """Reads a file from the working tree."""
        with open(os.path.join(self.path, path), encoding="utf-8") as f:
            return f.read()

    def commit(self, subject: str) -> str:
        """Commits every change and returns the new commit's hash."""
        self.git("add", "-A")
        self.git("commit", "-q", "-m", subject)
        return self.git("rev-parse", "HEAD")

    def adr(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        """Runs `adr.py` in the working repository."""
        full_env = {key: value for key, value in os.environ.items() if key != adr.CONFIG_ENV}
        full_env.update(env or {})
        return subprocess.run(
            [sys.executable, ADR, *args], cwd=self.path, env=full_env, capture_output=True, text=True
        )

    def edit(self, decision: str, summary: str) -> None:
        """Changes the record's decision and records the change set's row."""
        text = self.read("intent/decisions/topic.md").replace(self.decision(), decision)
        self.write("intent/decisions/topic.md", text)
        result = self.adr("row", "intent/decisions/topic.md", "--summary", summary)
        assert result.returncode == 0, result.stderr

    def decision(self) -> str:
        """Returns the record's current decision text."""
        lines = self.read("intent/decisions/topic.md").splitlines()
        return lines[lines.index("## Decision") + 2]

    def rows(self) -> list:
        """Returns the record's changelog rows."""
        return adr.parse_record(self.read("intent/decisions/topic.md")).rows

    def land(self, branch: str, how: str) -> str:
        """Lands `branch` on `main`, pushes, and returns `main`'s new head.

        Args:
            branch: The branch to land.
            how: `squash`, `merge`, or `rebase`.
        """
        if how == "rebase":
            self.git("rebase", "-q", "main", branch)
        self.git("checkout", "-q", "main")
        if how == "squash":
            self.git("merge", "-q", "--squash", branch)
            self.git("commit", "-q", "-m", f"Land {branch}")
        elif how == "merge":
            self.git("merge", "-q", "--no-ff", "-m", f"Merge {branch}", branch)
        else:
            self.git("merge", "-q", "--ff-only", branch)
        self.git("push", "-q", "origin", "main")
        return self.git("rev-parse", "HEAD")

    def assert_check(self, test: unittest.TestCase, *expected: str) -> None:
        """Asserts that `adr.py check` passes, or fails with each expected message."""
        result = self.adr("check")
        if not expected:
            test.assertEqual((result.returncode, result.stderr), (0, ""))
            return
        test.assertEqual(result.returncode, 1)
        for message in expected:
            test.assertIn(message, result.stderr)


class MergeStrategyTest(unittest.TestCase):
    def test_rows_point_at_the_previous_version_under_every_strategy(self):
        for how in ("squash", "merge", "rebase"):
            with self.subTest(how):
                repo = Repo(self)
                repo.git("checkout", "-q", "-b", "one")
                repo.edit("Use Y.", "Draft.")
                repo.commit("Edit once")
                repo.edit("Use Z.", "Switch to Z.")
                repo.commit("Edit again")
                self.assertEqual(repo.rows(), [adr.Row(repo.created, "Switch to Z.")])
                repo.assert_check(self)
                landed = repo.land("one", how)
                repo.assert_check(self)
                self.assertEqual(repo.adr("audit").returncode, 0)

                repo.git("checkout", "-q", "-b", "two")
                repo.edit("Use W.", "Switch to W.")
                repo.assert_check(self)
                self.assertEqual(repo.rows()[0].previous, landed)
                self.assertEqual(
                    repo.git("show", f"{landed}:intent/decisions/topic.md"),
                    repo.git("show", "HEAD:intent/decisions/topic.md"),
                )

    def test_merging_the_canonical_branch_in_moves_the_base(self):
        repo = Repo(self)
        repo.git("checkout", "-q", "-b", "feature")
        repo.write("src/app.py", "print('feature')\n")
        repo.commit("Feature work")
        repo.git("checkout", "-q", "-b", "other", "main")
        repo.edit("Use Y.", "Switch to Y.")
        repo.commit("Edit")
        landed = repo.land("other", "squash")
        repo.git("checkout", "-q", "feature")
        repo.git("merge", "-q", "-m", "Sync", "main")
        repo.edit("Use Z.", "Switch to Z.")
        repo.assert_check(self)
        self.assertEqual(repo.rows()[0].previous, landed)


class CheckTest(unittest.TestCase):
    def test_rejects_a_change_without_its_row(self):
        repo = Repo(self)
        repo.write("intent/decisions/topic.md", record(decision="Use Y."))
        repo.assert_check(self, f"the newest row must be {repo.created}")

    def test_rejects_a_hand_written_row_with_the_wrong_commit(self):
        repo = Repo(self)
        repo.write("intent/decisions/topic.md", record(decision="Use Y.", rows=((HASH_A, "Change."),)))
        repo.assert_check(self, f"the newest row must be {repo.created}")

    def test_rejects_a_new_record_with_rows(self):
        repo = Repo(self)
        repo.write("intent/decisions/new.md", record(rows=((repo.created, "Change."),)))
        repo.assert_check(self, "intent/decisions/new.md: a new record has no changelog rows")

    def test_rejects_reusing_a_deleted_slug(self):
        repo = Repo(self)
        repo.write("intent/decisions/other.md", record())
        os.remove(os.path.join(repo.path, "intent/decisions/topic.md"))
        repo.commit("Replace topic")
        repo.git("push", "-q", "origin", "main")
        repo.write("intent/decisions/topic.md", record())
        repo.assert_check(self, "intent/decisions/topic.md: this slug was used before")

    def test_rejects_references_to_a_deleted_record(self):
        repo = Repo(self)
        repo.write("intent/decisions/other.md", record(decision="Unlike [topic](topic.md)."))
        repo.write("README.md", "See intent/decisions/topic.md.\n")
        repo.commit("Refer to topic")
        repo.git("push", "-q", "origin", "main")
        os.remove(os.path.join(repo.path, "intent/decisions/topic.md"))
        repo.assert_check(
            self,
            "README.md: refers to intent/decisions/topic.md, which does not exist",
            "intent/decisions/other.md: refers to intent/decisions/topic.md, which does not exist",
        )

    def test_skips_excluded_files_only_in_the_reference_check(self):
        repo = Repo(self)
        repo.write("tests/test_x.py", 'FIXTURE = "intent/decisions/gone.md"\n')
        repo.write("README.md", "See intent/decisions/gone.md.\n")
        repo.write("intent/config.toml", '[references]\nexclude = ["tests/**"]\n')
        result = repo.adr("check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("README.md: refers to intent/decisions/gone.md", result.stderr)
        self.assertNotIn("tests/test_x.py", result.stderr)

    def test_rejects_exclude_globs_that_match_nothing_or_a_record(self):
        repo = Repo(self)
        repo.write("intent/decisions/other.md", record(decision="Unlike [gone](gone.md)."))
        repo.write("intent/config.toml", '[references]\nexclude = ["lib/**", "intent/**"]\n')
        repo.assert_check(
            self,
            "intent/config.toml: references.exclude glob matches no file: lib/**",
            "references.exclude glob matches a record: intent/**: intent/decisions/other.md",
            "intent/decisions/other.md: refers to intent/decisions/gone.md, which does not exist",
        )

    def test_rejects_globs_that_match_nothing(self):
        repo = Repo(self)
        repo.write("intent/decisions/other.md", record(governs=("lib/**",)))
        repo.assert_check(self, "intent/decisions/other.md: glob matches no file: lib/**")

    def test_rejects_moving_records(self):
        repo = Repo(self)
        repo.git("mv", "intent/decisions", "intent/adr")
        repo.write("intent/config.toml", '[decisions]\npath = "intent/adr"\n')
        repo.assert_check(self, "decisions moved from intent/decisions/")

    def test_fails_when_no_records_are_found(self):
        repo = Repo(self)
        repo.assert_check(self)
        result = repo.adr("check", env={adr.CONFIG_ENV: "elsewhere.toml"})
        self.assertIn("elsewhere.toml, which does not exist", result.stderr)
        repo.write("elsewhere.toml", '[decisions]\npath = "docs/adr"\n')
        result = repo.adr("check", env={adr.CONFIG_ENV: "elsewhere.toml"})
        self.assertEqual(result.returncode, 1)
        self.assertIn("no decision records found at docs/adr/", result.stderr)

    def test_fails_when_the_canonical_branch_is_unknown(self):
        repo = Repo(self)
        repo.git("remote", "set-head", "origin", "--delete")
        result = repo.adr("check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot tell the canonical branch", result.stderr)
        repo.write("intent/config.toml", 'canonical_branch = "origin/main"\n')
        repo.assert_check(self)

    def test_uses_the_configured_canonical_branch(self):
        repo = Repo(self)
        repo.git("checkout", "-q", "-b", "develop")
        repo.write("intent/config.toml", 'canonical_branch = "origin/develop"\n')
        repo.commit("Configure")
        repo.git("push", "-q", "origin", "develop")
        repo.edit("Use Y.", "Switch to Y.")
        develop = repo.commit("Edit on develop")
        repo.git("push", "-q", "origin", "develop")
        repo.git("checkout", "-q", "-b", "feature")
        repo.edit("Use Z.", "Switch to Z.")
        repo.assert_check(self)
        self.assertEqual(repo.rows()[0].previous, develop)


class AuditTest(unittest.TestCase):
    def test_finds_a_row_that_bypassed_the_check(self):
        repo = Repo(self)
        repo.write("intent/decisions/topic.md", record(decision="Use Y.", rows=((HASH_A, "Change."),)))
        repo.commit("Edit without the hook")
        result = repo.adr("audit")
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"intent/decisions/topic.md: row {HASH_A}: not a first-parent commit", result.stderr)

    def test_does_not_need_the_canonical_branch(self):
        repo = Repo(self)
        repo.git("remote", "set-head", "origin", "--delete")
        self.assertEqual(repo.adr("audit").returncode, 0)


class RowTest(unittest.TestCase):
    def test_refuses_new_records(self):
        repo = Repo(self)
        repo.write("intent/decisions/new.md", record())
        result = repo.adr("row", "intent/decisions/new.md", "--summary", "Change.")
        self.assertEqual(result.returncode, 1)
        self.assertIn("new records have no changelog", result.stderr)

    def test_takes_paths_relative_to_the_working_directory(self):
        repo = Repo(self)
        result = subprocess.run(
            [sys.executable, ADR, "row", "topic.md", "--summary", "Change."],
            cwd=os.path.join(repo.path, "intent/decisions"),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(repo.rows(), [adr.Row(repo.created, "Change.")])


class AffectedTest(unittest.TestCase):
    def test_lists_records_governing_the_files(self):
        repo = Repo(self)
        repo.write("intent/decisions/global.md", record(governs=("**",)))
        repo.write("intent/decisions/docs.md", record(governs=("README.md",)))
        repo.write("README.md", "Hi.\n")
        result = repo.adr("affected", "src/app.py")
        self.assertEqual(result.stdout.splitlines(), ["intent/decisions/global.md", "intent/decisions/topic.md"])

    def test_defaults_to_the_files_changed_since_the_base(self):
        repo = Repo(self)
        repo.write("intent/decisions/docs.md", record(governs=("README.md",)))
        repo.write("README.md", "Hi.\n")
        repo.commit("Add docs record")
        repo.git("push", "-q", "origin", "main")
        repo.write("README.md", "Hello.\n")
        self.assertEqual(repo.adr("affected").stdout.splitlines(), ["intent/decisions/docs.md"])

    def test_includes_the_old_path_of_a_moved_file(self):
        repo = Repo(self)
        os.makedirs(os.path.join(repo.path, "lib"))
        repo.git("mv", "src/app.py", "lib/app.py")
        self.assertEqual(repo.adr("affected").stdout.splitlines(), ["intent/decisions/topic.md"])


if __name__ == "__main__":
    unittest.main()
