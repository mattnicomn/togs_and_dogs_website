---
inclusion: always
---

# Windows shell execution rules

This repository is developed on Windows.

## Preferred command execution

- Prefer direct terminal commands or `cmd.exe`.
- Do not use `execute_pwsh`.
- Do not use PowerShell unless the task explicitly requires PowerShell syntax.
- When using `cmd.exe`, keep commands simple and avoid unnecessary nested quoting.
- Prefer separate commands over long chained commands.
- When running Vitest or web component tests, always `cd` using an uppercase
  drive letter (e.g. `cd C:\Users\...`) before executing the test command.
  Lowercase drive letters (e.g. `c:\`) cause Vitest to fail with
  "failed to find the current suite" due to a Windows path-casing issue.

## Failure handling

- Never retry the same failed command or tool invocation more than twice.
- After two failures, stop and report:
  - the exact command
  - the observed error
  - whether an equivalent `cmd.exe` command is available
- Do not state that work is blocked when the command already completed successfully.
- A trusted-command prompt is not a command failure.
- If command output shows tests, compile, Terraform, or Git succeeded, record the result and continue.

## Command trust

- Never recommend trusting `cmd *`, `powershell *`, `pwsh *`, `git *`,
  `terraform *`, `aws *`, or the entire shell tool.
- Prefer one-time approval or exact-command trust.
- Production AWS and Terraform write commands always require explicit user
  approval, regardless of prior trust.

## Git safety

- Use targeted `git add <specific-file>` commands only.
- Never use `git add .`.
- Do not use destructive Git commands, force pushes, or history rewriting.