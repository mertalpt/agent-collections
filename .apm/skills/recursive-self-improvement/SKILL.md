---
name: recursive-self-improvement
description: Learn from a notably successful or unsuccessful session and recommend evidence-based improvements to user-maintained instructions and skills.
argument-hint: "What went well or badly, and what should be examined?"
disable-model-invocation: true
---

# Recursive self-improvement

Review the current conversation and the user-maintained instructions and skills that materially
governed it. Treat the invocation argument as the user's primary signal about what went well or
badly and what deserves examination, but verify it against the session. Include this skill itself
when relevant. Do not broaden the review to unrelated customization files.

Report only; do not modify files.

## Review method

1. Establish the intended outcome, what the agent actually did, and why the user identified the
    session as successful or unsuccessful.
2. For a successful session, identify repeatable decisions or guidance that materially improved
    correctness, work quality, or completion time. For an unsuccessful session, identify concrete
    errors, corrections, rework, delays, or user friction and the patterns that caused them.
3. Inspect the source of each relevant instruction or skill. Do not rely on remembered wording or
    infer content that is unavailable.
4. Trace each observed outcome to the guidance, omission, decision, or workflow that contributed
    to it. Relevant causes include:
    - incorrect guidance or commands;
    - conflicting or duplicated guidance;
    - missing, ambiguous, or poorly placed guidance;
    - guidance that was present but insufficiently salient, precise, or enforceable;
    - unnecessary discovery, tool use, validation, repetition, or context consumption.
5. For guidance the agent failed to follow, treat the failure as improvement evidence. Assess
    whether to clarify, relocate, consolidate, shorten, or enforce the rule instead of merely
    repeating it.
6. Check proposed improvements against the other applicable guidance so they do not introduce a
    new conflict, duplicate an existing rule, or optimize speed at the expense of correctness.

Prefer demonstrated session evidence. Clearly label plausible but unproven concerns, and do not
present them as observed failures. Recommend removing or consolidating guidance when that would
improve compliance or reduce context cost.

## Generalization and scope

Do not turn an implementation detail, repository convention, tool limitation, or one-off incident
into general guidance merely because it appeared in this session. For every recommendation:

- identify the underlying pattern separately from the specific incident;
- explain why the pattern is likely to recur, or state that more evidence is needed;
- choose the narrowest effective scope: task skill, repository instructions, user instructions, or
  no customization change;
- keep project-specific commands and conventions in project-scoped guidance;
- preserve a successful practice only when the evidence supports a causal contribution, not merely
  correlation with a good result.

A single incident may justify a change when it exposes a deterministic error, direct conflict, or
unsafe behavior. Otherwise, prefer a narrowly framed recommendation or further observation over a
broad rule.

## Output

Present reusable strengths and failure-prevention findings, omitting either section when it has no
supported findings. Order findings by impact. For each finding include:

- the observed behavior and concrete evidence;
- the responsible or missing guidance, with a file reference when available;
- why it harmed correctness, work quality, or completion time;
- the justified scope and a concise description of the recommended change.

Prioritize correctness and conflict resolution, then work quality, then speed and token efficiency.
End with unresolved questions or risks. If no justified improvement is found, say so directly and
do not invent changes.
