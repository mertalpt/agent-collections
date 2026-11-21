---
description: "What earns a test, what to cover, and which shapes to avoid and prefer."
applyTo: "**"
---

# Testing

## Principle

A test exists to catch a failure before it reaches users or is found far
from its cause. Weigh what a test costs to write, run, and maintain against
what its failure would cost without it. Do not duplicate what type checks,
linters, or a failure at build or startup already catch. Concluding that no
test is needed is a valid outcome.

## Kinds of Tests

* **Agreement tests** check that two or more parts agree, such as a client and
the service it calls, or configuration and the code that reads it. They are
right or wrong regardless of what anyone intended.
* **Decision tests** pin a behavior that was chosen, such as a default, or
an invariant that must hold however the code around it changes. They
restate the choice; keep them short so a reader can confirm it at a glance.

## What Earns a Test

1. **Behavior.** A behavior the code owns and others rely on, tested through
the interface they use.
2. **Distance.** A constraint that a change elsewhere could break unnoticed:
another module, a dependency upgrade, or the way parts combine.
3. **Irreversibility.** A failure that would be silent and costly to undo,
such as lost or corrupted data, exposed secrets or data, or traffic sent
where it should not go. It earns a test even when unlikely.

## What to Cover

* The intended path, and the designed-for failure paths: invalid input, a
missing dependency, or a refused operation produces the intended error.
Edge cases the task or design does not settle are the user's decision, as
described in the `working-agreement` instruction; so are their tests.
* A bug fix comes with a test that fails without the fix. Run it once
before applying the fix to confirm.
* Test your use of a dependency, not the dependency. Do not test that a
database stores what an `INSERT` writes. Do test an endpoint that wraps the
`INSERT`: the test covers your configuration, connection, permissions, and
use of the library.

## Shapes

Avoid:

* restating a value declared in the code under test, or any test that can be
satisfied by copying a line out of it;
* comparing two expressions that read the same source, including asserting
that a mock returns what it was configured to return;
* asserting on implementation details, such as private calls or internal
state, when the behavior is observable through the interface;
* mocking what is cheap to use for real, such as pure functions, value
objects, or a temporary file or in-memory database.

Prefer:

* assertions on observable behavior: return values, raised errors, output,
and calls that cross the boundary;
* one behavior per test, named after the behavior;
* a property checked over every item the code produces, rather than a
hardcoded list of expected items, when items can be added later.

## Existing Tests

* Do not delete existing tests unless asked. Flag the ones these rules
reject.
