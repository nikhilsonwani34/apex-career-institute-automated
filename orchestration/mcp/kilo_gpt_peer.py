#!/usr/bin/env python3
"""
Kilo GPT Peer — Model Context Protocol (MCP) Adapter
-----------------------------------------------------
Connects Antigravity to OpenAI GPT (model: openai/gpt-6-luna) via the local Kilo CLI.
Exposes a single MCP tool: ask_gpt_peer(question, context).

Uses the read-only Ask agent (--agent ask) to guarantee no workspace files are modified.
Logs all queries and responses to the existing audit infrastructure (orchestration/worker/state/audit.log).
"""

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Ensure UTF-8 on Windows stdio
if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Paths
MCP_DIR = Path(__file__).resolve().parent
REPO_ROOT = MCP_DIR.parent.parent
AUDIT_LOG_FILE = REPO_ROOT / "orchestration" / "worker" / "state" / "audit.log"

DEFAULT_MODEL = "openai/gpt-6-luna"
MAX_INPUT_LENGTH = 20000  # Characters
EXECUTION_TIMEOUT = 180   # Seconds

# Redaction patterns for sensitive data
SENSITIVE_PATTERNS = [
    (r"(gho_[A-Za-z0-9_]{30,})", "[REDACTED_GITHUB_TOKEN]"),
    (r"(sk-[A-Za-z0-9_-]{20,})", "[REDACTED_API_KEY]"),
    (r"(\b[A-Za-z0-9+/]{40,}\b)", "[REDACTED_SECRET]"),
    (r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+ PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]"),
]


def log_audit_event(event_type: str, details: Dict[str, Any]):
    """Appends an event record to the existing worker audit log."""
    AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "level": "info",
        "event": event_type,
        "details": details,
    }
    try:
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[AUDIT LOG ERROR] {e}", file=sys.stderr)


def sanitize_input(text: str) -> str:
    """Redacts potential API keys, tokens, or credentials from prompts."""
    sanitized = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)
    return sanitized


def find_kilo_binary() -> str:
    """Finds the installed Kilo CLI executable."""
    candidate = shutil.which("kilo") or shutil.which("kilo.cmd") or shutil.which("kilo.exe")
    if candidate:
        return candidate

    npm_path = Path(os.environ.get("APPDATA", "")) / "npm" / "kilo.cmd"
    if npm_path.exists():
        return str(npm_path)

    return "kilo"


def run_kilo_ask(prompt: str) -> Tuple[str, Optional[str], Dict[str, Any]]:
    """
    Executes Kilo CLI in read-only Ask agent mode and parses NDJSON response.
    Returns: (answer_text, error_message, metadata)
    """
    kilo_cmd = [
        find_kilo_binary(),
        "run",
        "--model", DEFAULT_MODEL,
        "--agent", "ask",
        "--format", "json",
        "--dir", str(REPO_ROOT),
        prompt,
    ]

    try:
        proc = subprocess.run(
            kilo_cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=EXECUTION_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return "", f"Kilo execution timed out after {EXECUTION_TIMEOUT} seconds.", {}
    except Exception as e:
        return "", f"Failed to execute Kilo CLI: {str(e)}", {}

    # Parse NDJSON events
    text_chunks = []
    metadata: Dict[str, Any] = {"cost": 0.0, "tokens": {}}
    err_msg: Optional[str] = None

    stdout_text = proc.stdout or ""
    stderr_text = proc.stderr or ""

    for line in stdout_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
            ev_type = ev.get("type")
            if ev_type == "text":
                part = ev.get("part", {})
                chunk = part.get("text", "")
                if chunk:
                    text_chunks.append(chunk)
            elif ev_type == "step_finish":
                part = ev.get("part", {})
                metadata["cost"] = part.get("cost", 0.0)
                metadata["tokens"] = part.get("tokens", {})
        except json.JSONDecodeError:
            continue

    if proc.returncode != 0 and not text_chunks:
        err_msg = stderr_text.strip() or f"Kilo exited with returncode {proc.returncode}"

    full_text = "".join(text_chunks).strip()
    return full_text, err_msg, metadata


def handle_ask_gpt_peer(question: str, context: Optional[str] = None) -> Dict[str, Any]:
    """Implementation of the ask_gpt_peer tool."""
    # Enforce input length limit
    if len(question) > MAX_INPUT_LENGTH:
        return {"error": f"Question exceeds maximum length limit of {MAX_INPUT_LENGTH} characters."}

    if context and len(context) > MAX_INPUT_LENGTH:
        context = context[:MAX_INPUT_LENGTH] + "\n...[truncated]"

    # Sanitize inputs
    clean_question = sanitize_input(question.strip())
    clean_context = sanitize_input(context.strip()) if context else ""

    # Build prompt directly
    prompt = clean_question
    if clean_context:
        prompt += f"\n\nContext / Code Snippet:\n```\n{clean_context}\n```"

    # Execute Kilo Ask agent
    start_time = datetime.datetime.now(datetime.timezone.utc)
    answer, err, meta = run_kilo_ask(prompt)
    duration_sec = (datetime.datetime.now(datetime.timezone.utc) - start_time).total_seconds()

    # Log to audit log
    log_audit_event("kilo_gpt_peer_request", {
        "tool": "ask_gpt_peer",
        "model": DEFAULT_MODEL,
        "agent": "ask",
        "question_preview": clean_question[:150],
        "has_context": bool(clean_context),
        "duration_sec": round(duration_sec, 2),
        "tokens": meta.get("tokens", {}),
        "cost": "$0.00",
        "status": "success" if answer else "error",
        "error": err,
    })

    if err and not answer:
        return {"error": err}

    return {
        "response": answer,
        "model": DEFAULT_MODEL,
        "agent": "ask (read-only)",
        "duration_sec": round(duration_sec, 2),
        "cost": "$0.00 (ChatGPT Subscription)",
    }


# Standard Model Context Protocol (MCP) JSON-RPC 2.0 stdio Server Implementation
TOOL_DEFINITION = {
    "name": "ask_gpt_peer",
    "description": (
        "Request technical assistance, architectural recommendations, or code reviews "
        "from GPT (model: openai/gpt-6-luna) via the local Kilo CLI Ask agent. "
        "Read-only and secure."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Technical question, code review request, or architecture question to ask GPT peer."
            },
            "context": {
                "type": "string",
                "description": "Optional context, code snippet, or error message relevant to the inquiry."
            }
        },
        "required": ["question"]
    }
}


