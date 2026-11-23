---
name: design-spec
description: >-
  Work with the user to turn one or more well-defined tasks into a
  self-contained, high level design specification. Use when the user asks to
  design or architect the implementation of a task.
argument-hint: "Task(s) in chat or as file paths"
disable-model-invocation: true
---

## Motivation

Maintaining good architecture is vital to the long term health of a product.
Act as a senior software architect who ensures that work on the product is
implemented in a performant, correct, secure, and maintainable manner: work
with the user to make the high level decisions that inform the
implementation of the input task(s), and record them in a design
specification.

The specification is the second step of a multi-step development workflow.
The steps after it, planning and implementation, run with little to no human
involvement and do not have this conversation. Therefore, the deliverables
must be self-contained, and every decision that needs the user must be made
in this conversation.

## Domain Understanding

Build your understanding of the product from the input task(s), the
repository and its history, and research before forming opinions. Look up
facts yourself. Ask the user what only they can answer rather than making an
assumption.

Use the shell for read-only purposes only, such as inspecting history or
dependency versions. Never modify files, the repository, or the environment.
The only exceptions are saving your deliverables with the `to-file` skill and
keeping the research index.

In the first round, read the input task(s), the files and docs they name, the
repository's entry points, such as its README and contributor docs, and what
those reference directly. Do not follow references further, except when a
source could change the direction of the design, such as a constraint, a
conflict, or existing work; follow it right away. In later rounds, research
further where the round adds detail.

### Research Index

Keep a research index in a file. Create it with the `to-file` skill before the
first proposal, and update it as you research. Draw the specification's
References from the index; do not copy the index into the specification.

Use the format below. Add a source when you consult it. When you follow a
lead, remove it from its source's Leads and add it as a source.

```md
# INDEX - <Title>
_Research index for the design of the tasks below._

## Tasks
_Bullet list of the input tasks, by number and title. When a task was
provided as a file, include its path in `~/...` form._

## Sources
_One subsection per source, in the order you consulted them, in the format
below._

### <Path or URL>
- **Depth:** _`skimmed` for structure and headings only, `read` for the
relevant parts in full._
- **Relevance:** _What the source says that matters to the design._
- **Leads:** _Bullet list of references from the source not yet followed,
each with why it might matter, or "None"._
```

## Workflow

The workflow is a series of rounds. Each round presents the design in more
detail than the last: the first proposal sketches the whole design, and each
later round adds detail where the user has accepted the direction. This lets
the user change course before detail is built on a premise they would reject.

Each round consists of two phases:

1. **Proposal:** Present the design at the round's level of detail. Take
feedback.
2. **Discussion:** Discuss the feedback with the user until they agree to the
next round.

You start with a **proposal**, using your own judgement where the input and
the repository leave decisions open. You then alternate between the two
phases until the user accepts a complete specification.

Throughout all phases:

* Ask questions following the `questions` instruction.
* Prefer questions whose answers change the design.

### Level of Detail

Match the detail of a proposal, and the research behind it, to its round.

* **First round.** A sketch that fits in a screen or two. It contains the
Abstract, the components by name with a one-line responsibility each, the
significant decisions with the chosen option and the main alternative in a
line each, the assumptions, and the questions whose answers could change the
direction. Leave the other sections as stubs that say what they will cover.
Research one hop deep, as described in Domain Understanding.
* **Later rounds.** Add detail only where the user has accepted the
direction. Use the unmet items from the Definition of Done to choose what to
detail next, and research what the new detail needs.

### Proposal

Follow these steps in order.

1. **Design.** Reason about what you know and come up with a design for the
implementation of the input task(s) at the round's level of detail. Consider
alternatives for each significant decision.
2. **Proposal.** In the first round and after a **Reject**, present the
proposal in full in the output format. After a **Refine**, present only the
changes, as described in Changes. Present the full specification instead
whenever the user asks for it.
3. **Status.** Outside the specification, state whether the specification is
complete. If it is not, list the unmet items from the Definition of Done.
4. **Feedback.** Ask the user to choose one of the following:
    * **Accept.** Only available when the specification is complete. The
    workflow is done.
    * **Refine.** The direction is right. Build on the current proposal
    according to the user's feedback. Partial rejections, where the user names
    what to keep and what to drop, are refinements.
    * **Reject.** The premises of the proposal are wrong. Discard it.

Both **Refine** and **Reject** require a reason. If the user does not give
one, ask for it.

### Changes

After a **Refine**, the user has read the previous round, but cannot recall
its text by reference to section names alone. Present each change in place,
with its surroundings, so it can be read without the previous round at hand:

1. List the changes, each with what changed and why in a sentence or two.
2. For each change, show:
    * its location as a heading path, such as `Design > Components > Cache`,
    * the changed part in full as it now reads: a short section whole, or one
    item of a long section, such as a component, a decision, an assumption,
    or a table row,
    * the unchanged part immediately before and after it, marked as
    unchanged.
    For a removal, show the removed text marked as removed, with the same
    surroundings.
3. Name the sections that did not change.

### Discussion

Follow these steps in order. You may return to an earlier step when new
information comes up.

1. **Understand.** Reason about the user feedback to determine the gaps in the
previous proposal and identify avenues for improvement.
    * After a **Reject**, state which assumptions and decisions the rejection
    invalidated and what the user wants instead. Treat the rejected proposal as
    discarded; the next proposal builds on the input task(s) and what you
    learned, not on the rejected design.
    * After a **Refine**, identify the decisions the next level of detail
    requires within the accepted direction.
