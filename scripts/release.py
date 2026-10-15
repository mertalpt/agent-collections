#!/usr/bin/env python3
"""Per-collection release tooling. See docs/releasing.md and CONTRIBUTING.md."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass

import yaml

RELEASE_BRANCH = "release/pending"
MAIN_BRANCH = "main"


class ReleaseError(Exception):
    pass


# --- Conventions -------------------------------------------------------------

TYPES = ("feat", "fix", "chore")
SUBJECT_RE = re.compile(
    r"^(?P<type>[a-z]+)"
    r"(?:\((?P<scope>[^()\s]+)\))?"
    r"(?P<breaking>!)?"
    r": (?P<subject>\S.*?)"
    r"(?: \(#(?P<pr>\d+)\))?$"
)
SKIPPED_MESSAGE_PREFIXES = ("Merge ", "fixup! ", "squash! ", "amend! ")


@dataclass(frozen=True)
class Commit:
    type: str
    scope: str | None
    breaking: bool
    subject: str
    pr: int | None


def parse_subject(line: str) -> Commit | None:
    """Parse a commit subject or PR title. Returns None if it is invalid."""
    match = SUBJECT_RE.match(line.strip())
    if not match or match["type"] not in TYPES:
        return None
    breaking = match["breaking"] is not None
    if breaking and match["type"] == "chore":
        return None
    pr = int(match["pr"]) if match["pr"] else None
    return Commit(match["type"], match["scope"], breaking, match["subject"], pr)


def subject_error(line: str) -> str:
    return (
        f"Invalid subject {line!r}. Expected '<type>[(<scope>)][!]: <subject>' "
        f"with type one of {', '.join(TYPES)}; '!' only on feat and fix."
    )


# --- Semver ------------------------------------------------------------------

SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")

Version = tuple[int, int, int]


def parse_version(value: object) -> Version:
    if not isinstance(value, str) or not SEMVER_RE.match(value):
        raise ReleaseError(f"Invalid version {value!r}. Expected X.Y.Z.")
    major, minor, patch = (int(part) for part in value.split("."))
    return major, minor, patch


def format_version(version: Version) -> str:
    return ".".join(str(part) for part in version)


def compute_bump(current: Version, commits: list[Commit]) -> Version | None:
    """Apply the highest-impact commit to `current`. None means no release."""
    major, minor, patch = current
    if any(c.breaking for c in commits):
        return (major + 1, 0, 0) if major > 0 else (0, minor + 1, 0)
    if any(c.type == "feat" for c in commits):
        return major, minor + 1, 0
    if any(c.type == "fix" for c in commits):
        return major, minor, patch + 1
    return None


# --- Git ---------------------------------------------------------------------


class Git:
    def __init__(self, cwd: str = "."):
        self.cwd = cwd

    def run(self, *args: str, input: str | None = None, env: dict | None = None) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.cwd,
            input=input,
            env={**os.environ, **env} if env else None,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise ReleaseError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout

    def rev_parse(self, rev: str) -> str:
        return self.run("rev-parse", "--verify", f"{rev}^{{commit}}").strip()

    def show(self, rev: str, path: str) -> str:
        return self.run("show", f"{rev}:{path}")

    def exists(self, rev: str, path: str) -> bool:
        return bool(self.run("ls-tree", rev, "--", path).strip())

    def ls_tree(self, rev: str, path: str) -> list[str]:
        return self.run("ls-tree", "-r", "--name-only", rev, "--", path).splitlines()

    def diff_names(self, base: str, head: str) -> list[str]:
        return self.run("diff", "--name-only", f"{base}...{head}").splitlines()

    def log(self, rev_range: str) -> list[tuple[str, str]]:
        """Commits in `rev_range` as (sha, subject), oldest first."""
        out = self.run("log", "--reverse", "--format=%H%x00%s", rev_range)
        return [tuple(line.split("\0", 1)) for line in out.splitlines()]

    def diff_tree(self, sha: str) -> list[str]:
        return self.run("diff-tree", "--root", "--no-commit-id", "--name-only", "-r", sha).splitlines()

    def tags(self, name: str) -> list[Version]:
        """Versions of `<name>-v<semver>` tags, lowest first."""
        prefix = f"{name}-v"
        versions = []
        for tag in self.run("tag", "-l", f"{prefix}*").splitlines():
            if SEMVER_RE.match(tag[len(prefix):]):
                versions.append(parse_version(tag[len(prefix):]))
        return sorted(versions)

    def create_tag(self, tag: str, rev: str, message: str) -> None:
        self.run("tag", "-a", tag, rev, "-m", message)

    def push(self, *refspecs: str, force: bool = False) -> None:
        self.run("push", *(["--force"] if force else []), "origin", *refspecs)

    def commit_files(self, parent: str, files: dict[str, str], message: str) -> str:
        """Create a commit on top of `parent` with `files` replaced, without touching the worktree."""
        with tempfile.TemporaryDirectory() as tmp:
            env = {"GIT_INDEX_FILE": os.path.join(tmp, "index")}
            self.run("read-tree", parent, env=env)
            for path, content in files.items():
                blob = self.run("hash-object", "-w", "--stdin", input=content).strip()
                self.run("update-index", "--cacheinfo", f"100644,{blob},{path}", env=env)
            tree = self.run("write-tree", env=env).strip()
        return self.run("commit-tree", tree, "-p", parent, "-m", message).strip()


# --- Coverage ----------------------------------------------------------------

APM_YML_RE = re.compile(r"^collections/([^/]+)/apm\.yml$")


@dataclass
class Collection:
    name: str
    data: dict

    @property
    def path(self) -> str:
        return f"collections/{self.name}/apm.yml"

    @property
    def parent_paths(self) -> list[str]:
        deps = (self.data.get("dependencies") or {}).get("apm") or []
        return [
            dep["path"].strip("/").removeprefix("./")
            for dep in deps
            if isinstance(dep, dict) and dep.get("git") == "parent" and dep.get("path")
        ]

    @property
    def coverage(self) -> list[str]:
        return [f"collections/{self.name}", *self.parent_paths]

    def covers(self, file: str) -> bool:
        return any(file == path or file.startswith(path + "/") for path in self.coverage)


class Repo:
    """Collections and their commits, read from git at specific revisions."""

    def __init__(self, git: Git):
        self.git = git
        self._collections: dict[str, dict[str, Collection]] = {}

    def collections(self, rev: str) -> dict[str, Collection]:
        sha = self.git.rev_parse(rev)
        if sha not in self._collections:
            found = {}
            for path in self.git.ls_tree(sha, "collections"):
                match = APM_YML_RE.match(path)
                if not match:
                    continue
                try:
                    data = yaml.safe_load(self.git.show(sha, path))
                except yaml.YAMLError as e:
                    raise ReleaseError(f"{path} at {sha[:7]} is not valid YAML: {e}") from e
                if not isinstance(data, dict):
                    raise ReleaseError(f"{path} at {sha[:7]} is not a mapping.")
                found[match[1]] = Collection(match[1], data)
            self._collections[sha] = found
        return self._collections[sha]

    def commits(self, name: str, rev_range: str) -> list[Commit]:
        """Commits in `rev_range` touching `name`'s coverage at that commit, oldest first."""
        commits = []
        for sha, subject in self.git.log(rev_range):
            collection = self.collections(sha).get(name)
            if collection is None or not any(collection.covers(f) for f in self.git.diff_tree(sha)):
                continue
            commit = parse_subject(subject)
            if commit is None:
                raise ReleaseError(f"Commit {sha[:7]} touches {name}: {subject_error(subject)}")
            commits.append(commit)
        return commits

    def version_at(self, name: str, rev: str) -> str | None:
        collection = self.collections(rev).get(name)
        return collection.data.get("version") if collection else None

    def last_version_change(self, name: str, rev_range: str) -> str | None:
        """The newest commit in `rev_range` that changed `name`'s version."""
        for sha, _ in reversed(self.git.log(rev_range)):
            parents = self.git.run("rev-list", "--parents", "-n1", sha).split()[1:]
            before = self.version_at(name, parents[0]) if parents else None
            if self.version_at(name, sha) != before:
                return sha
        return None


