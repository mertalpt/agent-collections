#!/usr/bin/env python3
"""Checks and edits the mutable decision records kept under `intent/`.

The file format and the rules behind each check are in this skill's
`SKILL.md`. The script uses only the standard library because the pre-commit
hook runs it with `language: script` on whatever Python 3.11+ is on `PATH`;
for the same reason it validates parsed data by hand instead of with Pydantic.
"""

from __future__ import annotations

import sys

if sys.version_info < (3, 11):
    sys.exit("adr.py: needs Python 3.11 or newer")

import argparse
import os
import posixpath
import re
import subprocess
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass

CONFIG_ENV = "INTENT_CONFIG"
DEFAULT_CONFIG = "intent/config.toml"
DEFAULT_DECISIONS = "intent/decisions"

GOVERNS = "Governs"
CHANGELOG = "Changelog"
TABLE_HEADER = "| Previous version | Change |"
TABLE_RULE = "| --- | --- |"
GOVERNS_LINE = re.compile(r"^- `([^`]+)`$")
ROW_LINE = re.compile(r"^\| ([0-9a-f]{40}) \| (.*\S) \|$")
HEADING = re.compile(r"^## (.+?)\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
CODE_SPAN = re.compile(r"(`+).+?\1")
MD_PATH = re.compile(r"[\w./-]+\.md\b")


class Error(Exception):
    """A problem that stops a command, reported without a traceback."""


@dataclass(frozen=True)
class Row:
    """A changelog row.

    Attributes:
        previous: The commit that holds the record's previous version.
        summary: What the change did, as written in the table.
    """

    previous: str
    summary: str


@dataclass(frozen=True)
class Record:
    """The parts of a decision record the tooling reads.

    Attributes:
        governs: Globs for the files the decision governs.
        rows: Changelog rows, newest first.
    """

    governs: list[str]
    rows: list[Row]


@dataclass(frozen=True)
class Config:
    """Repository settings.

    Attributes:
        decisions: The decisions directory, relative to the repository root.
        canonical_branch: The ref where change sets become final, or `None`
            to use the one `origin/HEAD` points to.
        references_exclude: Globs for the files the reference check skips.
    """

    decisions: str
    canonical_branch: str | None
    references_exclude: tuple[str, ...] = ()


# Functional core: plain values in, plain values out.


def sections(lines: list[str]) -> dict[str, tuple[int, int]]:
    """Finds the `## ` sections of a Markdown document.

    Headings inside fenced code blocks are ignored.

    Args:
        lines: The document's lines.

    Returns:
        Each heading's title mapped to the half-open line range of its
        section, heading line included.

    Raises:
        Error: A heading appears twice.
    """
    found: dict[str, tuple[int, int]] = {}
    current: str | None = None
    start = 0
    fenced = False
    for i, line in enumerate(lines):
        if FENCE.match(line):
            fenced = not fenced
        match = None if fenced else HEADING.match(line)
        if match:
            if current is not None:
                found[current] = (start, i)
            current, start = match[1], i
            if current in found:
                raise Error(f"duplicate section '## {current}'")
    if current is not None:
        found[current] = (start, len(lines))
    return found


def body(lines: list[str], span: tuple[int, int]) -> list[str]:
    """Returns a section's non-blank lines, heading excluded."""
    return [line for line in lines[span[0] + 1 : span[1]] if line.strip()]


def parse_record(text: str) -> Record:
    """Parses a decision record.

    Args:
        text: The record's content.

    Returns:
        The parsed record.

    Raises:
        Error: The `Governs` or `Changelog` section is missing or malformed.
    """
    lines = text.splitlines()
    found = sections(lines)
    if GOVERNS not in found:
        raise Error(f"missing section '## {GOVERNS}'")
    governs = []
    for line in body(lines, found[GOVERNS]):
        match = GOVERNS_LINE.match(line)
        if not match:
            raise Error(f"'## {GOVERNS}' lines must look like - `glob`, got: {line}")
        glob = match[1]
        if glob.startswith("/") or "" in glob.split("/"):
            raise Error(f"glob must be a relative path without empty segments: {glob}")
        governs.append(glob)
    if not governs:
        raise Error(f"'## {GOVERNS}' lists no globs; use `**` for a cross-cutting decision")
    rows = []
    if CHANGELOG in found:
        table = body(lines, found[CHANGELOG])
        if table[:2] != [TABLE_HEADER, TABLE_RULE]:
            raise Error(f"'## {CHANGELOG}' must start with '{TABLE_HEADER}' and '{TABLE_RULE}'")
        for line in table[2:]:
            match = ROW_LINE.match(line)
            if not match:
                raise Error(f"changelog rows must be '| <full commit hash> | <summary> |', got: {line}")
            rows.append(Row(match[1], match[2]))
        if not rows:
            raise Error(f"'## {CHANGELOG}' has no rows; remove it until the first change")
        hashes = [row.previous for row in rows]
        if len(set(hashes)) != len(hashes):
            raise Error("changelog lists a commit twice")
    return Record(governs, rows)


def segment_regex(segment: str) -> str:
    """Translates one glob path segment without `**` to a regex."""
    out = []
    for char in segment:
        if char == "*":
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(char))
    return "".join(out)


