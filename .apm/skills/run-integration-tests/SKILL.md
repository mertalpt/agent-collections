---
name: run-integration-tests
description: "Run, reproduce, or debug one Juju charm integration test module locally. Use for targeted tox/pytest integration runs, including discovering repository-specific environments, artifacts, pytest options, preconditions, model lifecycle, and safe resource-aware parallelism."
---

# Run a Juju integration test module

Integration modules deploy real applications and may take more than 20 minutes. Treat this
skill as a discovery workflow, not as a repository specification. Run one module per process.

Repository instructions and executable configuration take precedence over examples in this skill.
Treat documented repository commands as strong candidates. Inspect composite commands before
running them. If an assumption or command fails, inspect the repository source for a contradiction
before adapting it; do not repeatedly retry the assumption.

## 1. Read the repository contract

Start at the repository root. Read `CONTRIBUTING.md` first, then the integration-testing sections
of `README.md`, relevant `Makefile` targets, and `tox.ini`.

Use source as the final authority for current behavior:

```sh
tox list
find tests/integration -maxdepth 1 -type f -name 'test_*.py' -print
grep -rnE 'pytest_addoption|addoption|getoption|temp_model|keep-model|no-deploy' tests
```

Documentation expresses the intended workflow; `tox.ini`, fixtures, and test modules reveal what
the current checkout actually executes. When they disagree, report the discrepancy and follow the
executable configuration unless doing so would be destructive or would broaden the requested run.

## 2. Select exactly one module and environment

Choose a concrete `tests/integration/test_*.py` module.

Prefer a per-module environment whose expanded command names that file. Confirm it before running:

```sh
tox c -e <environment> -k commands set_env pass_env
```

This shows the resolved command and environment settings, such as the concrete test file behind
`{env:TEST_FILE}`, without running the environment.

Environment naming is not uniform. A file such as `test_trino_catalog.py` may map to
`integration-trino-catalog`, another alias, or no dedicated environment at all. If there is no
verified per-module environment, do not fall back to the broad `integration` environment or assume
that adding the file as a positional argument narrows collection: many tox commands also append the
whole integration directory. Inspect `tox.ini` and repository guidance, then construct the narrowest
repository-supported command. Stop and explain the missing mapping if no safe targeted command is
available.

Use `-k` only to select tests within the already selected module. It does not prevent collection or
import of other modules when the tox command targets the whole directory.

## 3. Discover required arguments and artifacts

Do not assume option names, artifact counts, image names, registries, build tools, or local-cloud
topology. Discover them from all applicable `conftest.py` files and the fixtures used by the chosen
module. Read nearby comments as well as declarations and consumers: comments often identify options
accepted only for compatibility with a shared CI workflow and not needed locally. `tox -e
<environment> -- --help` can confirm registered pytest options without deploying.

For every required option:

1. Read its `addoption` declaration, nearby comments, and the fixture consuming `getoption`.
2. Determine whether it has a default, environment-variable fallback, or existing-deployment mode.
3. Find the repository-supported way to produce its value in `CONTRIBUTING.md`, `Makefile`, helper
   scripts, or CI workflow.
4. Verify each referenced artifact or OCI image exists before starting the long run.

A repository may have zero, one, or several rock resources, may use remote images, or may build the
charm inside a fixture. Do not assume that familiar targets such as `build-charm`, `build-rock`, or
`import-rock` exist or have consistent scope.

## 4. Run the cheapest preflight

Derive preconditions from the selected test path. Typical checks include tox/tool availability,
Juju controller access, cloud and credential availability, Kubernetes readiness, registry access,
LXD initialization, and sufficient disk space. Run only checks supported by repository evidence.

Inspect existing Juju models before starting, but never destroy every model globally. Existing
models may belong to the user or another concurrent test. An initial model snapshot is useful
diagnostic context, but it does not establish ownership of models that appear later.

If tox fails to create an environment because the checkout filesystem rejects symlinks, retry with
a native-filesystem work directory via the helper's `--workdir` option. Do not force an external
work directory when the repository filesystem works normally.

## 5. Use the bundled helper

Resolve `scripts/run_integration.sh` relative to this loaded `SKILL.md`, wherever the skill is
installed. It may be a user-level skill or live in the target repository. Invoke the resolved path
while the terminal's working directory is the target repository root.

```sh
<skill-directory>/scripts/run_integration.sh tests/integration/test_charm.py \
  --env integration-charm -- --charm-file=<path> --<image-option>=<image>
```

The helper does not build artifacts or invent pytest arguments. It verifies that the tox environment
exists and visibly targets the selected module, then runs it. Use `--allow-unverified-target` only
after source inspection proves that an indirect wrapper still selects that module.

Pass `--workdir <path>` only for a confirmed tox work-directory problem. Pass additional pytest
arguments after `--`.

## 6. Parallelism is conditional

Start serially. A second module may run concurrently only when all of these are true:

- the repository creates isolated models and does not mutate shared controller or cluster state;
- the modules do not reuse a fixed model, application names in one model, ports, or other shared
  resources;
- the first run's pods have all been initialized, or its Juju units have moved out of `waiting`, so
  its resource demand is visible;
- at launch, at least 10 GiB of `MemAvailable` remains and one-minute load per logical CPU is no
  greater than 0.75.

The agent must verify repository isolation and deployment readiness. The helper coordinates its own
runs and enforces the stagger and host-resource admission checks. It defaults to a 120-second
stagger, 10 GiB available memory, and a 0.75 normalized load ceiling. Tune them when the host or
repository justifies it:

```sh
INTEGRATION_STAGGER_SECONDS=180 \
INTEGRATION_MIN_AVAILABLE_GIB=12 \
INTEGRATION_MAX_LOAD_PER_CPU=0.70 \
  <skill-directory>/scripts/run_integration.sh <module> --env <environment> -- <pytest args>
```

The memory threshold is an admission floor, not a prediction that a module uses exactly 10 GiB.
Normalized load makes the CPU rule portable across machines. If the helper declines an additional
run, continue with the active run rather than forcing parallelism. Override the gate only at the
user's direction.

## 7. Observe without imposing a short timeout

Allow more than 20 minutes. Stream or retain complete output. When the agent's tools support
multiple terminals, use a separate one for targeted `juju status` or `juju debug-log` observation
after the model name is known. Otherwise rely on the test output and inspect Juju after the command
returns. Avoid filters that hide the first traceback or command failure.

For incremental test classes, later xfails may only reflect an earlier failure. Diagnose the first
failure in execution order.

## 8. Clean up only what the run owns

Let repository fixtures perform normal teardown. Respect documented keep/reuse options such as
`--keep-models` or `--no-deploy`; their names and semantics are repository-specific.

After interruption or failed teardown, identify models from exact names emitted by this run, its
fixture state, or its logs. Never infer ownership solely from a before/after model-set difference:
another process may have created a model concurrently. If ownership cannot be established, leave
the model in place and report it rather than destroying it. Preserve a deliberately kept model until
debugging is complete. Use the repository's cleanup command and storage policy rather than assuming
global `--destroy-storage --force` is appropriate.

## 9. Classify failures before changing code

- Before pytest starts: tooling, tox, artifact, controller, cloud, or registry setup.
- During deployment fixtures: inspect Juju status, debug logs, workload logs, and repository setup.
- In a test body: the deployment worked far enough to exercise product or test behavior.
- During teardown: report the test result separately from cleanup failure.

Compare local artifact versions and image references with CI when local behavior differs. If the
workflow remains blocked, report the command attempted, the first actionable failure, repository
evidence that contradicted the attempted assumption, and the next fact needed to proceed.
