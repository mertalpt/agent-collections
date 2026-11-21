---
name: ci-juju-integration-triage
description: "Extract the root cause from Juju charm integration-test runs in GitHub Actions. Use when given a GitHub Actions job or run URL, or asked why a charm's tox, pytest, or Juju integration CI failed."
---

# Juju integration CI triage

Find the earliest actionable failure, not merely the last error printed. GitHub Actions
logs can exceed 100,000 lines, and their tail is often cleanup or Juju debug noise.

Cache artifacts under
`/tmp/ci-juju-integration-triage/{owner}/{repo}/{job_id}/`. Namespacing by owner avoids
collisions between repositories with the same name, while the job ID keeps every
investigation self-contained. Before any command that creates a file, check whether
its destination already exists. Reuse a complete existing file; otherwise choose a
different path. Never overwrite an unknown file.

## 1. Resolve the URL

Extract `owner`, `repo`, and the numeric identifier from the URL.

- Job URL (`.../actions/runs/<run_id>/job/<job_id>`): inspect the job directly.
- Run URL (`.../actions/runs/<run_id>`): list its jobs and identify the failed job and
  step before downloading logs.

```sh
gh api repos/{owner}/{repo}/actions/jobs/{job_id}
gh api repos/{owner}/{repo}/actions/runs/{run_id}/jobs --paginate
```

Confirm that `gh` is authenticated and has access. Do not confuse the run ID with the
job ID.

## 2. Fetch once, to a file

Create the namespaced cache directory if needed, then reuse a non-empty cached log.
Write downloads to a temporary sibling and rename only after success, so an interrupted
fetch cannot masquerade as a complete cache entry:

```sh
cache_dir=/tmp/ci-juju-integration-triage/{owner}/{repo}/{job_id}
test -d "$cache_dir" || mkdir -p "$cache_dir"
if test -s "$cache_dir/full.log"; then
  echo "Reusing $cache_dir/full.log"
elif test -e "$cache_dir/full.log" || test -e "$cache_dir/full.log.part"; then
  echo "Refusing to overwrite an incomplete or unknown cached log" >&2
  exit 1
else
  gh run view --job {job_id} --log --repo {owner}/{repo} \
    > "$cache_dir/full.log.part" \
    && mv "$cache_dir/full.log.part" "$cache_dir/full.log"
fi
```

Always redirect the unfiltered response to a file. Fetching may take several minutes;
wait for completion and do not retry while it is running. Verify that the file is
non-empty before continuing.

## 3. Normalize once

Each line usually starts with `job-name<TAB>step-name<TAB>`. Strip those two fields but
retain timestamps, then remove ANSI escape sequences. Reuse a non-empty normalized
log, and use the same non-overwriting atomic-write pattern when creating it.

```sh
if test -s "$cache_dir/clean.log"; then
  echo "Reusing $cache_dir/clean.log"
elif test -e "$cache_dir/clean.log" || test -e "$cache_dir/clean.log.part"; then
  echo "Refusing to overwrite an incomplete or unknown normalized log" >&2
  exit 1
else
  sed -E 's/^[^\t]+\t[^\t]+\t//' "$cache_dir/full.log" \
    | perl -pe 's/\e\[[0-9;?]*[ -\/]*[@-~]//g' \
    > "$cache_dir/clean.log.part" \
    && mv "$cache_dir/clean.log.part" "$cache_dir/clean.log"
fi
```

Escapes may survive, so search for substrings rather than anchoring patterns at the
start of a line. Limit displayed width with `cut -c1-240`; long Juju lines consume far
more context than their line count suggests.

## 4. Locate the failing test environment

Index structural markers before reading any large section:

```sh
grep -nE 'test session starts|short test summary info|install_deps>|exit [01] ' \
  "$cache_dir/clean.log" | cut -c1-240
```

Use the markers that answer the immediate question:

- To identify the failed tox environment, pair its `install_deps>` marker with its
  `exit 1 (...)`. Setup and lint environments may precede integration tests.
- To inspect pytest, select the `test session starts` through `short test summary info`
  pair belonging to that failed environment. Prefer this narrower window.
- If pytest aborted before its summary, end at the tox failure marker instead.

Do not blindly choose the final marker pair: cleanup commands or later environments
may run after the failure. Check the proposed boundaries with a small window before
extracting them.

