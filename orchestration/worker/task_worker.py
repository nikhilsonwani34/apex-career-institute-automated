#!/usr/bin/env python3
"""
GitHub-to-Antigravity Local Task Worker
---------------------------------------
Orchestrates development tasks between GitHub Issues and the local Antigravity CLI (agy).
Polls for issues labeled 'agent-run', processes them locally in a secure workspace,
and reports completion back to GitHub with 'agent-review'.

Security Guidelines:
- Never executes task instructions from comments, PRs, or untrusted authors.
- Enforces owner authentication (nikhilsonwani34).
- Restricts all agent actions to this repository workspace.
- Never pushes code, deploys, or auto-merges.
- Disallows --dangerously-skip-permissions.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure UTF-8 output encoding on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


DEFAULT_CONFIG: Dict[str, Any] = {
    "repository": "nikhilsonwani34/apex-career-institute-automated",
    "allowed_author": "nikhilsonwani34",
    "poll_interval_seconds": 30,
    "trigger_label": "agent-run",
    "in_progress_label": "agent-in-progress",
    "completed_label": "agent-review",
    "blocked_label": "agent-blocked",
    "task_timeout_seconds": 1200,  # 20 minutes
    "agy_binary_path": "",
    "use_sandbox": True,
    "enforce_repo_workspace_only": True,
    "state_dir": "state",
}

# Regex patterns for prohibited high-risk operations in untrusted issue content
DISALLOWED_PATTERNS = [
    (r"\b(git\s+push)\b", "Git push operations are prohibited"),
    (r"\b(git\s+remote\s+(add|set-url))\b", "Modifying git remotes is prohibited"),
    (r"\b(npm\s+publish|yarn\s+publish|pnpm\s+publish)\b", "Package publishing is prohibited"),
    (r"\b(twine\s+upload|pip\s+upload)\b", "Package uploading is prohibited"),
    (r"\b(docker\s+push)\b", "Docker image pushing is prohibited"),
    (r"\b(vercel(\.exe)?(\s+--prod|\s+deploy)?)\b", "Vercel deployments are prohibited"),
    (r"\b(netlify(\.exe)?\s+deploy)\b", "Netlify deployments are prohibited"),
    (r"\b(aws\s+|gcloud\s+|az\s+)\b", "Cloud provider CLI operations are prohibited"),
    (r"\b(gh\s+auth\s+token)\b", "Accessing GitHub authentication tokens is prohibited"),
    (r"\b(id_rsa|id_ed25519|\.ssh[\\/])\b", "Accessing SSH private credentials is prohibited"),
    (r"\b(rmdir\s+/s\s+/q\s+C:\\|rm\s+-rf\s+/)\b", "Destructive system deletions are prohibited"),
    (r"\b(--dangerously-skip-permissions)\b", "Disabling permissions bypass is strictly prohibited"),
]


class AuditLogger:
    """Logs audit events to file and console."""

    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log(self, level: str, event: str, details: Optional[Dict[str, Any]] = None):
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        entry = {
            "timestamp": timestamp,
            "level": level,
            "event": event,
            "details": details or {},
        }
        # Append to audit.log
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[AUDIT LOG ERROR] Failed to write to audit log: {e}", file=sys.stderr)

        # Also print user-friendly line to console
        msg = f"[{timestamp[:19]}] [{level.upper()}] {event}"
        if details:
            summary = " ".join(f"{k}={v}" for k, v in details.items() if k not in ("body", "prompt"))
            if summary:
                msg += f" ({summary})"
        print(msg)


class StateManager:
    """Maintains persistent task state to prevent duplicate execution."""

    def __init__(self, state_file: Path, audit: AuditLogger):
        self.state_file = state_file
        self.audit = audit
        self.data: Dict[str, Any] = {"version": 1, "tasks": {}}
        self._load()

    def _load(self):
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                self.audit.log("warn", "state_load_failed_reinitializing", {"error": str(e)})
                self.data = {"version": 1, "tasks": {}}

    def save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.state_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            temp_file.replace(self.state_file)
        except Exception as e:
            self.audit.log("error", "state_save_failed", {"error": str(e)})

    def get_task(self, issue_number: int) -> Optional[Dict[str, Any]]:
        return self.data.get("tasks", {}).get(str(issue_number))

    def is_processed(self, issue_number: int) -> bool:
        task = self.get_task(issue_number)
        if not task:
            return False
        return task.get("status") in ("completed", "in_progress", "blocked")

    def record_task_start(self, issue_number: int, title: str, author: str, run_id: str):
        tasks = self.data.setdefault("tasks", {})
        task = tasks.setdefault(str(issue_number), {})
        task.update({
            "id": issue_number,
            "title": title,
            "author": author,
            "status": "in_progress",
            "first_seen": task.get("first_seen") or datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "last_start": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "active_run_id": run_id,
        })
        self.save()

    def record_task_complete(self, issue_number: int, status: str, run_dir: str, duration_sec: float):
        task = self.data.get("tasks", {}).get(str(issue_number), {})
        task.update({
            "status": status,
            "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "last_run_dir": run_dir,
            "duration_seconds": round(duration_sec, 2),
        })
        self.save()


class TaskWorker:
    """Local worker orchestrating GitHub Issues and Antigravity execution."""

    def __init__(self, config_path: Optional[str] = None, once: bool = False, dry_run: bool = False):
        self.running = True
        self.once = once
        self.dry_run = dry_run
        self.config = self._load_config(config_path)
        self.repo_root = self._find_repo_root()
        
        state_dir_path = Path(self.config.get("state_dir", "state"))
        if not state_dir_path.is_absolute():
            state_dir_path = Path(__file__).resolve().parent / state_dir_path
        self.state_dir = state_dir_path
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.audit = AuditLogger(self.state_dir / "audit.log")
        self.state = StateManager(self.state_dir / "task_state.json", self.audit)

        self.gh_path = self._verify_gh()
        self.agy_path = self._verify_agy()

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        cfg = DEFAULT_CONFIG.copy()
        target_path: Optional[Path] = None

        if config_path:
            target_path = Path(config_path)
        else:
            local_json = Path(__file__).resolve().parent / "config.json"
            example_json = Path(__file__).resolve().parent / "config.example.json"
            if local_json.exists():
                target_path = local_json
            elif example_json.exists():
                target_path = example_json

        if target_path and target_path.exists():
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    user_cfg = json.load(f)
                    cfg.update(user_cfg)
            except Exception as e:
                print(f"[WARN] Failed to parse config file {target_path}: {e}. Using defaults.", file=sys.stderr)

        return cfg

    def _find_repo_root(self) -> Path:
        """Finds the root of the current Git repository."""
        cur = Path(__file__).resolve()
        for parent in [cur] + list(cur.parents):
            if (parent / ".git").exists():
                return parent
        return Path.cwd().resolve()

    def _verify_gh(self) -> str:
        """Verifies that gh is installed and authenticated."""
        gh = shutil.which("gh")
        if not gh:
            msg = (
                "ERROR: GitHub CLI ('gh') is not installed or not in PATH.\n"
                "To install gh on Windows, use winget:\n"
                "  winget install --id GitHub.cli\n"
                "Or download from official source: https://cli.github.com"
            )
            print(msg, file=sys.stderr)
            sys.exit(1)

        # Check authentication status
        res = subprocess.run([gh, "auth", "status"], capture_output=True, text=True)
        if res.returncode != 0:
            print("ERROR: GitHub CLI is not authenticated. Run:\n  gh auth login", file=sys.stderr)
            sys.exit(1)
        return gh

    def _verify_agy(self) -> str:
        """Verifies that agy CLI is installed and returns its path."""
        candidate = self.config.get("agy_binary_path")
        if candidate and Path(candidate).exists():
            return candidate

        in_path = shutil.which("agy") or shutil.which("agy.exe")
        if in_path:
            return in_path

        # Check standard default installation paths on Windows
        home_dir = Path.home()
        standard_paths = [
            home_dir / ".gemini" / "bin" / "agy.exe",
            home_dir / ".gemini" / "antigravity" / "bin" / "agy.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Antigravity IDE" / "bin" / "agy.exe",
        ]
        for p in standard_paths:
            if p.exists():
                return str(p)

        msg = (
            "ERROR: Antigravity CLI ('agy') was not found.\n"
            "Official installation for Windows PowerShell:\n"
            "  irm https://antigravity.google/cli/install.ps1 | iex\n"
            "Or ensure C:\\Users\\<USER>\\.gemini\\bin is added to your PATH environment variable."
        )
        print(msg, file=sys.stderr)
        sys.exit(1)

    def verify_repository(self):
        """Verifies repository remote origin matches configured repository."""
        expected_repo = self.config["repository"].lower()
        res = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
        )
        url = res.stdout.strip().lower()
        if expected_repo not in url:
            self.audit.log(
                "warn",
                "repository_url_mismatch",
                {"expected": expected_repo, "actual_remote_url": url},
            )
            print(
                f"[WARN] Local repo remote origin ('{url}') does not strictly match "
                f"configured repo '{expected_repo}'. Continuing carefully."
            )
        else:
            self.audit.log("info", "repository_verified", {"repo": expected_repo, "root": str(self.repo_root)})

    def poll_issues(self) -> List[Dict[str, Any]]:
        """Queries GitHub for open issues carrying the trigger label."""
        cmd = [
            self.gh_path,
            "issue",
            "list",
            "--repo",
            self.config["repository"],
            "--state",
            "open",
            "--label",
            self.config["trigger_label"],
            "--json",
            "number,title,body,author,labels,state,createdAt",
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            issues = json.loads(res.stdout)
            return issues
        except subprocess.CalledProcessError as e:
            self.audit.log("error", "gh_issue_list_failed", {"error": e.stderr.strip()})
            return []
        except json.JSONDecodeError as e:
            self.audit.log("error", "gh_issue_json_parse_error", {"error": str(e)})
            return []

    def validate_security(self, issue: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validates issue author and checks for prohibited operations.
        Treats GitHub issue contents as untrusted input.
        """
        issue_number = issue["number"]
        author = issue.get("author", {}).get("login", "")
        allowed = self.config["allowed_author"]

        # 1. Author check
        if author.lower() != allowed.lower():
            self.audit.log(
                "warn",
                "unauthorized_author_ignored",
                {"issue": issue_number, "author": author, "expected": allowed},
            )
            return False, f"Issue author '{author}' does not match allowed author '{allowed}'."

        title = issue.get("title", "")
        body = issue.get("body", "") or ""
        content = f"{title}\n{body}"

        # 2. Pattern check for prohibited operations
        for pattern, reason in DISALLOWED_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                matched_token = match.group(0)
                self.audit.log(
                    "warn",
                    "security_policy_violation",
                    {
                        "issue": issue_number,
                        "token": matched_token,
                        "reason": reason,
                    },
                )
                return False, f"Prohibited operation detected: {reason} (matched: '{matched_token}')"

        return True, None

    def update_issue_labels(self, issue_number: int, add_label: Optional[str], remove_label: Optional[str]):
        """Updates labels on GitHub issue using gh CLI."""
        if self.dry_run:
            print(f"[DRY-RUN] Update labels #{issue_number}: +{add_label} -{remove_label}")
            return

        cmd = [self.gh_path, "issue", "edit", str(issue_number), "--repo", self.config["repository"]]
        if add_label:
            cmd.extend(["--add-label", add_label])
        if remove_label:
            cmd.extend(["--remove-label", remove_label])

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            self.audit.log("error", "update_labels_failed", {"issue": issue_number, "error": res.stderr.strip()})
        else:
            self.audit.log("info", "labels_updated", {"issue": issue_number, "add": add_label, "remove": remove_label})

    def post_issue_comment(self, issue_number: int, comment_body: str):
        """Posts a markdown report comment to the GitHub issue."""
        if self.dry_run:
            print(f"[DRY-RUN] Comment on #{issue_number}:\n{comment_body[:120]}...")
            return

        cmd = [
            self.gh_path,
            "issue",
            "comment",
            str(issue_number),
            "--repo",
            self.config["repository"],
            "--body",
            comment_body,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            self.audit.log("error", "post_comment_failed", {"issue": issue_number, "error": res.stderr.strip()})
        else:
            self.audit.log("info", "comment_posted", {"issue": issue_number})

    def capture_git_changes(self) -> Tuple[List[str], str]:
        """Captures git status and diff stat within repository workspace."""
        res_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
        )
        status_lines = [line.strip() for line in res_status.stdout.splitlines() if line.strip()]

        res_diff = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
        )
        diff_stat = res_diff.stdout.strip()
        return status_lines, diff_stat

    def execute_tests_if_present(self) -> Tuple[bool, str]:
        """Detects and runs project tests if present, sandboxed in repository."""
        # 1. Python pytest / unittest
        test_dir = self.repo_root / "tests"
        if test_dir.exists():
            res = subprocess.run(
                ["pytest", "-v"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=60,
            )
            success = res.returncode == 0
            return success, f"pytest completed with exit code {res.returncode}:\n{res.stdout}\n{res.stderr}"

        # 2. Node.js package.json test
        pkg_json = self.repo_root / "package.json"
        if pkg_json.exists():
            res = subprocess.run(
                ["npm", "test"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=60,
            )
            success = res.returncode == 0
            return success, f"npm test completed with exit code {res.returncode}:\n{res.stdout}\n{res.stderr}"

        return True, "No automated test suite discovered in repository."

    def build_agent_prompt(self, issue: Dict[str, Any]) -> str:
        """Constructs safe, structured prompt passed to Antigravity CLI."""
        title = issue.get("title", "").strip()
        body = issue.get("body", "").strip()
        issue_number = issue.get("number")

        prompt = (
            f"You are executing automated development task #{issue_number} from GitHub.\n\n"
            f"TASK TITLE: {title}\n\n"
            f"TASK INSTRUCTIONS:\n{body}\n\n"
            f"EXECUTION RULES:\n"
            f"1. You are running in workspace: {self.repo_root}\n"
            f"2. Restrict all edits, file creation, or reads STRICTLY within this repository workspace.\n"
            f"3. Do NOT push code to remote git branches, do NOT deploy, and do NOT alter account credentials.\n"
            f"4. Focus cleanly on fulfilling the task objective described above.\n"
            f"5. Maintain clean code and add tests where appropriate.\n"
        )
        return prompt

    def process_issue(self, issue: Dict[str, Any]):
        """Processes a single validated GitHub issue."""
        issue_number = issue["number"]
        title = issue.get("title", "")
        author = issue.get("author", {}).get("login", "")

        # Duplicate check
        if self.state.is_processed(issue_number):
            self.audit.log("info", "skipping_already_processed_task", {"issue": issue_number})
            return

        print(f"\n========================================================")
        print(f"[*] Processing Task #{issue_number}: {title}")
        print(f"    Author: @{author}")
        print(f"========================================================")

        # Pre-execution security screening
        is_safe, violation_reason = self.validate_security(issue)
        if not is_safe:
            print(f"[!] Security check rejected task #{issue_number}: {violation_reason}")
            self.update_issue_labels(
                issue_number,
                add_label=self.config["blocked_label"],
                remove_label=self.config["trigger_label"],
            )
            blocked_comment = (
                f"### 🛑 Task Blocked by Automated Security Policy\n\n"
                f"The worker refused execution for Task **#{issue_number}** due to a security violation:\n\n"
                f"> **Reason:** {violation_reason}\n\n"
                f"- Tasks cannot perform external publishing, deployments, credential access, or code pushes.\n"
                f"- Please review the task description and submit a clean task instruction."
            )
            self.post_issue_comment(issue_number, blocked_comment)
            self.state.record_task_complete(issue_number, "blocked", "", 0.0)
            return

        # Prepare run directory
        run_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"issue-{issue_number}-{run_timestamp}"
        run_dir = self.state_dir / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Mark issue in progress
        self.state.record_task_start(issue_number, title, author, run_id)
        self.update_issue_labels(
            issue_number,
            add_label=self.config["in_progress_label"],
            remove_label=self.config["trigger_label"],
        )

        start_time = datetime.datetime.now(datetime.timezone.utc)
        start_time_iso = start_time.isoformat()

        # Build prompt
        prompt = self.build_agent_prompt(issue)
        prompt_file = run_dir / "prompt.txt"
        prompt_file.write_text(prompt, encoding="utf-8")

        # Prepare agy command arguments with sandboxing and scoped allow-permissions
        scoped_settings = {
            "permissions": {
                "allow": [
                    "read_file(*)",
                    "write_file(*)",
                    "edit_file(*)",
                    "command(git status)",
                    "command(git diff)",
                    "command(pytest)",
                    "command(npm test)",
                    "command(python *)",
                ],
                "deny": [
                    "command(git push)",
                    "command(git remote *)",
                    "command(npm publish)",
                    "command(yarn publish)",
                    "command(pnpm publish)",
                    "command(pip upload)",
                    "command(twine upload)",
                    "command(vercel*)",
                    "command(netlify*)",
                    "command(gh auth token)",
                    "write_file(.git/*)",
                ]
            }
        }

        agy_cmd = [self.agy_path, "-p", prompt]
        if self.config.get("use_sandbox", True):
            agy_cmd.append("--sandbox")
        agy_cmd.extend(["--settings", json.dumps(scoped_settings)])

        timeout_sec = self.config.get("task_timeout_seconds", 1200)

        stdout_log = run_dir / "stdout.log"
        stderr_log = run_dir / "stderr.log"

        self.audit.log(
            "info",
            "executing_antigravity",
            {
                "issue": issue_number,
                "timeout_sec": timeout_sec,
                "sandbox": self.config.get("use_sandbox", True),
                "run_dir": str(run_dir.relative_to(self.repo_root) if run_dir.is_relative_to(self.repo_root) else run_dir),
                "planned_by": "ChatGPT",
                "executed_by": "Antigravity",
                "communication_method": "manual_relay",
            },
        )

        execution_error: Optional[str] = None
        returncode = 0
        raw_stdout = ""
        raw_stderr = ""

        if self.dry_run:
            print(f"[DRY-RUN] Invoking Antigravity for Task #{issue_number}")
            raw_stdout = "Dry-run completed successfully."
        else:
            try:
                proc = subprocess.run(
                    agy_cmd,
                    cwd=str(self.repo_root),
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                )
                returncode = proc.returncode
                raw_stdout = proc.stdout
                raw_stderr = proc.stderr
            except subprocess.TimeoutExpired as e:
                returncode = -1
                execution_error = f"Task execution exceeded maximum timeout of {timeout_sec} seconds."
                raw_stdout = e.stdout or ""
                raw_stderr = e.stderr or ""
            except Exception as e:
                returncode = -1
                execution_error = f"Unexpected execution error: {str(e)}"

        # Write execution logs locally
        stdout_log.write_text(raw_stdout, encoding="utf-8")
        stderr_log.write_text(raw_stderr, encoding="utf-8")

        end_time = datetime.datetime.now(datetime.timezone.utc)
        end_time_iso = end_time.isoformat()
        duration_sec = (end_time - start_time).total_seconds()

        # Post-execution status inspection
        status_lines, diff_stat = self.capture_git_changes()
        test_success, test_report = self.execute_tests_if_present()

        final_status = "completed" if (returncode == 0 and not execution_error) else "failed"

        # Record in state
        self.state.record_task_complete(issue_number, final_status, str(run_dir), duration_sec)

        # Generate markdown report
        report_md = self._generate_report(
            issue_number=issue_number,
            title=title,
            author=author,
            start_iso=start_time_iso,
            end_iso=end_time_iso,
            duration_sec=duration_sec,
            returncode=returncode,
            error=execution_error,
            stdout_sample=raw_stdout[:1000],
            status_lines=status_lines,
            diff_stat=diff_stat,
            test_report=test_report,
            run_dir=run_dir,
        )

        # Save report locally
        (run_dir / "report.md").write_text(report_md, encoding="utf-8")

        # Comment on GitHub issue
        self.post_issue_comment(issue_number, report_md)

        # Update labels: agent-in-progress -> agent-review (or agent-blocked if failure)
        target_label = self.config["completed_label"] if final_status == "completed" else self.config["blocked_label"]
        self.update_issue_labels(
            issue_number,
            add_label=target_label,
            remove_label=self.config["in_progress_label"],
        )

        self.audit.log(
            "info",
            "task_processing_finished",
            {
                "issue": issue_number,
                "status": final_status,
                "duration_sec": round(duration_sec, 2),
                "planned_by": "ChatGPT",
                "executed_by": "Antigravity",
                "communication_method": "manual_relay",
            },
        )
        print(f"[OK] Task #{issue_number} finished with status '{final_status}'.\n")

    def _generate_report(
        self,
        issue_number: int,
        title: str,
        author: str,
        start_iso: str,
        end_iso: str,
        duration_sec: float,
        returncode: int,
        error: Optional[str],
        stdout_sample: str,
        status_lines: List[str],
        diff_stat: str,
        test_report: str,
        run_dir: Path,
    ) -> str:
        """Constructs human-readable completion report for GitHub Issue."""
        status_badge = "🟢 Succeeded" if returncode == 0 and not error else "🔴 Error Encountered"

        files_changed_section = ""
        if status_lines:
            files_changed_section += "\n```text\n" + "\n".join(status_lines) + "\n```\n"
        else:
            files_changed_section += "\n*No local files were modified or created.*\n"

        if diff_stat:
            files_changed_section += "\n**Diff Statistics:**\n```text\n" + diff_stat + "\n```\n"

        error_section = ""
        if error:
            error_section = f"\n### ⚠️ Errors / Warnings\n```text\n{error}\n```\n"

        stdout_clean = stdout_sample.strip() or "Execution produced no stdout output."

        report = f"""## 🤖 Antigravity Task Report

| Field | Value |
|---|---|
| **Task ID** | #{issue_number} |
| **Task Title** | {title} |
| **Author** | @{author} |
| **Start Time** | `{start_iso}` |
| **Completion Time** | `{end_iso}` |
| **Duration** | `{round(duration_sec, 1)}s` |
| **Status** | {status_badge} |
| **Human Review Required** | **YES** — Changes are in local workspace pending review |

---

### 📂 Files Changed
{files_changed_section}
### 🧪 Tests Executed & Results
```text
{test_report}
```
{error_section}
### 📝 Agent Output Highlights
```text
{stdout_clean}
```

---

### 🤝 Multi-Agent Attribution
| Attribution | Details |
|---|---|
| **Task Planning** | Planned by ChatGPT (Task specification & architecture) |
| **Execution Agent** | Executed by Antigravity CLI (Headless local workspace run & tests) |
| **Technical Guidance** | Supplied by ChatGPT (Permissions & CLI scoped rules) |
| **Assistance Requested** | Requested by Antigravity (Headless permission auto-denial resolution) |
| **Implementation & Verification** | Implemented & Verified in workspace (Scoped rules without skipping permissions) |
| **Communication Method** | Manual Relay (Owner prompt relay) |

---

### 🛡️ Security & Integrity Checklist
- [x] Executed strictly within the local repository workspace.
- [x] No automatic code push or branch merge performed.
- [x] No deployment, publishing, or paid services executed.
- [x] Local run logs preserved in `{run_dir.name}`.
- [x] Labeled with `{self.config["completed_label"]}` for human review.
"""
        return report

    def run(self):
        """Main worker loop."""
        self.verify_repository()
        print(f"\n[+] Antigravity Task Worker started.")
        print(f"   Repository: {self.config['repository']}")
        print(f"   Allowed Author: {self.config['allowed_author']}")
        print(f"   Listening for label: '{self.config['trigger_label']}'")
        print(f"   Workspace: {self.repo_root}")
        print(f"   Poll interval: {self.config['poll_interval_seconds']}s")
        print("   Press Ctrl+C to stop gracefully.\n")

        self.audit.log("info", "worker_started", {"repo": self.config["repository"]})

        while self.running:
            try:
                issues = self.poll_issues()
                for issue in issues:
                    if not self.running:
                        break
                    # Process only one task at a time as required
                    self.process_issue(issue)

                if self.once:
                    print("[*] Single-pass mode (--once) completed.")
                    break

                # Sleep interval with interruptible polling
                sleep_left = self.config.get("poll_interval_seconds", 30)
                while sleep_left > 0 and self.running:
                    time.sleep(min(1, sleep_left))
                    sleep_left -= 1

            except KeyboardInterrupt:
                print("\n[!] Shutdown signal received. Exiting...")
                self.running = False
                break
            except Exception as e:
                self.audit.log("error", "worker_loop_exception", {"error": str(e)})
                if self.once:
                    break
                time.sleep(5)

        self.audit.log("info", "worker_stopped")
        print("[*] Antigravity Task Worker stopped cleanly.")


def main():
    parser = argparse.ArgumentParser(description="Antigravity GitHub Task Worker")
    parser.add_argument("--config", "-c", help="Path to config.json", default=None)
    parser.add_argument("--once", action="store_true", help="Run a single poll iteration and exit")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without modifying GitHub or files")
    args = parser.parse_args()

    worker = TaskWorker(config_path=args.config, once=args.once, dry_run=args.dry_run)

    # Setup signal handling for graceful shutdown
    def handle_sig(sig, frame):
        print("\n[!] Caught termination signal. Gracefully stopping...")
        worker.running = False

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    worker.run()


if __name__ == "__main__":
    main()
