# AGENTS.md

> Runtime workflow supplement.

## How It Works

**Default — code directly.** Most changes are a bug fix or small feature with a clear scope.

1. Write the problem to `runtime/ISSUES.md`
2. `fx issue push` → creates a GitHub Issue, back-fills `#123` into `runtime/ISSUES.md`
3. `fx issue push` 默认会在创建 issue 后，按顺序依次调用 Codex 解决；单个 issue 也应按同样规则执行
4. `fx verify` → confirm tests pass
5. Close the GitHub Issue

**If work starts from Feishu — use staged flow.**

1. Use `fd-feishu-issue-flow`
2. Proposal first, no direct code change
3. Human review approves the proposal
4. Then create the GitHub issue
5. Then run implementation → verify → PR → review → merge → close

**For large changes — use a phase.** When the change spans multiple files, pages, or services.

1. Collect problems in `runtime/ISSUES.md`, run `fx issue push`
2. `fx plan draft` → directly writes `runtime/plans/phase-X.md`
3. Human reviews the phase plan and adjusts it if needed
4. `fx plan` → builds the execution prompt from `runtime/AGENTS.md + runtime/PLAN.md + runtime/STATE.md + current plan` and runs Codex
5. `fx verify` → confirm tests pass
6. `fx close` → archives phase, auto-switches to next planned phase

## Completion Notification

- If the user explicitly asks for a Feishu notification after completion, prefer the configured Feishu bot conversation context first.
- If the task came from a Feishu bot conversation and the repo has a working `fa` bridge context, reuse that same conversation and profile; do not ask for a separate `open_id` first.
- If the user explicitly asks for milestone Feishu updates, send one after implementation/verify/PR creation and another after PR review is complete or merge-ready.
- For milestone updates with an active `fa` task, prefer `f fa task notify <task-id> --label ... --summary ...` so the same bridge context and profile are reused.
- Only when the task did not originate from a Feishu bot conversation should `f fl ...` direct sending become the fallback option.
- With `f fl ...`, single-line completion messages may use `--text`, while multi-line summaries must use explicit `post` content.
- If there is neither a reusable bot conversation context nor a direct-send target, do not block completion; state clearly that the Feishu notification was not actually sent.