def glob_regex(glob: str) -> re.Pattern[str]:
    """Compiles a glob over repository paths.

    `*` and `?` stay within one path segment; a `**` segment matches any
    number of segments.

    Args:
        glob: A glob such as `src/**` or `**/*.py`.

    Returns:
        A pattern to `fullmatch` against repository paths.
    """
    segments = glob.split("/")
    out = []
    for i, segment in enumerate(segments):
        last = i == len(segments) - 1
        if segment == "**":
            out.append(".*" if last else "(?:[^/]+/)*")
        else:
            out.append(segment_regex(segment) + ("" if last else "/"))
    return re.compile("".join(out))


def governed(globs: Iterable[str], paths: Iterable[str]) -> list[str]:
    """Returns the paths any of `globs` matches, in their original order."""
    patterns = [glob_regex(glob) for glob in globs]
    return [path for path in paths if any(p.fullmatch(path) for p in patterns)]


def escape_summary(summary: str) -> str:
    """Prepares a summary for a table cell.

    Raises:
        Error: The summary is blank or spans lines.
    """
    if not summary.strip() or "\n" in summary:
        raise Error("the summary must be one non-blank line")
    return summary.strip().replace("|", "\\|")


def with_row(text: str, base_rows: list[Row], row: Row) -> str:
    """Records a change set's row in a record's changelog.

    The row is added on top of the rows the record had at the base, or
    replaces the change set's earlier row.

    Args:
        text: The record's current content.
        base_rows: The record's rows at the base of the change set.
        row: The row to record.

    Returns:
        The record's new content.

    Raises:
        Error: The changelog has changed beyond the change set's own row.
    """
    current = parse_record(text).rows
    if current != base_rows and current[1:] != base_rows:
        raise Error("the changelog differs from the base by more than this change set's row")
    rows = [row, *base_rows]
    lines = text.splitlines()
    table = ["", TABLE_HEADER, TABLE_RULE, *(f"| {r.previous} | {r.summary} |" for r in rows)]
    span = sections(lines).get(CHANGELOG)
    if span is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["", f"## {CHANGELOG}", *table]
    else:
        tail = [""] if span[1] < len(lines) else []
        lines[span[0] : span[1]] = [f"## {CHANGELOG}", *table, *tail]
    return "\n".join(lines) + "\n"


def change_errors(record: Record, base: Record | None, changed: bool, last_touch: str | None) -> list[str]:
    """Checks a record's changelog against the base of its change set.

    Args:
        record: The record as it is now.
        base: The record at the base, or `None` if it is new.
        changed: Whether the record's content differs from the base.
        last_touch: The last commit on the canonical branch that changed the
            record, as of the base.

    Returns:
        A message for each violation.
    """
    if base is None:
        return ["a new record has no changelog rows"] if record.rows else []
    if not changed:
        return []
    errors = []
    if record.rows[1:] != base.rows:
        errors.append("rows below the newest must stay as they are at the base; add one row on top")
    if not record.rows or record.rows[0].previous != last_touch:
        errors.append(f"the newest row must be {last_touch}, the commit that holds the previous version; run `adr.py row`")
    return errors


