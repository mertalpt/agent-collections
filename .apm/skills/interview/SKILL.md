---
name: interview
description: >-
  Interview the user relentlessly about a plan, decision, or idea until there
  is a shared understanding. Use when the user wants to stress-test their
  thinking or asks to be interviewed or grilled.
---

Interview the user until you reach a shared understanding. Map the topic as a
**design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose
prerequisites are already settled: the questions you can ask _now_ without
guessing at answers you have not heard yet. Each round, ask from the frontier
following the `questions` instruction, choosing the questions that unblock the
most.

Each round of answers reshapes the tree: settled decisions push the frontier
outward and unblock the questions that depended on them. Recompute the
frontier before the next round.

Finding facts is your job, never the user's. When a frontier question needs a
fact from the environment, look it up, using a subagent if available. Do not
block on it: only the questions downstream of a running lookup wait for it;
ask the rest of the frontier now.

The interview is read-only. Keep candidate changes, such as new terms or
decisions to record, in the conversation. Write them only after the user
confirms the shared understanding and permits the change.

The interview is done when the frontier is empty: every branch of the design
tree visited, nothing left silently assumed. Do not act on it until the user
confirms you have reached a shared understanding.