# --- Bump and notes ----------------------------------------------------------


def render_notes(commits: list[Commit]) -> str:
    groups = {
        "Breaking Changes": [c for c in commits if c.breaking],
        "Features": [c for c in commits if c.type == "feat" and not c.breaking],
        "Fixes": [c for c in commits if c.type == "fix" and not c.breaking],
    }
    lines = []
    for heading, entries in groups.items():
        if entries:
            lines.append(f"### {heading}")
            for c in entries:
                scope = f"**{c.scope}:** " if c.scope else ""
                pr = f" (#{c.pr})" if c.pr else ""
                lines.append(f"- {scope}{c.subject}{pr}")
    return "\n".join(lines)


VERSION_LINE_RE = re.compile(r"^version:[ \t]*\S+[ \t]*$", re.MULTILINE)


def set_version(text: str, version: str) -> str:
    """Replace the single top-level `version:` line, keeping everything else intact."""
    new_text, count = VERSION_LINE_RE.subn(f"version: {version}", text)
    if count != 1:
        raise ReleaseError(f"Expected exactly one top-level 'version:' line, found {count}.")
    return new_text


def tag_name(name: str, version: Version) -> str:
    return f"{name}-v{format_version(version)}"


# --- GitHub ------------------------------------------------------------------


class GitHub:
    """The only place that talks to the GitHub API, via `gh`."""

    def __init__(self, cwd: str = "."):
        self.cwd = cwd

    def _gh(self, *args: str, input: str | None = None) -> str:
        result = subprocess.run(["gh", *args], cwd=self.cwd, input=input, capture_output=True, text=True)
        if result.returncode != 0:
            raise ReleaseError(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout

    def find_release_pr(self) -> int | None:
        out = self._gh(
            "pr", "list", "--head", RELEASE_BRANCH, "--base", MAIN_BRANCH,
            "--state", "open", "--json", "number",
        )
        prs = json.loads(out)
        return prs[0]["number"] if prs else None

    def create_pr(self, title: str, body: str) -> None:
        self._gh(
            "pr", "create", "--head", RELEASE_BRANCH, "--base", MAIN_BRANCH,
            "--title", title, "--body-file", "-", input=body,
        )

    def edit_pr(self, number: int, title: str, body: str) -> None:
        self._gh("pr", "edit", str(number), "--title", title, "--body-file", "-", input=body)

    def close_pr(self, number: int) -> None:
        self._gh("pr", "close", str(number), "--delete-branch", "--comment", "No pending releases.")

    def create_release(self, tag: str, notes: str) -> None:
        self._gh("release", "create", tag, "--verify-tag", "--title", tag, "--notes-file", "-", input=notes)


# --- Commands ----------------------------------------------------------------


def check_message(message: str) -> list[str]:
    lines = [line for line in message.splitlines() if not line.startswith("#") and line.strip()]
    if not lines or lines[0].startswith(SKIPPED_MESSAGE_PREFIXES):
        return []
    return [] if parse_subject(lines[0]) else [subject_error(lines[0])]


def check_pr(git: Git, base: str, head: str, title: str) -> list[str]:
    errors = []
    commit = parse_subject(title)
    if commit is None:
        errors.append(f"PR title: {subject_error(title)}")

    repo = Repo(git)
    try:
        collections = [*repo.collections(base).values(), *repo.collections(head).values()]
    except ReleaseError as e:
        return [*errors, str(e)]

    covered = sorted({f for f in git.diff_names(base, head) for c in collections if c.covers(f)})
    if commit and covered and commit.type == "chore":
        errors.append(f"PR changes collection content ({', '.join(covered)}), so its type must be feat or fix.")
    if commit and not covered and commit.type != "chore":
        errors.append("PR changes no collection content, so its type must be chore.")

    for name, collection in repo.collections(head).items():
        if collection.data.get("name") != name:
            errors.append(f"{collection.path}: 'name' must be {name!r}.")
        try:
            parse_version(collection.data.get("version"))
        except ReleaseError as e:
            errors.append(f"{collection.path}: {e}")
        for path in collection.parent_paths:
            if not git.exists(head, path):
                errors.append(f"{collection.path}: dependency path {path!r} does not exist.")
    return errors


@dataclass
class PendingTag:
    tag: str
    rev: str
    notes: str


def release(git: Git, github: GitHub) -> list[str]:
    """Tag every collection whose version is ahead of its latest tag. Returns errors."""
    repo = Repo(git)
    head = git.rev_parse("HEAD")
    pending, errors = [], []
    for name, collection in sorted(repo.collections(head).items()):
        try:
            version = parse_version(collection.data.get("version"))
            tags = git.tags(name)
            if not tags:
                pending.append(PendingTag(tag_name(name, version), head, "Initial release."))
                continue
            latest = tags[-1]
            if version == latest:
                continue
            if version < latest:
                raise ReleaseError(f"version {format_version(version)} is lower than the latest tag.")
            latest_tag = tag_name(name, latest)
            rev = repo.last_version_change(name, f"{latest_tag}..{head}")
            if rev is None:
                raise ReleaseError(f"no commit after {latest_tag} changes the version.")
            commits = repo.commits(name, f"{latest_tag}..{rev}")
            computed = compute_bump(latest, commits)
            if computed and version < computed:
                raise ReleaseError(
                    f"commit {rev[:7]} sets version {format_version(version)}, but the commits since "
                    f"{latest_tag} require at least {format_version(computed)}."
                )
            notes = render_notes(commits) or f"Promoted to {format_version(version)}."
            pending.append(PendingTag(tag_name(name, version), rev, notes))
        except ReleaseError as e:
            errors.append(f"{name}: {e}")
    if errors:
        return errors

    for p in pending:
        git.create_tag(p.tag, p.rev, p.tag)
        git.push(f"refs/tags/{p.tag}")
        github.create_release(p.tag, p.notes)
        print(f"Released {p.tag} at {p.rev[:7]}.")
    return []


def plan(git: Git, github: GitHub) -> None:
    """Create, update or close the release PR to match pending bumps since the latest tags."""
    repo = Repo(git)
    head = git.rev_parse("HEAD")
    files, titles, sections = {}, [], []
    for name, collection in sorted(repo.collections(head).items()):
        tags = git.tags(name)
        if not tags:
            continue
        commits = repo.commits(name, f"{tag_name(name, tags[-1])}..{head}")
        target = compute_bump(tags[-1], commits)
        current = parse_version(collection.data.get("version"))
        if target is None or current >= target:
            continue
        version = format_version(target)
        files[collection.path] = set_version(git.show(head, collection.path), version)
        titles.append(f"{name} {version}")
        sections.append(f"## {name} {version}\n\n{render_notes(commits)}")

    number = github.find_release_pr()
    if not files:
        if number is not None:
            github.close_pr(number)
            print(f"Closed release PR #{number}.")
        return

    title = f"chore(release): {', '.join(titles)}"
    body = "Merging this PR tags the releases below.\n\n" + "\n\n".join(sections) + "\n"
    commit = git.commit_files(head, files, title)
    git.push(f"{commit}:refs/heads/{RELEASE_BRANCH}", force=True)
    if number is None:
        github.create_pr(title, body)
        print(f"Opened release PR: {title}")
    else:
        github.edit_pr(number, title, body)
        print(f"Updated release PR #{number}: {title}")


# --- CLI ---------------------------------------------------------------------


def report(errors: list[str]) -> int:
    # Workflow commands are read from stdout; locally errors belong on stderr.
    in_actions = bool(os.environ.get("GITHUB_ACTIONS"))
    for error in errors:
        print(("::error::" if in_actions else "error: ") + error, file=sys.stdout if in_actions else sys.stderr)
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    msg = sub.add_parser("check-message", help="Validate a commit message file or text.")
    msg.add_argument("message")
    pr = sub.add_parser("check-pr", help="Validate a PR title and the collections it changes.")
    pr.add_argument("--base", required=True)
    pr.add_argument("--head", required=True)
    pr.add_argument("--title", required=True)
    sub.add_parser("release", help="Tag collections whose version is ahead of their latest tag.")
    sub.add_parser("plan", help="Create, update or close the release PR.")
    args = parser.parse_args(argv)

    try:
        if args.command == "check-message":
            message = args.message
            if os.path.isfile(message):
                with open(message, encoding="utf-8") as f:
                    message = f.read()
            return report(check_message(message))
        if args.command == "check-pr":
            return report(check_pr(Git(), args.base, args.head, args.title))
        if args.command == "release":
            return report(release(Git(), GitHub()))
        plan(Git(), GitHub())
        return 0
    except ReleaseError as e:
        return report([str(e)])


if __name__ == "__main__":
    sys.exit(main())
