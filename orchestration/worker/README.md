# GitHub-to-Antigravity Local Task Worker

A secure local automation bridge connecting **GitHub Issues** to the **Google Antigravity CLI (`agy`)**.

This worker allows you (or ChatGPT) to draft structured development tasks as GitHub Issues. The worker polls for issues carrying the `agent-run` label, runs them through the local Antigravity CLI in headless print mode (`agy -p`), records audit logs and git changes, and reports completion back as a comment on the GitHub Issue with the label `agent-review`.

---

## 🏗️ Architecture & Workflow

```
[ GitHub Issue Created ]
       │
       ▼
[ Labeled 'agent-run' ]
       │
       ▼
[ Local Python Worker polls GitHub via `gh` ]
  ├─ Verify Issue Author == 'nikhilsonwani34'
  ├─ Security & Disallowed Operations Inspection
  ├─ Deduplicate via local state/task_state.json
  ├─ Relabel: 'agent-in-progress'
  │
  ▼
[ Antigravity CLI Execution ]
  ├─ Headless Print Mode (`agy -p`)
  ├─ Enforce Sandboxed Mode (`--sandbox`)
  ├─ Bounded Timeout (20 minutes max)
  ├─ Restricted to repository root workspace
  │
  ▼
[ Post-Execution Reporting ]
  ├─ Inspect git status & diff
  ├─ Execute tests if present
  ├─ Save stdout / stderr / prompt logs locally
  ├─ Post completion Markdown report to GitHub Issue
  └─ Relabel: 'agent-review' (or 'agent-blocked' if failed)
```

---

## 📋 Prerequisites

1. **Python 3.10+**:
   Verify with:
   ```powershell
   python --version
   ```
2. **GitHub CLI (`gh`)**:
   Verify with:
   ```powershell
   gh --version
   ```
   If not installed:
   ```powershell
   winget install --id GitHub.cli
   ```
3. **Antigravity CLI (`agy`)**:
   Verify with:
   ```powershell
   agy --version
   ```
   Official installer for Windows PowerShell:
   ```powershell
   irm https://antigravity.google/cli/install.ps1 | iex
   ```
   *(Ensure `C:\Users\<USER>\.gemini\bin` is present in your PATH).*

---

## 🔐 1. GitHub CLI Authentication

The worker uses the GitHub CLI to read issues, update labels, and post comments.

Authenticate your GitHub account:
```powershell
gh auth login
```
Follow the interactive prompts:
- What account do you want to log into? **GitHub.com**
- What is your preferred protocol for Git operations? **HTTPS**
- Authenticate Git with your GitHub credentials? **Yes**
- How would you like to authenticate? **Login with a web browser** (or paste an auth token)

Verify authentication:
```powershell
gh auth status
```

---

## 🏷️ 2. Label Setup

The orchestration workflow depends on four labels on GitHub:

| Label | Color | Description |
|---|---|---|
| `agent-run` | `#1D76DB` (Blue) | Assign this to trigger the worker to execute the task. |
| `agent-in-progress` | `#FBCA04` (Yellow) | Applied automatically while the agent is running. |
| `agent-review` | `#0E8A16` (Green) | Applied automatically when done; ready for human review. |
| `agent-blocked` | `#D93F0B` (Red) | Applied if security checks fail or execution errors out. |

To create them in your repository via GitHub CLI:
```powershell
gh label create "agent-run" --repo nikhilsonwani34/apex-career-institute-automated --description "Ready for local agent execution" --color "1D76DB" --force
gh label create "agent-in-progress" --repo nikhilsonwani34/apex-career-institute-automated --description "Local agent is currently processing this task" --color "FBCA04" --force
gh label create "agent-review" --repo nikhilsonwani34/apex-career-institute-automated --description "Agent execution completed; awaiting human review" --color "0E8A16" --force
gh label create "agent-blocked" --repo nikhilsonwani34/apex-career-institute-automated --description "Task execution blocked or failed security validation" --color "D93F0B" --force
```

