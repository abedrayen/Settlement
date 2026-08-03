# Deceased Borrower Policy

## Rule

If `FlagDeceased = 1`, the agent must **not** issue any settlement recommendation.

## Required Action

1. Block the recommendation immediately (deterministic guardrail).
2. Escalate to the **deceased_escalation** specialist workflow queue.
3. Log the event in the audit trail.

## Messaging

The agent must inform the user that no settlement recommendation can be issued and that the case has been escalated.