Include the selected line range in the filename so later investigations can retain
different slices. After checking that the destination is absent, create it atomically:

```sh
slice="$cache_dir/slice-{start}-{end}.log"
if test -s "$slice"; then
  echo "Reusing $slice"
elif test -e "$slice" || test -e "$slice.part"; then
  echo "Refusing to overwrite an incomplete or unknown slice" >&2
  exit 1
else
  sed -n '{start},{end}p' "$cache_dir/clean.log" > "$slice.part" \
    && mv "$slice.part" "$slice"
fi
```

## 5. Build an evidence index

Do not page sequentially through the slice. Search semantic markers, then inspect only
small windows around relevant hits:

```sh
grep -niE 'FAILED|ERROR|Traceback|Exception|assert|timed out|Invalid configuration|status-set' \
  "$slice" | cut -c1-240
grep -nE '=+ short test summary info =+|[0-9]+ failed|exit 1 ' \
  "$slice" | cut -c1-240
```

Extend the index with exact exception names, statuses, hook tools, endpoints, and log
messages found in the failing code. Read roughly 10-150 lines around each useful hit.

Use negative and quantitative evidence carefully:

- Absence matters only when the log window covers the event and the code always emits
  the expected marker on that path.
- Counts can distinguish branches; use `grep -c` for repeated requests, hooks, or
  status transitions.
- Captured `juju debug-log --limit N` output omits old events, so absence near its
  beginning proves nothing.

## 6. Reconstruct the timeline

GitHub concatenates output by step, while pytest may print captured Juju logs during
teardown. The same event can therefore appear twice and file order may not be event
order. Correlate timestamps instead.

```sh
grep -niE 'cli: juju (deploy|integrate|config|grant-secret|add-secret)|PASSED|FAILED|ERROR unit|jujuc running hook tool' \
  "$slice" | cut -c1-240
```

Put test commands, assertions, workload events, and hook activity on one clock. Pytest
live logs may have sub-second precision while Juju logs have second precision; use the
more precise timestamp to order events within the same second.

For Juju, hook-tool sequences expose control flow even without application logs. For
example, `is-leader` then `relation-get` followed by no mutation or status update may
indicate an early return; `relation-set` followed by `status-set` indicates a completed
success path. Verify such interpretations against the workload code when available.

## 7. Trace symptom to cause

The final pytest exception is often only a symptom. A `NoneType` access, for example,
shows that a lookup returned nothing but not why. Work backward from the failing frame
to the workload decision, request, hook, or missing post-condition.

- Read the final exception and the last one or two frames in repository-owned code.
- Check client-library error semantics before interpreting return values. A 404 may
  return `None` while authentication failures raise exceptions.
- Compare expected and observed workload logs, hook tools, statuses, and request counts.
- Treat unrelated application errors as leads, not causes, unless timing and control
  flow connect them to the assertion.

## 8. Classify and compare

Choose the best-supported failure class before recommending a fix:

- **Product defect:** workload code logged an error or took an incorrect branch.
- **Test race:** the expected work completed after the assertion. A common signature is
  an active/idle window between two hooks, with the post-condition established by the
  second hook. Poll the actual post-condition rather than status alone.
- **Test or fixture ordering:** setup performs operations in an order the product cannot
  satisfy.
- **Environment or dependency drift:** a floating charm channel, image, package, or
  external service changed.
- **Infrastructure failure:** setup failed before meaningful product behavior ran.

Check recent default-branch runs for a baseline:

```sh
gh run list --repo {owner}/{repo} --branch main --limit 5 \
  --json databaseId,displayTitle,conclusion,createdAt
```

A green baseline supports branch causation; a red baseline supports a pre-existing or
environmental failure. Neither proves causation by itself.

## 9. Report and retain the cache

Report, in this order:

1. Pytest summary and failing node ID.
2. Root cause in one sentence, or the narrowest proven conclusion.
3. Final exception and the last one or two repository-owned frames.
4. A compact timestamp table when ordering or timing matters.
5. Failure class and the evidence supporting it.
6. Separate **Proved** from **Inferred**. If unresolved, name the exact missing evidence
   or log line that would decide between the remaining hypotheses.

Do not dump broad log sections or pytest/pluggy internals unless requested.

Keep the cached files for follow-up analysis and repeat questions. They live under
`/tmp`, so normal operating-system cleanup bounds their lifetime. Include the cache
directory in the report so another investigation can reuse it.
