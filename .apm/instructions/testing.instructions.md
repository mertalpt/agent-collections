---
description: "What earns a test or check, which shapes to avoid and prefer, and how to prove a test can fail."
applyTo: "**"
---

# Testing

## Principle

A test exists to catch a failure that the existing safety nets do not. Safety
nets include type checks, linters, CI, reverting a change, and failures that
are loud the moment the change is used. Weigh what a test costs to write, run,
and maintain against what its failure would cost without it. Concluding that
no test is needed is a valid outcome; a comment where the breaking change would
be made is often enough.

There are two kinds of tests:

* **Agreement tests** check that two or more parts agree, such as a client and
the service it calls, or configuration and the code that reads it. They are
right or wrong regardless of what anyone intended.
* **Decision tests** pin a behavior that was chosen. They necessarily restate
the choice; their value is that a reader can confirm the behavior at a glance,
so keep them short and readable.

## What Earns a Test

Apply these in order:

1. **Distance.** A test earns its place when the change that would break it is
likely made somewhere the reason is not visible: another module, a dependency,
an upstream default, or the way parts are combined. If a comment at the place
of the breaking change would explain the constraint, the comment is enough.
2. **Irreversibility.** A test earns its place regardless of distance when its
failure would be silent and not undone by reverting the change: lost or
corrupted data, exposed secrets or data, or traffic sent where it should not
go. Failures that are loud and reversible do not qualify, however alarming
they sound.
3. **No duplication.** If the first two leave it unclear, reject a test that
can be satisfied by copying a line out of the code it tests.

## Shapes

Avoid:

* restating a value that is declared in the code under test;
* comparing two expressions that read the same source, which cannot fail,
including asserting that a mock returns what it was configured to return;
* a hardcoded list of expected items, which cannot catch an item that is added
later without the tested property.

Prefer, in this order:

1. a negative assertion that nothing else was added or exposed;
2. a property checked over every item the code produces or discovers;
3. an assertion of the reason behind a choice rather than its value;
4. a check over how parts combine, which no single part can see.

## Proof

* Prove every new test can fail: violate its property on purpose, confirm the
test fails with a message that explains the problem, then revert.
* Prefer reporting every violation in one run over stopping at the first.
* Failures that cannot be undone should block the change before it is merged
or deployed. Failures that are merely undesirable may be reported instead.
* Do not delete existing tests unless asked. Flag the ones these rules reject.
