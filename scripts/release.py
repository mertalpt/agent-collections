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

TYPES = ("feat", "fix", "chore")
SUBJECT_RE = re.compile(
    r"^(?P<type>[a-z]+)"
    r"(?:\((?P<scope>[^()\s]+)\))?"
    r"(?P<breaking>!)?"
    r": (?P<subject>\S.*?)"
    r"(?: \(#(?P<pr>\d+)\))?$"
)
# Subjects git generates itself, for merges, `git revert` and `git commit --fixup/--squash`.
SKIPPED_MESSAGE_PREFIXES = ("Merge ", 'Revert "', "fixup! ", "squash! ", "amend! ")

SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
APM_YML_RE = re.compile(r"^collections/([^/]+)/apm\.yml$")
VERSION_LINE_RE = re.compile(r"^version:[ \t]*\S+[ \t]*$", re.MULTILINE)

Version = tuple[int, int, int]


class ReleaseError(Exception):
    """An expected failure, reported to the user without a traceback."""


@dataclass(frozen=True)
class Commit:
    """A parsed commit subject or PR title.

    Attributes:
        type: One of `TYPES`.
        scope: The optional scope, e.g. a primitive name.
        breaking: Whether the subject has `!`.
        subject: The description, without the trailing PR number.
        pr: The PR number GitHub appends to squash commits, if present.
    """

    type: str
    scope: str | None
    breaking: bool
    subject: str
    pr: int | None


class Git:
    """Thin wrapper around the `git` CLI for one repository."""

    def __init__(self, cwd: str = "."):
        """Initializes the wrapper.

        Args:
            cwd: Path to the repository's working tree.
        """
        self.cwd = cwd

    def run(self, *args: str, input: str | None = None, env: dict | None = None) -> str:
        """Runs a git command.

        Args:
            *args: Arguments after `git`.
            input: Text passed on stdin.
            env: Extra environment variables.

        Returns:
            The command's stdout.

        Raises:
            ReleaseError: If the command fails.
        """
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
        """Returns the commit SHA that `rev` points to."""
        return self.run("rev-parse", "--verify", f"{rev}^{{commit}}").strip()

    def show(self, rev: str, path: str) -> str:
        """Returns the content of `path` at `rev`."""
        return self.run("show", f"{rev}:{path}")

    def exists(self, rev: str, path: str) -> bool:
        """Returns whether `path` (file or directory) exists at `rev`."""
        return bool(self.run("ls-tree", rev, "--", path).strip())

    def ls_tree(self, rev: str, path: str) -> list[str]:
        """Returns every file under `path` at `rev`."""
        return self.run("ls-tree", "-r", "--name-only", rev, "--", path).splitlines()

    def diff_names(self, base: str, head: str) -> list[str]:
        """Returns the files changed on `head` since it diverged from `base`."""
        return self.run("diff", "--name-only", f"{base}...{head}").splitlines()

    def log(self, rev_range: str) -> list[tuple[str, str]]:
        """Returns the commits in `rev_range` as (sha, subject), oldest first."""
        out = self.run("log", "--reverse", "--format=%H%x00%s", rev_range)
        return [tuple(line.split("\0", 1)) for line in out.splitlines()]

    def diff_tree(self, sha: str) -> list[str]:
        """Returns the files changed by commit `sha`."""
        return self.run("diff-tree", "--root", "--no-commit-id", "--name-only", "-r", sha).splitlines()

    def parent(self, sha: str) -> str | None:
        """Returns the first parent of `sha`, or None for a root commit."""
        parents = self.run("rev-list", "--parents", "-n1", sha).split()[1:]
        return parents[0] if parents else None

    def tags(self, name: str) -> list[Version]:
        """Returns the versions of `<name>-v<semver>` tags, lowest first."""
        prefix = f"{name}-v"
        suffixes = [tag[len(prefix):] for tag in self.run("tag", "-l", f"{prefix}*").splitlines()]
        return sorted(parse_version(s) for s in suffixes if SEMVER_RE.match(s))

    def create_tag(self, tag: str, rev: str, message: str) -> None:
        """Creates an annotated tag."""
        self.run("tag", "-a", tag, rev, "-m", message)

    def push(self, *refspecs: str, force: bool = False) -> None:
        """Pushes `refspecs` to `origin`."""
        self.run("push", *(["--force"] if force else []), "origin", *refspecs)

    def commit_files(self, parent: str, files: dict[str, str], message: str) -> str:
        """Creates a commit without touching the working tree or the current branch.

        Args:
            parent: The commit to build on.
            files: New content by path. Other files are kept as in `parent`.
            message: The commit message.

        Returns:
            The new commit's SHA.
        """
        with tempfile.TemporaryDirectory() as tmp:
            env = {"GIT_INDEX_FILE": os.path.join(tmp, "index")}
            self.run("read-tree", parent, env=env)
            for path, content in files.items():
                blob = self.run("hash-object", "-w", "--stdin", input=content).strip()
                self.run("update-index", "--cacheinfo", f"100644,{blob},{path}", env=env)
            tree = self.run("write-tree", env=env).strip()
        return self.run("commit-tree", tree, "-p", parent, "-m", message).strip()