def audit_errors(rows: list[Row], changes: list[str]) -> list[str]:
    """Checks a record's changelog against the commits that changed it.

    Args:
        rows: The record's changelog rows, newest first.
        changes: The first-parent commits that changed the record, newest
            first.

    Returns:
        A message for each row that cannot hold a previous version.
    """
    positions = {commit: i for i, commit in enumerate(changes)}
    errors = []
    newer = 0
    for row in rows:
        position = positions.get(row.previous)
        if position is None:
            errors.append(f"row {row.previous}: not a first-parent commit that changed this record")
        elif position == 0:
            errors.append(f"row {row.previous}: is the last change to this record, so it cannot hold a previous version")
        elif position <= newer:
            errors.append(f"row {row.previous}: out of order; rows must follow the history, newest first")
        else:
            newer = position
    return errors


def reference_targets(path: str, text: str) -> set[str]:
    """Returns the repository paths of Markdown files `text` refers to.

    A reference counts when it resolves relative to the referring file or
    to the repository root.

    Args:
        path: The referring file's repository path.
        text: Its content.

    Returns:
        The normalized candidate paths.
    """
    targets = set()
    for token in MD_PATH.findall(text):
        for candidate in (posixpath.join(posixpath.dirname(path), token), token.lstrip("/")):
            targets.add(posixpath.normpath(candidate))
    return targets


def without_changelog(text: str) -> str:
    """Drops the changelog, whose summaries may name deleted records."""
    lines = text.splitlines()
    span = sections(lines).get(CHANGELOG)
    if span is not None:
        del lines[span[0] : span[1]]
    return "\n".join(lines)


def without_code(text: str) -> str:
    """Drops a Markdown document's fenced code blocks and inline code."""
    kept = []
    fenced = False
    for line in text.splitlines():
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced:
            kept.append(CODE_SPAN.sub("", line))
    return "\n".join(kept)


def dangling(texts: dict[str, str], decisions: str, records: set[str]) -> list[tuple[str, str]]:
    """Finds references to records that do not exist.

    Markdown files are read without their code, so documents can show example
    record paths as code; other files are read whole.

    Args:
        texts: File contents by repository path.
        decisions: The decisions directory.
        records: The paths of the records that exist.

    Returns:
        `(referring path, missing record)` pairs, sorted.
    """
    found = set()
    for path, text in texts.items():
        if posixpath.dirname(path) == decisions:
            text = without_changelog(text)
        if path.endswith(".md"):
            text = without_code(text)
        for target in reference_targets(path, text):
            if posixpath.dirname(target) == decisions and target not in records:
                found.add((path, target))
    return sorted(found)


def parse_config(text: str | None) -> Config:
    """Parses the config file.

    Args:
        text: The file's content, or `None` when there is no file.

    Returns:
        The settings, with defaults for what the file leaves out.

    Raises:
        Error: The file is not valid TOML or has unknown or invalid keys.
    """
    data = {} if text is None else tomllib.loads(text)
    unknown = set(data) - {"canonical_branch", "decisions", "references"}
    decisions = data.get("decisions", {})
    references = data.get("references", {})
    for name, table in [("decisions", decisions), ("references", references)]:
        if not isinstance(table, dict):
            raise Error(f"config: `{name}` must be a table")
    unknown |= {f"decisions.{key}" for key in set(decisions) - {"path"}}
    unknown |= {f"references.{key}" for key in set(references) - {"exclude"}}
    if unknown:
        raise Error(f"config: unknown keys: {', '.join(sorted(unknown))}")
    branch = data.get("canonical_branch")
    path = decisions.get("path", DEFAULT_DECISIONS)
    exclude = references.get("exclude", [])
    if branch is not None and (not isinstance(branch, str) or not branch):
        raise Error("config: `canonical_branch` must be a non-empty string")
    if not isinstance(path, str) or not path:
        raise Error("config: `decisions.path` must be a non-empty string")
    path = posixpath.normpath(path)
    if path.startswith("/") or path == ".." or path.startswith("../"):
        raise Error("config: `decisions.path` must be inside the repository")
    if not isinstance(exclude, list) or not all(isinstance(glob, str) and glob for glob in exclude):
        raise Error("config: `references.exclude` must be a list of non-empty strings")
    return Config(path, branch, tuple(exclude))