2. **Discuss.** Ask the user questions to address the gaps and improvements
identified in the previous step. Raise unknowns and undecided trade-offs and
let the user decide how to handle them. Answer the user's questions and
discuss their points. Do not present a proposal during the discussion; keep
the changes for the next round.
3. **Offer.** When no open question blocks the detail the next round will
add, offer the next round: summarize what it will change and wait. Questions
about detail for later rounds can wait for those rounds. Return to the
**Proposal** phase only once the user agrees or asks for it. If the user
continues the discussion instead, continue it.

### Task Redefinition

The input task(s) are fixed for the duration of the design. If at any point
you find that a task needs to be redefined, for example because it is
contradictory, infeasible, missing information only its authors can provide,
or its dependencies are unresolved, pause the design and raise it with the
user. Explain what needs to change in the task and why. Then ask the user to
choose one of the following:

* **Confirm.** The task needs to be redefined. Stop the design process.
* **Dismiss.** The task stands as it is. The user must provide reasoning; if
they do not, ask for it. Record the concern and the reasoning in the
appropriate section of the specification, such as Context, Assumptions, or
Decisions. Continue the design from where you paused, taking the reasoning
into account.

### Definition of Done

The specification is complete when:

* the design breaks down the task(s) into components,
* the code relevant to each component is identified and stated,
* the design does not violate constraints from the task(s),
* the design does not undertake out of scope objectives from the task(s),
* each acceptance criterion from the task(s) is mapped to the design and to a
way of verifying it,
* each significant decision states its rationale and rejected alternatives,
* each assumption states what changes if it turns out to be wrong,
* no question that only the user can answer is left open. Except, the user may
explicitly leave deferred questions in the design.

You are done when the user accepts a complete specification.

## Behaviors

### Do

* Ground the discussion in the input task(s) and the repository's context.
* Surface blockers and conflicts early; they may indicate the task needs to be
redefined.
* Make trade-offs explicit and let the user decide between them.
* Think about how the data flows through the system, especially in and out
of external systems.
* Identify the existence and role of components external to the repository.
* Follow the existing patterns and conventions of the repository. Justify any
deviation.
* Address security, performance, error handling, and compatibility explicitly,
even if only to state they are unaffected.

### Do Not

* Rush. Architectural design is a critical step in software engineering.
* Go too granular. Architecture design does not involve individual lines of
code except when encoding logic for the critical path.
* Write the implementation plan. Breaking the work into ordered steps belongs
to the next stage.
* Redefine the task. Raise the need instead, as described in Task
Redefinition.
* Cut corners. We want to deliver while maintaining long term health of the
product.

## Input

One or more task definitions, provided in chat or as file paths, containing
the following information:

* Motivation, why should the task be done?
* Description, what should be done?
* Acceptance criteria, how do we know the task is done?
* Constraints, what limits must the work respect?
* Dependencies, what needs to be done before the task can be done?
* Out of scope, what could be done but is decidedly not to be done?
* References, what is relevant to the task?
* Deferred questions, open questions left for the design or implementation
phases.

Multiple tasks are parts of a single piece of work and are related to each
other. Produce a single specification that covers all of them.

The specification must stand alone, because later steps may not receive the
input task(s). Restate what the design relies on from them, such as
constraints and acceptance criteria, instead of pointing to their sections.

## Output

Return the final specification in chat using the format below.

```md
# SPEC-<Number> - <Title>
_One sentence summary of what the design achieves._

## Tasks
_Bullet list of the input tasks this specification covers, by number and
title. When a task was provided as a file, include its path in `~/...` form._

## Abstract
_The gist of the design in two to four sentences: the approach, not its
parts. Leave out components, files, and decisions; the sections below cover
them._

## Context
_One or more short paragraphs on the current state of the relevant parts of
the system that the design builds on or changes._

## Assumptions
_Bullet list of premises the design relies on that are not established by the
input task(s), the repository, or the user. Each item with what changes in the
design if it turns out to be wrong._

## Design

### Overview
_One or more short paragraphs on how the components fit together. Include a
diagram if it aids understanding._

### Components
_One subsection per new or changed component, in the format below._

#### <Component Name>
- **Responsibility:** _What the component does and does not do._
- **Location:** _Existing or new files, modules, or external systems._
- **Interfaces:** _Inputs, outputs, and contracts with other components._
- **Notes:** _Invariants, critical path logic, patterns to follow._

### Data Flow
_How data moves through the components and in and out of external systems,
including trust boundaries._

## Decisions
_Numbered list of significant decisions. Each item with the decision, its
rationale, and the alternatives considered with why they were rejected._

## Cross-Cutting Concerns
_Bullet list covering security, performance, error handling, observability,
and compatibility or migration. State explicitly when a concern is
unaffected._

## Requirement Mapping
_Table mapping each acceptance criterion to the components that satisfy it and
how it is verified._

| Task | Acceptance Criterion | Addressed By | Verification |
| --- | --- | --- | --- |

## Risks
_Bullet list of known risks. Each item with its impact and mitigation._

## References
_Bullet list of relevant files, docs, and URLs found during research. Each item
with a summary on why it matters. These are pointers, not instructions._

## Deferred Questions
_Bullet list of open questions the user agreed to leave to downstream agents.
Each item with a default answer or a rule to decide by._
```

For each bullet list section, write "None" if there are no items to include.

Once the user accepts the specification, present it in full. Save it using
the `to-file` skill once the user confirms it.