@dataclass
class Collection:
    """A collection's `apm.yml` at some revision.

    Attributes:
        name: The collection's directory name.
        data: The parsed `apm.yml`.
    """

    name: str
    data: dict

    @property
    def path(self) -> str:
        """The repository path of the collection's `apm.yml`."""
        return f"collections/{self.name}/apm.yml"

    @property
    def parent_paths(self) -> list[str]:
        """The `path` of every `git: parent` dependency, normalized."""
        deps = (self.data.get("dependencies") or {}).get("apm") or []
        parent_deps = [d for d in deps if isinstance(d, dict) and d.get("git") == "parent" and d.get("path")]
        return [d["path"].strip("/").removeprefix("./") for d in parent_deps]

    @property
    def coverage(self) -> list[str]:
        """The paths whose changes belong to this collection."""
        return [f"collections/{self.name}", *self.parent_paths]

    def covers(self, file: str) -> bool:
        """Returns whether `file` is one of the coverage paths or inside one."""
        return any(file == path or file.startswith(path + "/") for path in self.coverage)


class Repo:
    """Collections and their commits, read from git at specific revisions."""

    def __init__(self, git: Git):
        """Initializes the reader.

        Args:
            git: The repository to read from.
        """
        self.git = git
        self._collections: dict[str, dict[str, Collection]] = {}

    def collections(self, rev: str) -> dict[str, Collection]:
        """Returns the collections at `rev`, by name.

        Raises:
            ReleaseError: If an `apm.yml` isn't a valid YAML mapping.
        """
        sha = self.git.rev_parse(rev)
        if sha in self._collections:
            return self._collections[sha]

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
        return found

    def commits(self, name: str, rev_range: str) -> list[Commit]:
        """Returns the commits in `rev_range` that touch a collection, oldest first.

        Coverage is read at each commit, so a change to a primitive only counts
        once the collection uses it.

        Args:
            name: The collection's name.
            rev_range: A git revision range, e.g. `common-v0.1.0..HEAD`.

        Raises:
            ReleaseError: If a commit touching the collection has an invalid subject.
        """
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

    def version_at(self, name: str, rev: str | None) -> str | None:
        """Returns the collection's raw `version` at `rev`, or None if it doesn't exist."""
        if rev is None:
            return None
        collection = self.collections(rev).get(name)
        return collection.data.get("version") if collection else None

    def last_version_change(self, name: str, rev_range: str) -> str | None:
        """Returns the newest commit in `rev_range` that changed the collection's version."""
        for sha, _ in reversed(self.git.log(rev_range)):
            if self.version_at(name, sha) != self.version_at(name, self.git.parent(sha)):
                return sha
        return None