# Imperative shell: git and the file system.


def git(*args: str, ok: tuple[int, ...] = (0,)) -> str:
    """Runs git in the current directory.

    Args:
        *args: The git arguments.
        ok: The exit codes that count as success.

    Returns:
        Standard output.

    Raises:
        Error: Git exited with another code.
    """
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if result.returncode not in ok:
        raise Error(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def show(rev: str, path: str) -> str | None:
    """Returns a file's content at `rev`, or `None` if it does not exist there."""
    result = subprocess.run(["git", "show", f"{rev}:{path}"], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


def config_path() -> str:
    """Returns the config file's path, relative to the repository root when it is inside it."""
    path = os.environ.get(CONFIG_ENV) or DEFAULT_CONFIG
    if os.path.isabs(path):
        relative = os.path.relpath(path)
        return path if relative.startswith("..") else relative.replace(os.sep, "/")
    return posixpath.normpath(path)


def load_config(path: str) -> Config:
    """Reads the config file, which only an explicit `INTENT_CONFIG` requires."""
    if not os.path.exists(path):
        if os.environ.get(CONFIG_ENV):
            raise Error(f"{CONFIG_ENV} points to {path}, which does not exist")
        return parse_config(None)
    with open(path, encoding="utf-8") as f:
        try:
            return parse_config(f.read())
        except tomllib.TOMLDecodeError as e:
            raise Error(f"config: {path}: {e}") from e


def canonical(config: Config) -> str:
    """Returns the canonical branch's ref.

    Raises:
        Error: It is not configured and `origin/HEAD` is not set, or the ref
            does not exist.
    """
    ref = config.canonical_branch
    if ref is None:
        ref = git("symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD", ok=(0, 1)).strip()
        if not ref:
            raise Error(
                "cannot tell the canonical branch: origin/HEAD is not set; "
                "set `canonical_branch` in the config, or run `git remote set-head origin --auto`"
            )
    if not git("rev-parse", "--verify", "-q", f"{ref}^{{commit}}", ok=(0, 1)).strip():
        raise Error(f"canonical branch {ref} does not exist here; fetch it")
    return ref


def list_records(decisions: str) -> list[str]:
    """Returns the record paths in the working tree.

    Raises:
        Error: There are none, which in a repository that runs the hook
            means the location is misconfigured.
    """
    names = sorted(os.listdir(decisions)) if os.path.isdir(decisions) else []
    records = [f"{decisions}/{name}" for name in names if name.endswith(".md")]
    if not records:
        raise Error(f"no decision records found at {decisions}/; create one, or set {CONFIG_ENV}")
    return records


def read(path: str) -> str:
    """Reads a file from the working tree."""
    with open(path, encoding="utf-8") as f:
        return f.read()


def last_touch(base: str, path: str) -> str:
    """Returns the last first-parent commit up to `base` that changed `path`."""
    return git("log", "--first-parent", "-1", "--format=%H", base, "--", path).strip()


def repo_path(path: str, root: str) -> str:
    """Converts an absolute path to a repository path."""
    return os.path.relpath(path, root).replace(os.sep, "/")


def check(config: Config, conf_path: str, base: str) -> list[str]:
    """Runs every check and returns the violations."""
    records = list_records(config.decisions)
    errors = []
    files = git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()
    for path in records:
        text = read(path)
        try:
            record = parse_record(text)
        except Error as e:
            errors.append(f"{path}: {e}")
            continue
        for glob in record.governs:
            if not governed([glob], files):
                errors.append(f"{path}: glob matches no file: {glob}")
        base_text = show(base, path)
        base_record = None
        if base_text is None:
            if git("log", "-1", "--format=%H", base, "--", path).strip():
                errors.append(f"{path}: this slug was used before; pick a new one")
        else:
            try:
                base_record = parse_record(base_text)
            except Error as e:
                errors.append(f"{path}: cannot parse the version at the base: {e}")
                continue
        touch = last_touch(base, path) if base_text is not None else None
        errors += [f"{path}: {e}" for e in change_errors(record, base_record, text != base_text, touch)]
    name = posixpath.basename(config.decisions)
    for glob in config.references_exclude:
        if not governed([glob], files):
            errors.append(f"{conf_path}: references.exclude glob matches no file: {glob}")
        for path in governed([glob], records):
            errors.append(f"{conf_path}: references.exclude glob matches a record: {glob}: {path}")
    mentioning = git("grep", "-l", "-I", "--untracked", "-F", "-e", name, ok=(0, 1)).splitlines()
    mentioning = [path for path in mentioning if not governed(config.references_exclude, [path])]
    texts = {path: read(path) for path in {*mentioning, *records} if os.path.isfile(path)}
    for path, target in dangling(texts, config.decisions, set(records)):
        errors.append(f"{path}: refers to {target}, which does not exist")
    base_conf = show(base, conf_path) if not os.path.isabs(conf_path) else None
    old = parse_config(base_conf).decisions
    if old != config.decisions and any(
        name.endswith(".md") for name in git("ls-tree", "--name-only", base, f"{old}/").splitlines()
    ):
        errors.append(f"{conf_path}: decisions moved from {old}/ while it holds records; moving them is not supported")
    return errors


def audit(config: Config) -> list[str]:
    """Checks every committed record's changelog against its whole history."""
    names = git("ls-tree", "--name-only", "HEAD", f"{config.decisions}/").splitlines()
    records = sorted(name for name in names if name.endswith(".md"))
    if not records:
        raise Error(f"no decision records committed at {config.decisions}/; create one, or set {CONFIG_ENV}")
    errors = []
    for path in records:
        try:
            rows = parse_record(git("show", f"HEAD:{path}")).rows
        except Error as e:
            errors.append(f"{path}: {e}")
            continue
        changes = git("log", "--first-parent", "--format=%H", "HEAD", "--", path).split()
        errors += [f"{path}: {e}" for e in audit_errors(rows, changes)]
    return errors


def main(argv: list[str] | None = None) -> int:
    """Runs a command.

    Args:
        argv: The arguments, without the program name.

    Returns:
        The exit code.
    """
    parser = argparse.ArgumentParser(prog="adr.py", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="check every record against the base of the change set")
    row = commands.add_parser("row", help="record this change set's changelog row in a record")
    row.add_argument("record", help="path to the record")
    row.add_argument("--summary", required=True, help="what the change does to the record")
    affected = commands.add_parser("affected", help="list the records that govern the given files")
    affected.add_argument("paths", nargs="*", help="files to look up; defaults to those changed since the base")
    commands.add_parser("audit", help="check every committed record's changelog against its whole history")
    args = parser.parse_args(argv)
    try:
        given = [os.path.abspath(p) for p in ([args.record] if args.command == "row" else getattr(args, "paths", []))]
        root = git("rev-parse", "--show-toplevel").strip()
        os.chdir(root)
        given = [repo_path(p, root) for p in given]
        conf_path = config_path()
        config = load_config(conf_path)
        if args.command == "audit":
            errors = audit(config)
            for error in errors:
                print(error, file=sys.stderr)
            return 1 if errors else 0
        base = git("merge-base", "HEAD", canonical(config)).strip()
        if args.command == "check":
            errors = check(config, conf_path, base)
            for error in errors:
                print(error, file=sys.stderr)
            return 1 if errors else 0
        if args.command == "row":
            record_arg = given[0]
            base_text = show(base, record_arg)
            if base_text is None:
                raise Error(f"{record_arg} is new in this change set, and new records have no changelog")
            row_value = Row(last_touch(base, record_arg), escape_summary(args.summary))
            text = with_row(read(record_arg), parse_record(base_text).rows, row_value)
            with open(record_arg, "w", encoding="utf-8") as f:
                f.write(text)
            return 0
        records = list_records(config.decisions)
        paths = given or sorted(
            {
                *git("diff", "--name-only", "--no-renames", base).splitlines(),
                *git("ls-files", "--others", "--exclude-standard").splitlines(),
            }
        )
        for path in records:
            if governed(parse_record(read(path)).governs, paths):
                print(path)
        return 0
    except Error as e:
        print(f"adr.py: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
