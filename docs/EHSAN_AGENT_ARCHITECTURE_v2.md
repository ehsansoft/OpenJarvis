# Hermes agent architecture v2 — roles, capabilities, tasks, reports, thinking

Proposal for the next iteration of the Hermes fleet on Ehsan's workstation.
Companion to `EHSAN_SYSTEM_PLAN.md`; decisions flagged with **[NEEDS
DECISION]**.

## 1. Design principles

1. **One brain per concern.** A profile owns a domain; overlap is resolved
   by handoff, not by duplication.
2. **Local by default, remote by opt-in.** Every SOUL already encodes this;
   v2 keeps it and adds routing hygiene (below).
3. **Board-first.** Tasks arrive through the OpenJarvis board; completion
   means a board update + a report file — not a chat message.
4. **Reports are artifacts.** Every role writes
   `D:\AI-Control\OpenJarvis\reports\YYYY-MM-DD-<role>.md` with a fixed
   template so results are greppable and comparable day to day.
5. **Thinking is visible.** Each role has a "thinking protocol" — the
   order of questions it must answer before acting — so output quality is
   inspectable, not vibes.

## 2. Fleet map (12 roles)

| Role | Owns | Primary models | Thinks like |
| ---- | ---- | -------------- | ----------- |
| coder | code implementation via editor CLIs | local `local/code` for private repos; `free/code`/`kilo/*` for public | smallest diff that proves the point; verify before claiming |
| maintainer | ongoing project health | local; `free/code` public | what changed, what broke, what drifts |
| plugindev | EhsanSoft / WordPress | **local only** (private product) | standards, security, runtime proof on Wamp |
| webbuilder | site assembly | local for client content | render-check both directions (RTL/LTR) |
| researcher | deep research | local + `free/research` on opt-in | sources first, confidence last |
| scout | fast info gathering | `free/research`/`kilo/*` (public) | cite or omit; label inference |
| newswire | news digests | remote free tiers | timestamp, dedupe, rumor≠fact |
| keeper | user + project knowledge | **local only, ever** | record, never guess; flag conflicts |
| writer | articles | local drafts; remote for public topics | outline→draft→cuts |
| seo | SEO assets | local for client sites | intent over volume guesses |
| translator | fa-IR ↔ en | local for private text | meaning, not words; glossary |
| cleanup | disk reclaim plans | local | report-only; approve-per-item |

## 3. Task routing (who gets what)

- A request names its **domain**, not its agent: "write plugin code" →
  plugindev; "fix bug in repo X" → coder (private) — routing rules live in
  the board, not in your head.
- **Escalation chain**: scout finds → keeper stores; writer drafts → seo
  packages; maintainer flags → coder fixes.
- **Model policy is automatic per role**: SOUL pins it; you never choose
  models for routine work. Manual override stays one flag away
  (`--provider openjarvis --model <id>`).

## 4. Report template (all roles)

```markdown
# <role> report — <date>
Task: <one line from the board>
Done: <bullets, each with its verification>
Evidence: <test name / HTTP status / file path>
Not done: <honest list>
Needs Ehsan: <decisions, approvals, tokens>
Next: <smallest next step>
```

## 5. Thinking protocols (quality lever)

Before acting, each role answers in order:
1. **What is actually being asked?** (restate in one line)
2. **What do I know vs. assume?** (mark assumptions)
3. **What is the cheapest verification?** (test, probe, render)
4. **What could this break?** (blast radius)
5. **What is the first smallest shippable step?**

Private-data check runs automatically: if the task touches user content →
local model path, no exceptions.

## 6. Scheduled capabilities (proposed; needs decisions)

| Job | Cadence | Owner | Delivers to |
| --- | ------- | ----- | ----------- |
| Morning digest (newswire) | daily 08:00 | newswire | report file + Telegram (when wired) |
| Model health sweep | daily | maintainer (script) | recovered/dead model list |
| Cleanup report | weekly | cleanup | reclaim plan, approval-gated |
| Project health check | weekly | maintainer | drift, failing tests, TODOs |
| Knowledge sync | weekly | keeper | what was learned, conflicts found |

## 7. Quality upgrades (concrete, small)

1. **Engine error transparency** — surface upstream 429/502 as 502+reason
   instead of bare 500 (queued in repo).
2. **Reports folder + template** — one convention, all roles.
3. **Board integration per profile** — each SOUL gains "read the board,
   update the board" lines (small edit, high leverage).
4. **Daily model watchdog** — re-tests yesterday's failures automatically.
5. **Memory discipline** — only keeper writes durable memory; others
   propose facts to keeper (prevents memory soup).

## 8. What I need from you (see interview)

Telegram token, schedule preferences, priority handoffs, D: decisions,
and whether keeper may store your personal preferences centrally.