class GitHub:
    """The only place that talks to the GitHub API, via `gh`."""

    def __init__(self, cwd: str = "."):
        """Initializes the adapter.

        Args:
            cwd: Path inside the repository, so `gh` picks the right one.
        """
        self.cwd = cwd

    def _gh(self, *args: str, input: str | None = None) -> str:
        """Runs a `gh` command and returns its stdout.

        Raises:
            ReleaseError: If the command fails.
        """
        result = subprocess.run(["gh", *args], cwd=self.cwd, input=input, capture_output=True, text=True)
        if result.returncode != 0:
            raise ReleaseError(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout

    def find_release_pr(self) -> int | None:
        """Returns the number of the open release PR, if any."""
        out = self._gh(
            "pr", "list", "--head", RELEASE_BRANCH, "--base", MAIN_BRANCH,
            "--state", "open", "--json", "number",
        )
        prs = json.loads(out)
        return prs[0]["number"] if prs else None

    def create_pr(self, title: str, body: str) -> None:
        """Opens the release PR from `RELEASE_BRANCH`."""
        self._gh(
            "pr", "create", "--head", RELEASE_BRANCH, "--base", MAIN_BRANCH,
            "--title", title, "--body-file", "-", input=body,
        )

    def edit_pr(self, number: int, title: str, body: str) -> None:
        """Replaces the title and body of PR `number`."""
        self._gh("pr", "edit", str(number), "--title", title, "--body-file", "-", input=body)

    def close_pr(self, number: int) -> None:
        """Closes PR `number` and deletes its branch."""
        self._gh("pr", "close", str(number), "--delete-branch", "--comment", "No pending releases.")

    def create_release(self, tag: str, notes: str) -> None:
        """Publishes a GitHub Release for an existing, pushed tag."""
        self._gh("release", "create", tag, "--verify-tag", "--title", tag, "--notes-file", "-", input=notes)


@dataclass
class PendingTag:
    """A tag `release` will create once every check has passed.

    Attributes:
        tag: The tag name, e.g. `common-v0.2.0`.
        rev: The commit to tag.
        notes: The GitHub Release notes.
    """

    tag: str
    rev: str
    notes: str


def parse_subject(line: str) -> Commit | None:
    """Parses a commit subject or PR title.

    Args:
        line: The subject, e.g. `feat(to-file)!: drop the legacy layout (#21)`.

    Returns:
        The parsed commit, or None if the subject doesn't follow the conventions.
    """
    match = SUBJECT_RE.match(line.strip())
    if not match or match["type"] not in TYPES:
        return None
    breaking = match["breaking"] is not None
    if breaking and match["type"] == "chore":
        return None
    pr = int(match["pr"]) if match["pr"] else None
    return Commit(match["type"], match["scope"], breaking, match["subject"], pr)


def subject_error(line: str) -> str:
    """Returns the error message for an invalid subject."""
    return (
        f"Invalid subject {line!r}. Expected '<type>[(<scope>)][!]: <subject>' "
        f"with type one of {', '.join(TYPES)}; '!' only on feat and fix."
    )


def parse_version(value: object) -> Version:
    """Parses a strict `X.Y.Z` version.

    Raises:
        ReleaseError: If `value` isn't a string in `X.Y.Z` form.
    """
    if not isinstance(value, str) or not SEMVER_RE.match(value):
        raise ReleaseError(f"Invalid version {value!r}. Expected X.Y.Z.")
    major, minor, patch = (int(part) for part in value.split("."))
    return major, minor, patch


def format_version(version: Version) -> str:
    """Formats a version as `X.Y.Z`."""
    return ".".join(str(part) for part in version)


def tag_name(name: str, version: Version) -> str:
    """Returns the tag for a collection version, e.g. `common-v0.2.0`."""
    return f"{name}-v{format_version(version)}"


def compute_bump(current: Version, commits: list[Commit]) -> Version | None:
    """Applies the highest-impact commit to a version.

    `0.x` versions treat breaking changes as minor, so they never reach `1.0.0`
    on their own.

    Args:
        current: The latest released version.
        commits: The commits since that release.

    Returns:
        The next version, or None if no commit calls for a release.
    """
    major, minor, patch = current
    if any(c.breaking for c in commits):
        return (major + 1, 0, 0) if major > 0 else (0, minor + 1, 0)
    if any(c.type == "feat" for c in commits):
        return major, minor + 1, 0
    if any(c.type == "fix" for c in commits):
        return major, minor, patch + 1
    return None


def render_notes(commits: list[Commit]) -> str:
    """Renders release notes grouped by impact, oldest first, without empty groups."""
    groups = {
        "Breaking Changes": [c for c in commits if c.breaking],
        "Features": [c for c in commits if c.type == "feat" and not c.breaking],
        "Fixes": [c for c in commits if c.type == "fix" and not c.breaking],
    }
    lines = []
    for heading, entries in groups.items():
        if not entries:
            continue
        lines.append(f"### {heading}")
        for c in entries:
            scope = f"**{c.scope}:** " if c.scope else ""
            pr = f" (#{c.pr})" if c.pr else ""
            lines.append(f"- {scope}{c.subject}{pr}")
    return "\n".join(lines)


def set_version(text: str, version: str) -> str:
    """Replaces the single top-level `version:` line, keeping everything else intact.

    Raises:
        ReleaseError: If there isn't exactly one top-level `version:` line.
    """
    new_text, count = VERSION_LINE_RE.subn(f"version: {version}", text)
    if count != 1:
        raise ReleaseError(f"Expected exactly one top-level 'version:' line, found {count}.")
    return new_text


def check_message(message: str) -> list[str]:
    """Checks a commit message's subject line.

    Args:
        message: The full message. `#` comment lines are ignored, as git does.

    Returns:
        Error messages; empty if the message is valid or generated by git.
    """
    lines = [line for line in message.splitlines() if not line.startswith("#") and line.strip()]
    if not lines or lines[0].startswith(SKIPPED_MESSAGE_PREFIXES):
        return []
    return [] if parse_subject(lines[0]) else [subject_error(lines[0])]


def check_pr(git: Git, base: str, head: str, title: str) -> list[str]:
    """Checks a PR's title against its changes, and the collections at its head.

    Args:
        git: The repository.
        base: The PR's base commit.
        head: The PR's head commit.
        title: The PR title, which becomes the squash commit subject.

    Returns:
        Error messages; empty if the PR is valid.
    """
    errors = []
    commit = parse_subject(title)
    if commit is None:
        errors.append(f"PR title: {subject_error(title)}")

    repo = Repo(git)
    try:
        collections = [*repo.collections(base).values(), *repo.collections(head).values()]
    except ReleaseError as e:
        return [*errors, str(e)]

    # Base coverage catches files of collections the PR deletes.
    covered = sorted({f for f in git.diff_names(base, head) for c in collections if c.covers(f)})
    if commit and covered and commit.type == "chore":
        errors.append(f"PR changes collection content ({', '.join(covered)}), so its type must be feat or fix.")
    if commit and not covered and commit.type != "chore":
        errors.append("PR changes no collection content, so its type must be chore.")

    for name, collection in repo.collections(head).items():
        errors.extend(check_collection(git, head, name, collection))
    return errors


def check_collection(git: Git, rev: str, name: str, collection: Collection) -> list[str]:
    """Checks a collection's `apm.yml` at `rev`.

    Returns:
        Error messages; empty if the collection is valid.
    """
    errors = []
    if collection.data.get("name") != name:
        errors.append(f"{collection.path}: 'name' must be {name!r}.")
    try:
        parse_version(collection.data.get("version"))
    except ReleaseError as e:
        errors.append(f"{collection.path}: {e}")
    for path in collection.parent_paths:
        if not git.exists(rev, path):
            errors.append(f"{collection.path}: dependency path {path!r} does not exist.")
    return errors


def covered_files(git: Git, rev: str) -> list[str]:
    """Returns every file at `rev` that some collection covers."""
    collections = Repo(git).collections(rev).values()
    return [f for f in git.ls_tree(rev, ".") if any(c.covers(f) for c in collections)]


def pending_tag(repo: Repo, head: str, collection: Collection) -> PendingTag | None:
    """Works out whether a collection needs a new tag.

    A collection with no tags is tagged at `head`. A collection whose version is
    ahead of its latest tag is tagged at the commit that changed the version,
    not at `head`, so re-runs tag exactly what was released.

    Args:
        repo: The repository.
        head: The commit being released from.
        collection: The collection at `head`.

    Returns:
        The tag to create, or None if the collection is up to date.

    Raises:
        ReleaseError: If the version is invalid, lower than the latest tag, or
            lower than the commits since the latest tag require.
    """
    name = collection.name
    version = parse_version(collection.data.get("version"))
    tags = repo.git.tags(name)
    if not tags:
        return PendingTag(tag_name(name, version), head, "Initial release.")
    latest = tags[-1]
    if version == latest:
        return None
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
    return PendingTag(tag_name(name, version), rev, notes)


def release(git: Git, github: GitHub) -> list[str]:
    """Tags and publishes every collection that needs it.

    Every collection is checked before any tag is created, so a failed check
    creates no tags.

    Args:
        git: The repository, with `HEAD` at the pushed commit.
        github: The GitHub adapter.

    Returns:
        Error messages; empty if everything was released.
    """
    repo = Repo(git)
    head = git.rev_parse("HEAD")
    pending, errors = [], []
    for name, collection in sorted(repo.collections(head).items()):
        try:
            tag = pending_tag(repo, head, collection)
        except ReleaseError as e:
            errors.append(f"{name}: {e}")
            continue
        if tag:
            pending.append(tag)
    if errors:
        return errors

    for p in pending:
        git.create_tag(p.tag, p.rev, p.tag)
        git.push(f"refs/tags/{p.tag}")
        github.create_release(p.tag, p.notes)
        print(f"Released {p.tag} at {p.rev[:7]}.")
    return []


def plan(git: Git, github: GitHub) -> None:
    """Creates, updates or closes the release PR to match pending bumps.

    Target versions come from the latest tags, never from `apm.yml`, so a bad
    release commit is corrected by the next release PR.

    Args:
        git: The repository, with `HEAD` at the pushed commit.
        github: The GitHub adapter.
    """
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
    if not files and number is None:
        return
    if not files:
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
        return
    github.edit_pr(number, title, body)
    print(f"Updated release PR #{number}: {title}")


def report(errors: list[str]) -> int:
    """Prints errors, as GitHub annotations when running in Actions.

    Returns:
        The process exit code.
    """
    # Workflow commands are read from stdout; locally errors belong on stderr.
    in_actions = bool(os.environ.get("GITHUB_ACTIONS"))
    for error in errors:
        print(("::error::" if in_actions else "error: ") + error, file=sys.stdout if in_actions else sys.stderr)
    return 1 if errors else 0


def read_message(arg: str) -> str:
    """Returns the content of `arg` if it's a file, otherwise `arg` itself."""
    if not os.path.isfile(arg):
        return arg
    with open(arg, encoding="utf-8") as f:
        return f.read()


def main(argv: list[str] | None = None) -> int:
    """Runs the command line interface.

    Returns:
        The process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    msg = sub.add_parser("check-message", help="Validate a commit message file or text.")
    msg.add_argument("message")
    pr = sub.add_parser("check-pr", help="Validate a PR title and the collections it changes.")
    pr.add_argument("--base", required=True)
    pr.add_argument("--head", required=True)
    pr.add_argument("--title", required=True)
    sub.add_parser("covered-files", help="List files covered by any collection at HEAD.")
    sub.add_parser("release", help="Tag collections whose version is ahead of their latest tag.")
    sub.add_parser("plan", help="Create, update or close the release PR.")
    args = parser.parse_args(argv)

    try:
        if args.command == "check-message":
            return report(check_message(read_message(args.message)))
        if args.command == "check-pr":
            return report(check_pr(Git(), args.base, args.head, args.title))
        if args.command == "covered-files":
            print("\n".join(covered_files(Git(), "HEAD")))
            return 0
        if args.command == "release":
            return report(release(Git(), GitHub()))
        plan(Git(), GitHub())
        return 0
    except ReleaseError as e:
        return report([str(e)])


if __name__ == "__main__":
    sys.exit(main())
