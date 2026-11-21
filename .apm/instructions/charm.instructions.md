---
description: "Structure, architecture, and conventions for Juju charm repositories."
applyTo: "**"
---

# Juju Charms

These are the standards for new charms and for migrations. In an existing
repository, follow its conventions, as described in the `working-agreement`
instruction. If they differ from these standards, such as no reconciler,
widespread `event.defer`, or legacy test frameworks, mention it once and
proceed.

Charms serve any operator, not one organization: defaults, docs, and
examples must not assume a particular organization's environment, such as
its registries, endpoints, or naming.

## Repository

* **`src/`**: charm source code.
* **`lib/`**: charm libraries vendored by `charmcraft` and listed under
`charm-libs` in `charmcraft.yaml`. A library under `lib/charms/<owner>/v<N>/`
is vendored unless `<owner>` is this charm's name in snake_case, in which case
the repository owns it. Do not edit vendored libraries; update them with
`charmcraft fetch-libs`. When one changes, check how the charm's code uses
it.
* **`tests/`**: unit tests use Scenario (`ops.testing`); integration tests use
Jubilant. `ops.testing.Harness` and `pytest-operator` are deprecated. In a
repository that still uses them, write new tests with the framework already
in use.
* **`<charm>_rock/`**: `rockcraft` files for the charm's rocks.
* **`charmcraft.yaml`**: charm metadata. It documents every configuration
option.
* **`README.md`**: for operators: deploying with the `juju` CLI,
dependencies, relations, and non-trivial configuration.
* **`CONTRIBUTING.md`**: for developers: building the charm and rocks,
deploying locally, and working with branches.

When a change affects deployment, configuration, or the development workflow,
raise the documentation impact in the plan.

## Architecture

### Reconciler

* Every observed event funnels into one reconcile pipeline:
  1. **Inputs:** read config, relations, secrets, leadership, and peer data
  from the model, not from the event.
  2. **Desired state:** compute it with pure functions: rendered files,
  configuration, the Pebble plan.
  3. **Apply:** push files, update the Pebble layer, `replan`, call workload
  APIs.
* The pipeline is idempotent and eventually consistent: what one event
cannot finish, a later one does, including `update-status`. Do not add
synthetic retries, persistent retry state, or handling for transient states
that a later event resolves. The same holds for every event handler.
* Unmet preconditions return early and surface as status. Do not use
`event.defer()` unless there is an exceptional reason approved by the user.
* Side effects are idempotent: applying the same desired state again
changes nothing.
* In machine charms, installing is part of the pipeline. `snap install`
leaves an installed snap alone, but `apt install` upgrades an installed
package when a newer version is available: use `--no-upgrade` or check
for the package first.
* When configuration switches the charm between roles that run different
workloads, such as a coordinator and a worker, branch once at the start of
the pipeline into one function per role, rather than checking the role
throughout.

### Workload Changes

* Do not call `container.restart()` outside a `restart` action. Put a hash of
the rendered state (configuration and files) into the Pebble layer
environment and call `replan`, so the workload restarts only when its inputs
changed, and at most once per hook. Prefer a hot reload when the workload
supports it.
* Prefer passing secret values to the workload in files over the Pebble
environment: environment values are inherited by child processes and often
end up in debug output, such as `pebble plan` or crash reports.
* Do not give Pebble checks `level: alive` unless a container restart is
the fix: alive checks drive the Kubernetes liveness probe, which restarts
the whole container. Use a check without a level, and `on-check-failure:
restart` on the service.
* Declare the workload's ports with `unit.set_ports` in the pipeline. On
Kubernetes, the application's Service carries only declared ports.

### Responsibilities

* `charm.py` holds only wiring: event observation, charm library objects that
must be `ops.Object`s, the pipeline, action handlers, `collect-unit-status`,
and leader gating. Its methods are private.
* Nothing except `charm.py` holds or receives the charm object. Prefer
module-level functions that take only what they need: `ops.Model`,
`ops.Relation`, `ops.Container`, `ops.Secret`, or plain values.
* Typical layout, adapted to the charm's size:

| Path                 | Contents                                                        |
| -------------------- | --------------------------------------------------------------- |
| `src/charm.py`       | Wiring and pipeline                                             |
| `src/constants.py`   | Constants: ports, paths, container, service and endpoint names  |
| `src/state.py`       | Dataclasses for the pipeline's inputs and desired state         |
| `src/exceptions.py`  | Typed exceptions                                                |
| `src/relations/`     | One module per endpoint                                         |
| `src/workload/`      | Rendering, Pebble layer and file pushes, workload API client    |
| `src/core/`          | Pure domain logic, free of Juju concepts; it does not import `ops` |

* Name relation modules after endpoints, so that the requirer and provider
sides of one interface stay separate. Share only the schema between them.

### Data

* The charm's boundaries, in the sense of the `python-code` instruction,
include charm config, loaded through `ops.CharmBase.load_config`, and
databags read from other applications.
* Parse boundary data into Pydantic models first, so that it reaches the
dataclasses in `src/state.py` only once validated.
* `relation.load` only reads. Use a custom decoder to shape data where needed,
and prefer a charm library's reader where it offers a good one.
* A provider needs no model for its own databag, even when reading it back;
the charm owns that data.
* Build workload configuration as data and serialize it, e.g. with
`yaml.safe_dump`. Where templates are clearer, keep them declarative, with the
logic in the code that prepares their data.

### Configuration

* Give each option an opinionated default that works for most deployments,
rather than leaving it empty or required. Override options are the
exception.
* An override option has no default: when empty, the charm derives the value;
when set, the value overrides it. Document the precedence in `charmcraft.yaml`
and `README.md`.
* Secret-grade configuration comes from Juju secrets, never plaintext
config.

### Secrets

* Exchange secrets through Juju secrets, not plaintext relation databags.
* Application-owned secrets are created by the leader and shared by ID.
* A value held in a Juju secret does not need to be stored anywhere else.

### Errors and Status

* Raise typed exceptions at the edges; `charm.py` maps them to statuses.
* Set status declaratively in `collect-unit-status`; each part of the charm
contributes its status, and ops reports the highest priority.
* Invalid configuration or a missing required relation is `BlockedStatus`:
the operator must act. Waiting on another unit, or on data or a secret from
an existing relation, is `WaitingStatus`. Reserve error states for serious
failures; do not let a charm flip between error and active.
* An "already exists" error from a create call is success only when the
existing resource matches the desired one. If it differs and the charm owns
it, converge it like any other drift. If the charm does not own it, leave it
alone and surface the clash as status.
* When one of several independent operations fails, continue with the rest,
then surface the failures as status. Stop the pipeline instead when the
failure affects the rest, such as an unreachable workload API, or when
continuing could do damage.

## Integration Tests

* Prefer a `charm` fixture that takes the path of a packed charm, such as
from a `--charm-file` option, so tests run the artifact CI built instead of
packing their own.
* Order-dependent tests in a module use an incremental marker, so the tests
after a failure are not run against a broken deployment.
* Simulate crashes by deleting the pod with `kubectl`, not by removing and
redeploying the application.

## Rocks

* Prefer package sources in this order: snaps, debs, official binaries. Pin
official binaries with a checksum.
