# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the Meritum label set (defined in meritum-monorepo `scripts/setup-labels.sh`).

| Label in mattpocock/skills | Label in our tracker     | Meaning                                                      |
| -------------------------- | ------------------------ | ------------------------------------------------------------ |
| `needs-triage`             | `status: triage`         | New; a human reviews it before work starts                   |
| `needs-info`               | `status: needs info`     | Waiting on the reporter for more information                 |
| `ready-for-agent`          | `status: ready`          | Clear and accepted; an agent may claim it                    |
| `ready-for-human`          | `status: ready for human`| Accepted, but a human implements it; agents leave it alone   |
| `wontfix`                  | `wontfix`                | Will not be actioned                                         |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table. A role change replaces the previous `status:` label, so an issue carries one `status:` label at a time.

`agent`, `status: in progress`, `status: in review`, `status: blocked` and `review: …` belong to `meritum-issue-claiming` and `meritum-pr-review-loop`; triage leaves them as they are.