---

## ⚙️ 3. Configuration

The worker configuration file is located at `orchestration/worker/config.json`. If it does not exist, copy from `config.example.json`:

```json
{
  "repository": "nikhilsonwani34/apex-career-institute-automated",
  "allowed_author": "nikhilsonwani34",
  "poll_interval_seconds": 30,
  "trigger_label": "agent-run",
  "in_progress_label": "agent-in-progress",
  "completed_label": "agent-review",
  "blocked_label": "agent-blocked",
  "task_timeout_seconds": 1200,
  "agy_binary_path": "",
  "use_sandbox": true,
  "enforce_repo_workspace_only": true,
  "state_dir": "state"
}
```

---

## 🚀 4. Worker Startup

Run the provided PowerShell startup script from your repository root:

```powershell
.\orchestration\worker\start-worker.ps1
```

Or run Python directly:
```powershell
python orchestration/worker/task_worker.py
```

### Command-line Options:
- `--once`: Runs a single poll cycle and exits (useful for automated testing or scheduled cron runs).
- `--dry-run`: Polls and simulates processing without changing GitHub labels or modifying files.
- `--config <path>`: Specifies a custom configuration JSON file.

### Graceful Shutdown:
Press `Ctrl+C` in the terminal. The worker intercepts the signal and cleanly flushes state and audit logs before terminating.

---

## 📝 5. How to Submit a Task

1. Go to your repository on GitHub:
   `https://github.com/nikhilsonwani34/apex-career-institute-automated/issues/new`
2. Title: Enter a concise title (e.g., `Add landing page header component`).
3. Description: Write detailed instructions for the task.
4. **Labels**: Add the label **`agent-run`**.
5. Click **Submit new issue**.

Within 30 seconds (or your configured `poll_interval_seconds`), the worker will detect the issue, change the label to `agent-in-progress`, run `agy`, and complete it!

---

## 📊 6. Inspecting Reports & Audit Logs

### On GitHub:
The worker posts a comprehensive Markdown comment on the issue containing:
- Task ID & execution timestamps
- Status badge
- List of modified and created files (`git status` and `git diff --stat`)
- Test suite outcomes
- Excerpt of agent response
- Next steps for human review

### Locally on Disk:
All run outputs are archived in `orchestration/worker/state/`:
- `state/audit.log`: Comprehensive JSON Lines log of every poll, security evaluation, and execution event.
- `state/task_state.json`: Persistent registry preventing duplicate runs.
- `state/runs/issue-<NUMBER>-<TIMESTAMP>/`:
  - `prompt.txt`: The exact prompt passed to the agent.
  - `stdout.log`: Full standard output from `agy`.
  - `stderr.log`: Diagnostics and error logs.
  - `report.md`: The markdown report that was submitted to GitHub.

---

## 🛡️ 7. Security & Isolation Safeguards

- **Strict Author Verification**: Only issues created by the configured `allowed_author` (`nikhilsonwani34`) are processed. Issue comments or issues created by other users are ignored.
- **Untrusted Input Pre-screening**: The worker scans task titles and descriptions for dangerous operations before passing them to the agent. It blocks tasks requesting deployments (`vercel`, `netlify`, `aws`), credential exfiltration (`gh auth token`, `id_rsa`), or remote code pushes (`git push`).
- **No Automatic Code Pushes**: The agent only modifies local working tree files. It never pushes commits to GitHub or merges branches. Human review is strictly required.
- **No `--dangerously-skip-permissions`**: The agent runs with terminal sandbox restrictions enabled.
- **Workspace Confinement**: Execution working directory is pinned to the local repository root (`cwd=repo_root`).
- **Hard Timeout**: Tasks are capped at 20 minutes (1200 seconds) to prevent infinite loops.
- **Single Task Concurrency**: The worker processes tasks strictly one-by-one to avoid file conflicts.

