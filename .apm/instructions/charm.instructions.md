---
description: "Structure, architecture, and conventions for Juju charm repositories."
applyTo: "**"
---

# Juju Charms

These are the current standards. A repository may not meet them yet. If you
find legacy elements, such as no reconciler, widespread `event.defer`, or
legacy test frameworks, warn the user once and proceed with the task. Do not
warn when the task is the migration itself.

Charms are generic: no references to internal projects, teams, or
infrastructure.

## Repository

* **`src/`**: charm source code.
* **`lib/`**: charm libraries vendored by `charmcraft` and listed under
`charm-libs` in `charmcraft.yaml`. A library under `lib/charms/<owner>/v<N>/`
is vendored unless `<owner>` is this charm's name in snake_case, in which case
the repository owns it. Do not edit vendored libraries; update them with
`charmcraft fetch-libs`. When one changes, check how the charm's code uses
it.
* **`tests/`**: unit tests use Scenario (`ops.testing`); integration tests use
Jubilant. `ops.testing.Harness` and `pytest-operator` are deprecated. Write new
tests with the current frameworks, adding them as dependencies if missing.
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
* The pipeline is idempotent and converges over later events, including
`update-status`. Do not add synthetic retries or persistent retry state.
* Unmet preconditions return early and surface as status. Do not use
`event.defer()` unless there is an exceptional reason the user approved.
* Side effects are idempotent. Compare desired and actual state before
applying when checking is cheaper than applying; a workload restart is
expensive.
* Install is part of the pipeline and idempotent: `snap install` is safe;
check for a package before `apt install`.
* For charms with several modes, route to `_reconcile_<mode>` early.

### Workload Changes

* Do not call `container.restart()` outside a `restart` action. Put a hash of
the rendered state (configuration and files) into the Pebble layer
environment and call `replan`, so the workload restarts only when its inputs
changed, and at most once per hook. Prefer a hot reload when the workload
supports it.
* Write files only when their content changed.
* Secret values go into files in the workload container, never into the
Pebble environment or logs. File contents feed the plan hash.
* Do not use `level: alive` on Pebble checks. Take care with
`on-check-failure` restarts: a check that fails during a slow startup causes a
restart loop.
* Open required ports explicitly with `open_port` or `set_ports`.

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
| `src/literals.py`    | Constants: ports, paths, container, service and endpoint names  |
| `src/state.py`       | Dataclasses for inputs and desired state                        |
| `src/exceptions.py`  | Typed exceptions                                                |
| `src/relations/`     | One module per endpoint                                         |
| `src/workload/`      | Rendering, Pebble layer and file pushes, workload API client    |
| `src/core/`          | Pure domain logic, free of Juju concepts                        |

* Name relation modules after endpoints, so that the requirer and provider
sides of one interface stay separate. Share only the schema between them.

### Data

* Use dataclasses for data passed around inside the charm, and Pydantic at
parsing boundaries: charm config through `ops.CharmBase.load_config`, and
databags read from other applications.
* `relation.load` only reads. Use a custom decoder to shape data where needed,
and prefer a charm library's reader where it offers a good one.
* Provider sides need no databag models; the charm owns that data.
* Build workload configuration as data and serialize it, e.g. with
`yaml.safe_dump`. Where templates are clearer, keep them declarative, with the
logic in the code that prepares their data.

### Configuration

* Choose opinionated, sane defaults.
* An override option has no default: when empty, the charm derives the value;
when set, the value overrides it. Document the precedence in `charmcraft.yaml`
and `README.md`.
* Secret-grade configuration comes from Juju secrets, never plaintext
config.

### Secrets

* Exchange secrets through Juju secrets, not plaintext relation databags.
* Application-owned secrets are created by the leader and shared by ID;
followers wait until the secret exists.
* A value held in a Juju secret does not need to be stored anywhere else.

### Errors and Status

* Raise typed exceptions at the edges; `charm.py` maps them to statuses.
* Set status declaratively in `collect-unit-status`; each part of the charm
contributes its status, and ops reports the highest priority.
* Invalid configuration is `BlockedStatus`. Waiting on another unit,
relation, or secret is `WaitingStatus`. Reserve error states for serious
failures; do not let a charm flip between error and active.
* When one of several independent operations fails, such as creating
resources that already exist, continue with the rest.

## Integration Tests

* A `charm` fixture uses an existing packed charm rather than packing one.
* Order-dependent tests in a module use an incremental marker, so the tests
after a failure are not run against a broken deployment.
* Simulate crashes by deleting the pod with `kubectl`, not by removing and
redeploying the application.

## Rocks

* Prefer package sources in this order: snaps, debs, official binaries. Pin
official binaries with a checksum.