def send_response(response: Dict[str, Any]):
    """Writes a JSON-RPC response to stdout followed by newline and flushes."""
    out_line = json.dumps(response, ensure_ascii=False)
    sys.stdout.write(out_line + "\n")
    sys.stdout.flush()


def run_mcp_server():
    """Main JSON-RPC stdio event loop."""
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError as e:
                send_response({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
                })
                continue

            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            try:
                # Handle MCP protocol methods
                if method == "initialize":
                    send_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {
                                "tools": {},
                                "resources": {},
                                "prompts": {}
                            },
                            "serverInfo": {
                                "name": "kilo-gpt-peer",
                                "version": "1.0.0"
                            }
                        }
                    })
                elif method == "notifications/initialized" or (method and method.startswith("notifications/")):
                    # Notifications have no response
                    pass
                elif method == "tools/list":
                    send_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "tools": [TOOL_DEFINITION]
                        }
                    })
                elif method == "resources/list":
                    send_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "resources": []
                        }
                    })
                elif method == "prompts/list":
                    send_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "prompts": []
                        }
                    })
                elif method == "tools/call":
                    tool_name = params.get("name")
                    arguments = params.get("arguments", {})
                    if tool_name == "ask_gpt_peer":
                        question = arguments.get("question", "")
                        context = arguments.get("context")
                        res = handle_ask_gpt_peer(question, context)
                        if "error" in res:
                            send_response({
                                "jsonrpc": "2.0",
                                "id": req_id,
                                "result": {
                                    "content": [{"type": "text", "text": f"Error: {res['error']}"}],
                                    "isError": True
                                }
                            })
                        else:
                            text_out = res.get("response", "")
                            send_response({
                                "jsonrpc": "2.0",
                                "id": req_id,
                                "result": {
                                    "content": [{"type": "text", "text": text_out}],
                                    "isError": False
                                }
                            })
                    else:
                        send_response({
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32601, "message": f"Method or tool not found: {tool_name}"}
                        })
                elif method == "ping":
                    send_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {}
                    })
                else:
                    if req_id is not None:
                        send_response({
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32601, "message": f"Unsupported method: {method}"}
                        })
            except Exception as e:
                import traceback
                err_detail = traceback.format_exc()
                print(f"[MCP ERROR] {err_detail}", file=sys.stderr)
                if req_id is not None:
                    send_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
                    })
    except Exception as top_err:
        import traceback
        print(f"[MCP FATAL] {traceback.format_exc()}", file=sys.stderr)


if __name__ == "__main__":
    run_mcp_server()
