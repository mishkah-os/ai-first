"""
track3_engine.py — Track 3 Clean MAS Engine.

Stateless, text-only AI interaction with array-based mutations protocol.
Uses SurgicalSkeletonizer for parsing — no reinventing the wheel.
"""

import json
import hashlib
import os
import re
import shutil
import subprocess
import logging
import time
import tempfile
from datetime import datetime
from threading import Lock
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request as GoogleAuthRequest
    HAS_GOOGLE_AUTH = True
except ImportError:
    HAS_GOOGLE_AUTH = False

from surgical_skeletonizer import SurgicalSkeletonizer
from track3_logger import ai_logger
from track3_object_store import Track3ObjectStore
from services.provider_credentials import provider_credentials

logger = logging.getLogger(__name__)

# Languages we support for block-level analysis
SUPPORTED_EXTENSIONS = {'.py', '.js', '.jsx', '.ts', '.tsx', '.cpp', '.c', '.h', '.hpp'}
# Extensions where we extract <script> blocks only
HTML_EXTENSIONS = {'.html', '.htm'}
TRACK3_CONTEXT_SNIPPET_LIMIT = 2000


class CredentialQueue:
    """Persisted round-robin credential selector."""

    def __init__(self, state_path: Optional[str] = None):
        default_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "set",
            "provider_key_queue.json",
        )
        self.state_path = state_path or os.environ.get("TRACK3_KEY_QUEUE_FILE", default_path)
        self._lock = Lock()

    def next(self, pool_name: str, values: List[str]) -> str:
        cleaned = [value.strip() for value in values if str(value).strip()]
        if not cleaned:
            return ""
        if len(cleaned) == 1:
            return cleaned[0]

        with self._lock:
            state = self._load_state()
            current_index = int(state.get(pool_name, 0) or 0)
            selected = cleaned[current_index % len(cleaned)]
            state[pool_name] = (current_index + 1) % len(cleaned)
            self._save_state(state)
            return selected

    def _load_state(self) -> Dict[str, int]:
        if not os.path.exists(self.state_path):
            return {}
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError, ValueError):
            pass
        return {}

    def _save_state(self, state: Dict[str, int]) -> None:
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)


# ────────────────────── AI Provider Client ──────────────────────

class AIProviderClient:
    """Unified text-only client for all AI providers."""

    def __init__(self, catalog_path: str = None):
        self.catalog_path = catalog_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'track3_providers.json'
        )
        self.catalog = self._load_catalog()
        self.credential_queue = CredentialQueue()

    def _load_catalog(self) -> dict:
        try:
            with open(self.catalog_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"providers": {}}

    def list_providers(self) -> List[dict]:
        """Return available providers with their models."""
        result = []
        for pid, pdata in self.catalog.get("providers", {}).items():
            models = []
            for mid, mdata in pdata.get("models", {}).items():
                models.append({"id": mid, **mdata})
            auth = pdata.get("auth", {})
            env_name = auth.get("env", "")
            pool_env_name = pdata.get("keys_pool", "")
            auth_type = auth.get("type")
            has_key = provider_credentials.has_any(pid, env_name=env_name, pool_env_name=pool_env_name)
            if auth_type in {"cli_file", "cli_stdout"}:
                has_key = self._cli_ready(pid, pdata)
            result.append({
                "id": pid,
                "label": pdata.get("label", pid),
                "models": models,
                "auth_env": env_name,
                "has_key": has_key,
                "disabled": bool(pdata.get("disabled", False)),
                "disabled_reason": pdata.get("disabled_reason", ""),
            })
        return result

    def _cli_ready(self, provider_id: str, provider: dict) -> bool:
        if provider_id == "claude_cli":
            claude_bin = (
                os.environ.get("CLAUDE_CLI_BIN")
                or shutil.which("claude")
                or os.path.expanduser("~/.local/bin/claude")
            )
            return bool(claude_bin and os.path.exists(claude_bin))

        template = str(provider.get("cli_template", "")).strip()
        if not template:
            return False
        binary = template.split(None, 1)[0]
        return bool(shutil.which(binary))

    @staticmethod
    def _expand_cli_value(value: Any) -> str:
        raw = str(value or "")

        def _replace(match: re.Match[str]) -> str:
            expr = match.group(1).strip()
            if expr.startswith("env:"):
                return os.environ.get(expr[4:].strip(), "")
            return match.group(0)

        return re.sub(r"\{([^{}]+)\}", _replace, raw)

    def _build_cli_env(self, provider: dict) -> Dict[str, str]:
        env = os.environ.copy()
        for key in provider.get("cli_unset_env", []) or []:
            env.pop(str(key), None)
        for key, value in (provider.get("cli_env", {}) or {}).items():
            expanded = self._expand_cli_value(value)
            if expanded:
                env[str(key)] = expanded
        return env

    def _resolve_credential(self, provider_id: str, provider: dict, api_key: Optional[str]) -> str:
        if api_key:
            return api_key

        auth = provider.get("auth", {})
        env_var = auth.get("env", "")
        pool_env_var = provider.get("keys_pool", "")
        auth_type = auth.get("type")

        if auth_type == "gcp_service_account":
            return provider_credentials.get_service_account_path(provider_id, env_name=env_var)

        values = provider_credentials.get_pool(provider_id, env_name=env_var, pool_env_name=pool_env_var)
        if values:
            queue_name = f"{provider_id}:{pool_env_var or env_var or 'keys'}"
            return self.credential_queue.next(queue_name, values)
        return ""

    def call(self, provider_id: str, model_id: str, prompt: str,
             system_prompt: str = "", api_key: str = None, source: str = "system") -> str:
        """Call an AI provider and return text response."""
        import urllib.request
        import urllib.error

        providers = self.catalog.get("providers", {})
        provider = providers.get(provider_id)
        if not provider:
            raise ValueError(f"Unknown provider: {provider_id}")

        auth = provider.get("auth", {})
        
        # 1. Resolve API key or service account credentials.
        actual_key = self._resolve_credential(provider_id, provider, api_key)
        
        if not actual_key and auth.get("type") not in ["cli_file", "cli_stdout"]:
            raise ValueError(f"No credentials provided for {provider_id}. Set {auth.get('env', '?')} or pass api_key.")

        # 2. Extract configuration
        url = provider.get("base_url", "")
        # Replace Vertex variables if present
        if "{region}" in url:
            url = url.replace("{region}", provider.get("region", "us-central1"))
        if "{project_id}" in url:
            url = url.replace("{project_id}", provider.get("project_id", ""))
            
        url = url.replace("{model}", model_id)
        
        if auth.get("type") in ["cli_file", "cli_stdout"]:
            import tempfile

            if provider_id == "claude_cli":
                return self._call_claude_cli(model_id, prompt, system_prompt, source)
            
            # For CLI tools, merge system prompt and user prompt into a raw text file
            raw_text = f"System Instruction:\n{system_prompt}\n\nTask:\n{prompt}"
            
            with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as prompt_f:
                prompt_f.write(raw_text)
                prompt_path = prompt_f.name
                
            out_path = prompt_path + ".out"
            
            cmd = provider.get("cli_template", "")
            cmd = cmd.replace("{model}", model_id)
            cmd = cmd.replace("{prompt_file}", prompt_path)
            cmd = cmd.replace("{out_file}", out_path)
            cli_env = self._build_cli_env(provider)
            
            start_time = time.time()
            try:
                # Execute CLI command via bash
                res = subprocess.run(
                    ["bash", "-c", cmd],
                    capture_output=True,
                    text=True,
                    env=cli_env,
                )

                # Raise immediately on non-zero exit so callers get a real error
                # instead of silently receiving an empty string.
                if res.returncode != 0:
                    stderr_snippet = (res.stderr or "").strip()[:400]
                    stdout_snippet = (res.stdout or "").strip()[:400]
                    raise RuntimeError(
                        f"CLI exited {res.returncode} for {provider_id}/{model_id}.\n"
                        f"Command: {cmd}\nStderr: {stderr_snippet}\nStdout: {stdout_snippet}"
                    )

                if auth.get("type") == "cli_file":
                    if os.path.exists(out_path):
                        with open(out_path, "r", encoding="utf-8") as f:
                            answer = f.read()
                    else:
                        raise RuntimeError(
                            f"CLI did not produce out_file.\n"
                            f"Command: {cmd}\nStderr: {res.stderr}\nStdout: {res.stdout}"
                        )
                else:
                    # cli_stdout — strip trailing newline added by most CLIs
                    answer = res.stdout.rstrip("\n")
                    if not answer.strip():
                        stderr_snippet = (res.stderr or "").strip()[:400]
                        raise RuntimeError(
                            f"CLI produced empty stdout for {provider_id}/{model_id}.\n"
                            f"Command: {cmd}\nStderr: {stderr_snippet}"
                        )

                latency_ms = (time.time() - start_time) * 1000
                ai_logger.log_request(provider_id, model_id, source, raw_text, answer, latency_ms, 0)
                return answer
            finally:
                if os.path.exists(prompt_path): os.remove(prompt_path)
                if os.path.exists(out_path): os.remove(out_path)


        # Build body for HTTP Requests
        if auth.get("type") == "query_param":
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}{auth['param']}={actual_key}"

        # Build body
        body = json.dumps(provider["body_template"], ensure_ascii=False)
        body = body.replace("{prompt}", json.dumps(prompt)[1:-1])
        body = body.replace("{system_prompt}", json.dumps(system_prompt)[1:-1])
        body = body.replace("{model}", model_id)
        body_bytes = body.encode("utf-8")

        # 4. Build headers & Auth
        headers = dict(provider.get("headers", {}))
        
        if auth.get("type") == "bearer":
            headers["Authorization"] = f"Bearer {actual_key}"
        elif auth.get("type") == "header":
            headers[auth["header"]] = actual_key
        elif auth.get("type") == "gcp_service_account":
            # Native Vertex AI support
            if not HAS_GOOGLE_AUTH:
                raise RuntimeError("google-auth is required for Vertex AI. Run: pip install google-auth")
            
            if not os.path.isfile(actual_key):
                raise ValueError(f"Vertex AI requires a valid Service Account JSON file path. Not found: {actual_key}")
                
            creds = service_account.Credentials.from_service_account_file(
                actual_key, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            auth_req = GoogleAuthRequest()
            creds.refresh(auth_req)
            headers["Authorization"] = f"Bearer {creds.token}"

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")

        start_time = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"AI API error {e.code}: {error_body[:500]}")

        latency_ms = (time.time() - start_time) * 1000

        # Extract tokens
        tokens = data.get("usage", {}).get("total_tokens", data.get("usageMetadata", {}).get("totalTokenCount", 0))

        # Extract text from response
        answer = self._extract_response(data, provider.get("response_path", ""))
        
        # Log to observability storage
        ai_logger.log_request(provider_id, model_id, source, body, answer, latency_ms, tokens)
        
        return answer

    def _extract_response(self, data: dict, path: str) -> str:
        """Extract text from nested response using dot-separated path."""
        obj = data
        try:
            for key in path.split("."):
                if key.isdigit():
                    obj = obj[int(key)]
                else:
                    obj = obj[key]
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(
                f"Cannot extract response at path '{path}': {e}. "
                f"Response keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}"
            )
        return str(obj)

    @staticmethod
    def _escape_json_value(text: str) -> str:
        """Escape text for safe embedding inside JSON string."""
        return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")

    def _call_claude_cli(self, model_id: str, prompt: str, system_prompt: str, source: str) -> str:
        """Call Claude Code using its documented headless flags instead of shell piping."""
        claude_bin = (
            os.environ.get("CLAUDE_CLI_BIN")
            or shutil.which("claude")
            or os.path.expanduser("~/.local/bin/claude")
        )
        if not claude_bin or not os.path.exists(claude_bin):
            raise RuntimeError(
                "Claude Code CLI is not installed or not on PATH. "
                "Install it, or set CLAUDE_CLI_BIN to the claude binary path."
            )

        normalized_model = self._normalize_claude_cli_model(model_id)
        cmd = [
            claude_bin,
            "--print",
            "--no-session-persistence",
            "--input-format",
            "text",
            "--output-format",
            "text",
            "--model",
            normalized_model,
            "--permission-mode",
            "default",
        ]
        if system_prompt:
            cmd.extend(["--append-system-prompt", system_prompt])
        cmd.extend(["--tools", ""])

        start_time = time.time()
        env = os.environ.copy()
        claude_home = os.environ.get("CLAUDE_HOME", "").strip()
        if claude_home:
            env["HOME"] = claude_home
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(self.catalog_path)),
            input=prompt,
            env=env,
        )
        if res.returncode != 0:
            stderr_snippet = (res.stderr or "").strip()[:600]
            stdout_snippet = (res.stdout or "").strip()[:600]
            raise RuntimeError(
                f"Claude CLI exited {res.returncode} for {model_id}.\n"
                f"Command: {' '.join(cmd[:-1])} [prompt]\nStderr: {stderr_snippet}"
                f"\nStdout: {stdout_snippet}"
            )

        answer = res.stdout.strip()
        if not answer:
            stderr_snippet = (res.stderr or "").strip()[:600]
            raise RuntimeError(
                f"Claude CLI produced empty stdout for {model_id}.\n"
                f"Command: {' '.join(cmd[:-1])} [prompt]\nStderr: {stderr_snippet}"
            )

        latency_ms = (time.time() - start_time) * 1000
        raw_prompt = prompt if not system_prompt else f"System Instruction:\n{system_prompt}\n\nTask:\n{prompt}"
        ai_logger.log_request("claude_cli", model_id, source, raw_prompt, answer, latency_ms, 0)
        return answer

    @staticmethod
    def _normalize_claude_cli_model(model_id: str) -> str:
        """Map legacy API-style model ids to Claude Code CLI aliases."""
        lowered = (model_id or "").strip().lower()
        if not lowered:
            return "sonnet"
        if lowered in {"sonnet", "haiku", "opus"}:
            return lowered
        if "haiku" in lowered:
            return "haiku"
        if "opus" in lowered:
            return "opus"
        if "sonnet" in lowered:
            return "sonnet"
        return model_id


def _normalize_track3_context_files(root_dir: str, file_paths: Optional[List[str]]) -> List[str]:
    root_abs = os.path.abspath(root_dir)
    supported_exts = SUPPORTED_EXTENSIONS | HTML_EXTENSIONS
    normalized: List[str] = []
    seen = set()

    for raw_path in file_paths or []:
        candidate = str(raw_path or "").strip()
        if not candidate:
            continue
        abs_path = candidate if os.path.isabs(candidate) else os.path.join(root_abs, candidate)
        abs_path = os.path.abspath(abs_path)
        if not abs_path.startswith(root_abs + os.sep) and abs_path != root_abs:
            continue
        if not os.path.isfile(abs_path):
            continue
        if os.path.splitext(abs_path)[1].lower() not in supported_exts:
            continue
        if abs_path in seen:
            continue
        seen.add(abs_path)
        normalized.append(abs_path)

    return normalized


def _compact_track3_path(relative_path: str, limit: int = 48) -> str:
    normalized = str(relative_path or "").replace("\\", "/")
    if len(normalized) <= limit:
        return normalized
    head = max(10, limit // 2 - 2)
    tail = max(10, limit - head - 3)
    return f"{normalized[:head]}...{normalized[-tail:]}"


def _track3_block_priority(block: dict) -> tuple[int, int]:
    kind = str((block or {}).get("kind") or "block")
    lines = (block or {}).get("lines") or [0, 0]
    start_line = int(lines[0] or 0)
    priority_map = {
        "class_def": 0,
        "function_def": 0,
        "method_def": 0,
        "async_function_def": 0,
        "route_def": 1,
        "object_def": 2,
        "variable_def": 3,
        "integrity_check": 8,
        "import": 9,
        "file_body": 10,
    }
    return (priority_map.get(kind, 4), start_line)


def track3_context_snippet(
    root_dir: str,
    file_paths: Optional[List[str]] = None,
    max_chars: int = TRACK3_CONTEXT_SNIPPET_LIMIT,
    max_files: int = 6,
    max_blocks_per_file: int = 4,
) -> str:
    """
    Build a compact Track3 object summary for worker prompts.

    The snippet intentionally excludes bodies and summaries. It only exposes
    stable object ids plus enough structure for agents to request reveals later.
    """
    root_abs = os.path.abspath(str(root_dir or "").strip() or ".")
    max_chars = max(240, int(max_chars or TRACK3_CONTEXT_SNIPPET_LIMIT))
    max_files = max(1, int(max_files or 1))
    max_blocks_per_file = max(1, int(max_blocks_per_file or 1))

    if not os.path.isdir(root_abs):
        return f"TRACK3_CONTEXT unavailable root_missing={root_abs}"

    store = Track3ObjectStore(root_abs)
    normalized_files = _normalize_track3_context_files(root_abs, file_paths)
    if normalized_files:
        store.ensure_artifacts(normalized_files)

    project_meta = store.load_project_meta() or {}
    index_payload = store.load_index() or {"entries": []}

    project_id = str(project_meta.get("project_id") or f"PRJ_{hashlib.sha1(root_abs.encode('utf-8')).hexdigest()[:16]}")
    root_name = str(project_meta.get("root_name") or os.path.basename(root_abs.rstrip(os.sep)) or root_abs)
    entry_by_rel = {
        str(entry.get("relative_path") or "").replace("\\", "/"): entry
        for entry in index_payload.get("entries", []) or []
        if isinstance(entry, dict)
    }

    selected_entries: List[dict] = []
    if normalized_files:
        for abs_path in normalized_files:
            rel_path = os.path.relpath(abs_path, root_abs).replace("\\", "/")
            entry = entry_by_rel.get(rel_path)
            if entry:
                selected_entries.append(entry)
                continue
            artifact = store.ensure_file_artifact(abs_path, refresh_manifests=False)
            if artifact:
                selected_entries.append(
                    {
                        "file_id": artifact.get("file_id"),
                        "relative_path": artifact.get("relative_path"),
                        "language": artifact.get("language"),
                    }
                )
    else:
        selected_entries = list(index_payload.get("entries", []) or [])[:max_files]

    prepared_files = []
    for entry in selected_entries:
        relative_path = str(entry.get("relative_path") or "").replace("\\", "/")
        file_id = str(entry.get("file_id") or "")
        artifact = store.load_file_artifact_by_id(file_id) if file_id else None
        if not artifact and relative_path:
            artifact = store.load_file_artifact(os.path.join(root_abs, relative_path))
        if not artifact and relative_path:
            artifact = store.ensure_file_artifact(os.path.join(root_abs, relative_path), refresh_manifests=False)

        blocks = sorted(artifact.get("blocks", []) if artifact else [], key=_track3_block_priority)
        block_tokens = [
            f"{str(block.get('block_id') or '')}:{str(block.get('kind') or 'block')}"
            for block in blocks
            if block.get("block_id")
        ]
        prepared_files.append(
            {
                "file_id": file_id or str((artifact or {}).get("file_id") or ""),
                "relative_path": relative_path or str((artifact or {}).get("relative_path") or ""),
                "language": str(entry.get("language") or (artifact or {}).get("language") or "unknown"),
                "block_tokens": block_tokens,
                "block_total": len(block_tokens),
            }
        )

    def _render(file_limit: int, blocks_limit: int) -> str:
        lines = [
            "TRACK3_CONTEXT v1",
            f"project_id={project_id} root={root_name} files={len(prepared_files)}",
            "protocol=read structure first; reveal body only on demand by stable ids",
        ]

        shown = prepared_files[: max(1, file_limit)]
        for item in shown:
            block_tokens = item["block_tokens"][: max(1, blocks_limit)]
            hidden_count = max(0, int(item["block_total"]) - len(block_tokens))
            if hidden_count:
                block_tokens.append(f"+{hidden_count}")
            token_text = ",".join(block_tokens) if block_tokens else "(no_blocks)"
            lines.append(
                f"- {item['file_id']} path={_compact_track3_path(item['relative_path'])} "
                f"lang={item['language']} blocks={token_text}"
            )

        if len(prepared_files) > len(shown):
            lines.append(f"- +{len(prepared_files) - len(shown)} more files omitted")
        return "\n".join(lines)

    file_limit = min(max_files, len(prepared_files)) if prepared_files else 1
    blocks_limit = max_blocks_per_file
    snippet = _render(file_limit, blocks_limit)

    while len(snippet) > max_chars and (blocks_limit > 1 or file_limit > 1):
        if blocks_limit > 1:
            blocks_limit -= 1
        elif file_limit > 1:
            file_limit -= 1
        snippet = _render(file_limit, blocks_limit)

    if len(snippet) > max_chars:
        snippet = snippet[: max_chars - 1].rstrip() + "…"

    return snippet


# ────────────────────── Mini Code Builder ──────────────────────

class MiniCodeBuilder:
    """Builds mini code view from project files using SurgicalSkeletonizer."""

    def __init__(self):
        self.skeletonizer = SurgicalSkeletonizer()

    def analyze(self, file_paths: List[str], root_dir: str = "") -> dict:
        """
        Analyze files → mini code with block IDs and signatures.
        Returns: {files: [{path, language, blocks: [{id, type, name, signature, lines, blinded}]}]}
        """
        root_abs = os.path.abspath(root_dir) if root_dir else ""
        store = Track3ObjectStore(root_abs) if root_abs else None
        results = {"files": [], "root": root_dir, "root_dir": root_abs}

        if store:
            store.ensure_artifacts(file_paths)
            results["track3"] = {
                "artifact_root": store.artifact_root,
                "project_meta": store.load_project_meta(),
                "index": store.load_index(),
            }

        for file_path in file_paths:
            ext = os.path.splitext(file_path)[1].lower()

            if ext in SUPPORTED_EXTENSIONS or ext in HTML_EXTENSIONS:
                file_data = self._analyze_file(file_path, root_abs or root_dir, store)
                if file_data:
                    results["files"].append(file_data)

        if store:
            results["track3"] = {
                "artifact_root": store.artifact_root,
                "project_meta": store.load_project_meta(),
                "index": store.load_index(),
            }

        return results

    def _analyze_file(self, file_path: str, root_dir: str, store: Optional[Track3ObjectStore]) -> Optional[dict]:
        """Analyze a single file while preferring fixed ids from .track3 artifacts."""
        skeleton = self.skeletonizer.analyze_file(file_path)
        if not skeleton:
            return None

        rel_path = os.path.relpath(file_path, root_dir) if root_dir else file_path
        artifact = store.load_file_artifact(file_path) if store else None
        file_id = artifact.get("file_id") if artifact else skeleton.get("id", f"FILE_{rel_path}")
        raw_blocks = skeleton.get("blocks", [])
        block_identities = self._build_block_identities(file_id, raw_blocks, store, artifact)
        blocks = []

        for block, block_identity in zip(raw_blocks, block_identities):
            blocks.append({
                "id": block_identity["block_id"],
                "type": block.get("type", "code"),
                "name": block.get("name", ""),
                "signature": block.get("signature", block.get("name", "")),
                "lines": block.get("lines", [1, 1]),
                "blinded": True,  # body hidden by default
                "content": block.get("content", ""),  # stored but not sent when blinded
                "stable_key": block_identity["stable_key"],
                "identity_status": block_identity.get("identity_status", artifact.get("identity_status", "volatile") if artifact else "volatile"),
            })

        return {
            "path": rel_path,
            "abs_path": file_path,
            "language": skeleton.get("language", "unknown"),
            "total_lines": skeleton.get("total_lines", 0),
            "file_id": file_id,
            "artifact_path": artifact.get("artifact_path") if artifact else None,
            "identity_status": artifact.get("identity_status", "volatile") if artifact else "volatile",
            "reconcile_report": artifact.get("reconcile_report") if artifact else None,
            "blocks": blocks,
        }

    def _build_block_identities(
        self,
        file_id: str,
        raw_blocks: List[dict],
        store: Optional[Track3ObjectStore],
        artifact: Optional[dict],
    ) -> List[dict]:
        if artifact and len(artifact.get("blocks", [])) == len(raw_blocks):
            return [
                {
                    "block_id": block.get("block_id") or self._make_id(file_id, raw_blocks[idx]),
                    "stable_key": block.get("stable_key", ""),
                    "identity_status": block.get("identity_status", artifact.get("identity_status", "stable")),
                }
                for idx, block in enumerate(artifact.get("blocks", []))
            ]
        if store:
            computed, _ = store.reconcile_block_records(file_id, raw_blocks, existing_artifact=artifact)
        else:
            computed = []
            for block in raw_blocks:
                computed.append({
                    "block_id": block.get("id") or self._make_id(file_id, block),
                    "stable_key": "",
                    "identity_status": "volatile",
                })

        if not artifact:
            return computed

        artifact_by_key = {
            str(block.get("stable_key") or ""): block
            for block in artifact.get("blocks", [])
            if block.get("stable_key")
        }
        merged = []
        for block in computed:
            stored = artifact_by_key.get(block.get("stable_key", ""))
            if stored:
                merged.append({
                    **block,
                    "block_id": stored.get("block_id", block["block_id"]),
                    "stable_key": stored.get("stable_key", block.get("stable_key", "")),
                    "identity_status": stored.get("identity_status", block.get("identity_status", "stable")),
                })
            else:
                merged.append(block)
        return merged

    @staticmethod
    def _make_id(rel_path: str, block: dict) -> str:
        seed = f"{rel_path}:{block.get('name', '')}:{block.get('type', '')}"
        return f"BLK_{hashlib.md5(seed.encode()).hexdigest()[:8]}"


# ────────────────────── Reveal Manager ──────────────────────

class RevealManager:
    """Manages revealing/unblinding blocks for AI consumption."""

    DEFAULT_VISIBILITY = "signature"
    VISIBILITY_LEVELS = {"hidden", "signature", "summary", "revealed"}

    @staticmethod
    def build_prompt(analysis: dict, revealed_ids: List[str],
                     instruction: str, history: List[dict] = None) -> str:
        """
        Build the complete prompt for the AI.
        Revealed blocks show numbered content, blinded blocks show signature only.
        """
        visibility_map = {bid: "revealed" for bid in revealed_ids}
        return RevealManager.build_prompt_with_visibility(
            analysis=analysis,
            visibility_map=visibility_map,
            instruction=instruction,
            history=history,
        )

    @staticmethod
    def build_prompt_with_visibility(
        analysis: dict,
        visibility_map: Dict[str, str],
        instruction: str,
        history: List[dict] = None,
    ) -> str:
        """Build prompt using per-block visibility levels."""
        lines = []
        lines.append("SYSTEM: You are a Surgical Coding Agent.")
        lines.append("You receive code with per-block visibility levels: hidden, signature, summary, or revealed.")
        lines.append("If you need to see more of a block, respond with: [\"read\", [\"BLOCK_ID1\", \"BLOCK_ID2\"]]")
        lines.append("To make changes, respond with arrays: [[\"BLOCK_ID\", [[\"r\",\"from:to\",\"code\"],[\"d\",\"line\"],[\"i\",\"line\",\"code\"]]]]")
        lines.append("To create a new file, respond with: [\"create\", \"relative/path.ext\", \"full file content\"]")
        lines.append("If the task is complete with no more edits required, respond with: [\"finish\", \"short summary\"]")
        lines.append("Line numbers are RELATIVE to the block (starting from 1).")
        lines.append("Operations: r=replace, d=delete, i=insert_before")
        lines.append("Delete accepts: single \"5\", range \"3:7\", or mixed [3,\"5:8\",12]")
        lines.append("")

        # History
        if history:
            lines.append("=== PREVIOUS ROUNDS ===")
            for h in history:
                if h.get("type") == "read_request":
                    lines.append(f"[AI requested read: {h['ids']}]")
                elif h.get("type") == "mutations":
                    lines.append(f"[AI sent mutations, result: {h.get('result', 'pending')}]")
                elif h.get("type") == "error":
                    lines.append(f"[ERROR: {h['message']}]")
            lines.append("")

        # Instruction
        lines.append(f"INSTRUCTION: {instruction}")
        lines.append("")

        # Mini Code
        lines.append("=== PROJECT CODE ===")
        for file_data in analysis.get("files", []):
            lines.append(
                f"File: {file_data['path']} ({file_data['language']}) "
                f"[lines={file_data.get('total_lines', 0)} blocks={len(file_data.get('blocks', []))}]"
            )
            lines.append("-" * 40)

            for block in file_data.get("blocks", []):
                bid = block["id"]
                sig = block.get("signature") or block.get("name", "unknown")
                visibility = visibility_map.get(bid, RevealManager.DEFAULT_VISIBILITY)
                if visibility not in RevealManager.VISIBILITY_LEVELS:
                    visibility = RevealManager.DEFAULT_VISIBILITY

                if visibility == "revealed":
                    # Show full content with numbered lines
                    lines.append(f"[{bid}] {sig}")
                    content = block.get("content", "")
                    for idx, line in enumerate(content.splitlines(), 1):
                        lines.append(f"  {str(idx).rjust(4)} | {line}")
                elif visibility == "summary":
                    content = block.get("content", "")
                    body_lines = max(len(content.splitlines()), 0)
                    first_line = content.splitlines()[0].strip() if content.splitlines() else ""
                    snippet = first_line[:100] if first_line else "(empty block)"
                    lines.append(
                        f"[{bid}] {sig} :: summary "
                        f"[type={block.get('type', 'code')} lines={block.get('lines')} body_lines={body_lines}]"
                    )
                    lines.append(f"  summary: {snippet}")
                elif visibility == "hidden":
                    lines.append(
                        f"[{bid}] <hidden {block.get('type', 'code')}> "
                        f"[lines={block.get('lines')}]"
                    )
                else:
                    lines.append(
                        f"[{bid}] {sig} ... "
                        f"[signature-only lines={block.get('lines')}]"
                    )

            lines.append("")

        return "\n".join(lines)


# ────────────────────── Array Protocol Parser ──────────────────────

class ArrayProtocolParser:
    """Parses AI's array-based response into structured operations."""

    @staticmethod
    def parse(response_text: str) -> dict:
        """
        Parse AI response. Returns:
        {"type": "read", "ids": [...]} or
        {"type": "mutations", "blocks": [{"id": "...", "ops": [...]}]} or
        {"type": "create", "path": "...", "content": "..."} or
        {"type": "finish", "summary": "..."} or
        {"type": "text", "content": "..."}
        """
        # Try to extract JSON from response
        text = response_text.strip()

        # Try to find JSON array in response (may be wrapped in markdown)
        json_match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', text)
        if json_match:
            text = json_match.group(1)
        else:
            # Try raw array
            arr_match = re.search(r'(\[[\s\S]*\])', text)
            if arr_match:
                text = arr_match.group(1)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return {"type": "text", "content": response_text}

        if not isinstance(data, list) or len(data) == 0:
            return {"type": "text", "content": response_text}

        # Check if it's a read request: ["read", ["id1", "id2"]]
        if len(data) == 2 and data[0] == "read" and isinstance(data[1], list):
            return {"type": "read", "ids": data[1]}
        if len(data) == 3 and data[0] == "create":
            return {"type": "create", "path": str(data[1]), "content": str(data[2])}
        if len(data) == 2 and data[0] == "finish":
            return {"type": "finish", "summary": str(data[1])}

        # Check if it's mutations: [["BLK_xxx", [...]], ...]
        if isinstance(data[0], list):
            blocks = []
            for item in data:
                if not isinstance(item, list) or len(item) != 2:
                    continue
                block_id = item[0]
                ops_raw = item[1]
                if not isinstance(ops_raw, list):
                    continue
                ops = ArrayProtocolParser._parse_ops(ops_raw)
                blocks.append({"id": block_id, "ops": ops})
            if blocks:
                return {"type": "mutations", "blocks": blocks}

        return {"type": "text", "content": response_text}

    @staticmethod
    def _parse_ops(ops_raw: list) -> List[dict]:
        """Parse operation arrays into structured dicts."""
        ops = []
        for op in ops_raw:
            if not isinstance(op, list) or len(op) < 2:
                continue
            action = op[0]  # r, d, i
            if action == "r":
                # ["r", "3:7", "new code"] or ["r", "3", "new code"]
                lines = ArrayProtocolParser._parse_line_spec(op[1])
                code = op[2] if len(op) > 2 else ""
                ops.append({"action": "replace", "lines": lines, "code": code})
            elif action == "d":
                # ["d", "3"] or ["d", "3:7"] or ["d", [3, "5:8", 12]]
                lines = ArrayProtocolParser._parse_line_spec(op[1])
                ops.append({"action": "delete", "lines": lines})
            elif action == "i":
                # ["i", "5", "new code"]
                line = int(str(op[1]).split(":")[0])
                code = op[2] if len(op) > 2 else ""
                ops.append({"action": "insert", "line": line, "code": code})
        return ops

    @staticmethod
    def _parse_line_spec(spec) -> List[int]:
        """Parse line specification: int, str "3:7", or list [3, "5:8", 12]."""
        if isinstance(spec, list):
            lines = []
            for item in spec:
                lines.extend(ArrayProtocolParser._parse_line_spec(item))
            return sorted(set(lines))

        s = str(spec)
        if ":" in s:
            parts = s.split(":")
            start = int(parts[0])
            end = int(parts[1])
            return list(range(start, end + 1))
        return [int(s)]


# ────────────────────── Mutation Applier ──────────────────────

class MutationApplier:
    """Applies mutations to files with backup and syntax checking."""

    SYNTAX_COMMANDS = {
        '.py': ['python3', '-m', 'py_compile'],
        '.js': None,  # No easy syntax check without node
        '.cpp': None,
        '.c': None,
    }

    def __init__(self, backup_dir: str = None):
        self.backup_dir = backup_dir

    @staticmethod
    def _block_line_count(block: dict) -> int:
        lines = block.get("lines") or [0, 0]
        start = int(lines[0] or 0)
        end = int(lines[1] or start)
        if start > 0 and end >= start:
            return max(1, end - start + 1)
        content_lines = len(str(block.get("content", "") or "").splitlines())
        return max(1, content_lines)

    def _validate_block_ops(self, block_id: str, block: dict, ops: List[dict]) -> List[str]:
        total_lines = self._block_line_count(block)
        errors: List[str] = []

        for index, op in enumerate(ops, start=1):
            action = str(op.get("action") or "").strip().lower()
            if action in {"replace", "delete"}:
                line_numbers = [int(line) for line in op.get("lines", []) or []]
                if not line_numbers:
                    errors.append(f"Block {block_id} op #{index} has no target lines")
                    continue
                minimum = min(line_numbers)
                maximum = max(line_numbers)
                if minimum < 1 or maximum > total_lines:
                    errors.append(
                        f"Block {block_id} op #{index} escapes block bounds "
                        f"(requested {minimum}:{maximum}, allowed 1:{total_lines})"
                    )
            elif action == "insert":
                line_number = int(op.get("line") or 0)
                if line_number < 1 or line_number > total_lines + 1:
                    errors.append(
                        f"Block {block_id} insert op #{index} escapes block bounds "
                        f"(requested {line_number}, allowed 1:{total_lines + 1})"
                    )
            else:
                errors.append(f"Block {block_id} op #{index} has unsupported action {action or 'unknown'}")

        return errors

    def apply(self, analysis: dict, mutations: List[dict], dry_run: bool = True) -> dict:
        """
        Apply mutations. If dry_run=True, apply in memory only and return preview.
        Returns: {"success": bool, "files_modified": [...], "errors": [...], "preview": {...}}
        """
        # Build block index: block_id → (file_data, block)
        block_index = {}
        for file_data in analysis.get("files", []):
            for block in file_data.get("blocks", []):
                block_index[block["id"]] = (file_data, block)

        results = {"success": True, "files_modified": [], "errors": [], "preview": {}}
        file_changes = {}  # abs_path → [(start, end, new_content)]

        for mut in mutations:
            block_id = mut["id"]
            ops = mut.get("ops", [])

            if block_id not in block_index:
                results["errors"].append(f"Block {block_id} not found")
                results["success"] = False
                continue

            file_data, block = block_index[block_id]
            block_errors = self._validate_block_ops(block_id, block, ops)
            if block_errors:
                results["errors"].extend(block_errors)
                results["success"] = False
                continue

            abs_path = file_data.get("abs_path", "")
            block_start = block["lines"][0]  # 1-based absolute line

            if abs_path not in file_changes:
                file_changes[abs_path] = {"original_lines": None, "ops": [], "ext": ""}

            file_changes[abs_path]["ext"] = os.path.splitext(abs_path)[1].lower()

            for op in ops:
                if op["action"] == "replace":
                    abs_lines = [block_start + l - 1 for l in op["lines"]]
                    file_changes[abs_path]["ops"].append({
                        "action": "replace",
                        "start": min(abs_lines),
                        "end": max(abs_lines),
                        "code": op["code"],
                    })
                elif op["action"] == "delete":
                    abs_lines = [block_start + l - 1 for l in op["lines"]]
                    file_changes[abs_path]["ops"].append({
                        "action": "delete",
                        "start": min(abs_lines),
                        "end": max(abs_lines),
                    })
                elif op["action"] == "insert":
                    abs_line = block_start + op["line"] - 1
                    file_changes[abs_path]["ops"].append({
                        "action": "insert",
                        "line": abs_line,
                        "code": op["code"],
                    })

        # Apply changes per file
        for abs_path, changes in file_changes.items():
            try:
                with open(abs_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except OSError as e:
                results["errors"].append(f"Cannot read {abs_path}: {e}")
                results["success"] = False
                continue

            changes["original_lines"] = lines[:]

            # Sort ops in reverse order to avoid index shifting
            sorted_ops = sorted(changes["ops"], key=lambda o: o.get("start", o.get("line", 0)), reverse=True)

            for op in sorted_ops:
                if op["action"] == "replace":
                    start = op["start"] - 1  # 0-indexed
                    end = op["end"]  # exclusive
                    new_lines = [l + "\n" for l in op["code"].splitlines()]
                    lines[start:end] = new_lines

                elif op["action"] == "delete":
                    start = op["start"] - 1
                    end = op["end"]
                    del lines[start:end]

                elif op["action"] == "insert":
                    pos = op["line"] - 1
                    new_lines = [l + "\n" for l in op["code"].splitlines()]
                    for i, nl in enumerate(new_lines):
                        lines.insert(pos + i, nl)

            new_content = "".join(lines)
            results["preview"][abs_path] = new_content

            # Syntax check
            ext = changes["ext"]
            syntax_ok, syntax_error = self._check_syntax(new_content, ext, abs_path)
            if not syntax_ok:
                results["errors"].append(f"Syntax error in {abs_path}: {syntax_error}")
                results["success"] = False
                continue

            if not dry_run:
                # Backup
                if self.backup_dir:
                    self._backup(abs_path)
                # Write
                with open(abs_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                results["files_modified"].append(abs_path)

        return results

    def create_file(self, analysis: dict, relative_path: str, content: str, dry_run: bool = True) -> dict:
        """Create a new file under the current analysis root with validation."""
        results = {"success": True, "files_modified": [], "errors": [], "preview": {}}
        root_dir = analysis.get("root_dir") or analysis.get("root") or ""
        if not root_dir:
            return {"success": False, "files_modified": [], "errors": ["Analysis root_dir is missing"], "preview": {}}

        rel_path = str(relative_path or "").strip().lstrip("/").replace("\\", "/")
        if not rel_path:
            return {"success": False, "files_modified": [], "errors": ["create path is empty"], "preview": {}}

        abs_path = os.path.abspath(os.path.join(root_dir, rel_path))
        root_abs = os.path.abspath(root_dir)
        if not abs_path.startswith(root_abs + os.sep) and abs_path != root_abs:
            return {"success": False, "files_modified": [], "errors": [f"create path escapes project root: {rel_path}"], "preview": {}}
        if os.path.exists(abs_path):
            return {"success": False, "files_modified": [], "errors": [f"file already exists: {rel_path}"], "preview": {}}

        ext = os.path.splitext(abs_path)[1].lower()
        syntax_ok, syntax_error = self._check_syntax(content, ext, abs_path)
        if not syntax_ok:
            return {"success": False, "files_modified": [], "errors": [f"Syntax error in {rel_path}: {syntax_error}"], "preview": {abs_path: content}}

        results["preview"][abs_path] = content
        if dry_run:
            return results

        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        results["files_modified"].append(abs_path)
        return results

    def _check_syntax(self, content: str, ext: str, file_path: str) -> Tuple[bool, str]:
        """Check syntax of modified content."""
        if ext == '.py':
            try:
                compile(content, file_path, 'exec')
                return True, ""
            except SyntaxError as e:
                return False, f"Line {e.lineno}: {e.msg}"

        if ext in {'.js', '.mjs', '.cjs'}:
            return self._check_with_node(content, file_path)

        if ext == '.json':
            try:
                json.loads(content)
                return True, ""
            except json.JSONDecodeError as e:
                return False, f"Line {e.lineno} column {e.colno}: {e.msg}"

        # For JS/C++ we skip syntax check for now (needs external tools)
        return True, ""

    def _check_with_node(self, content: str, file_path: str) -> Tuple[bool, str]:
        """Validate JavaScript syntax using node --check."""
        try:
            suffix = os.path.splitext(file_path)[1] or ".js"
            if suffix == ".js" and re.search(r"^\s*(export|import)\b", content, re.MULTILINE):
                suffix = ".mjs"
            with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            proc = subprocess.run(
                ["node", "--check", tmp_path],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if proc.returncode == 0:
                return True, ""
            error_text = (proc.stderr or proc.stdout or "").strip()
            return False, error_text[:500] or "node --check failed"
        except (OSError, subprocess.SubprocessError) as e:
            return False, f"JS validation failed: {e}"
        finally:
            try:
                if 'tmp_path' in locals() and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass

    def _backup(self, abs_path: str):
        """Create backup of file."""
        if not os.path.exists(abs_path):
            return
        os.makedirs(self.backup_dir, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{os.path.basename(abs_path)}.{ts}.bak"
        shutil.copy2(abs_path, os.path.join(self.backup_dir, backup_name))


def _normalize_block_mutation_ops(ops: Any) -> Tuple[Optional[List[dict]], str]:
    if not isinstance(ops, list) or not ops:
        return None, "ops must be a non-empty list"

    if all(isinstance(op, dict) for op in ops):
        normalized: List[dict] = []
        action_map = {
            "r": "replace",
            "replace": "replace",
            "d": "delete",
            "delete": "delete",
            "i": "insert",
            "insert": "insert",
        }
        for op in ops:
            action = action_map.get(str(op.get("action") or op.get("op") or "").strip().lower())
            if not action:
                return None, f"unsupported op action: {op.get('action') or op.get('op')}"
            if action == "replace":
                if "lines" not in op:
                    return None, "replace op is missing lines"
                normalized.append(
                    {
                        "action": "replace",
                        "lines": ArrayProtocolParser._parse_line_spec(op.get("lines")),
                        "code": str(op.get("code") or ""),
                    }
                )
            elif action == "delete":
                if "lines" not in op:
                    return None, "delete op is missing lines"
                normalized.append(
                    {
                        "action": "delete",
                        "lines": ArrayProtocolParser._parse_line_spec(op.get("lines")),
                    }
                )
            else:
                line_value = op.get("line")
                if line_value is None:
                    return None, "insert op is missing line"
                normalized.append(
                    {
                        "action": "insert",
                        "line": int(str(line_value).split(":")[0]),
                        "code": str(op.get("code") or ""),
                    }
                )
        return normalized, ""

    try:
        return ArrayProtocolParser._parse_ops(ops), ""
    except Exception as exc:
        return None, f"invalid ops payload: {exc}"


def apply_block_mutation(
    root_dir: str,
    file_id: str,
    block_id: str,
    ops: Any,
    dry_run: bool = True,
    backup_dir: str = None,
    require_block_preservation: bool = True,
) -> dict:
    """Apply a block-scoped mutation using stable file_id/block_id artifacts."""
    root_abs = os.path.abspath(str(root_dir or "").strip() or ".")
    result = {
        "success": False,
        "files_modified": [],
        "errors": [],
        "preview": {},
        "root_dir": root_abs,
        "file_id": str(file_id or ""),
        "block_id": str(block_id or ""),
        "dry_run": bool(dry_run),
        "artifact_updated": False,
        "block_preserved": False,
        "relative_path": "",
        "source_path": "",
        "updated_artifact": None,
        "updated_block": None,
    }

    if not os.path.isdir(root_abs):
        result["errors"].append(f"root does not exist: {root_abs}")
        return result

    normalized_ops, error = _normalize_block_mutation_ops(ops)
    if error:
        result["errors"].append(error)
        return result

    store = Track3ObjectStore(root_abs)
    artifact = store.load_file_artifact_by_id(file_id)
    if not artifact:
        result["errors"].append(f"file_id not found: {file_id}")
        return result

    source_path = str(artifact.get("source_path") or "")
    if not source_path or not os.path.isfile(source_path):
        result["errors"].append(f"source file missing for file_id {file_id}")
        return result

    artifact = store.ensure_file_artifact(source_path) or artifact
    resolved_file_id = str(artifact.get("file_id") or file_id or "")
    artifact, block_record = store.load_block_record(resolved_file_id, block_id)
    if not artifact or not block_record:
        result["errors"].append(f"block_id not found: {block_id}")
        return result

    result["file_id"] = resolved_file_id
    result["relative_path"] = str(artifact.get("relative_path") or "")
    result["source_path"] = source_path
    previous_source_hash = str(artifact.get("source_hash") or "")

    builder = MiniCodeBuilder()
    analysis = builder.analyze([source_path], root_dir=root_abs)
    applier = MutationApplier(backup_dir=backup_dir)
    mutation_result = applier.apply(
        analysis,
        [{"id": block_id, "ops": normalized_ops}],
        dry_run=dry_run,
    )
    result.update(mutation_result)
    result["file_id"] = resolved_file_id
    result["block_id"] = str(block_id or "")
    result["relative_path"] = str(artifact.get("relative_path") or "")
    result["source_path"] = source_path
    result["dry_run"] = bool(dry_run)
    result["artifact_updated"] = False
    result["block_preserved"] = False
    result["updated_artifact"] = None
    result["updated_block"] = None

    if dry_run or not mutation_result.get("success"):
        return result

    updated_artifact = store.ensure_file_artifact(source_path)
    if not updated_artifact:
        result["success"] = False
        result["errors"].append("failed to refresh Track3 artifact after mutation")
        return result

    result["artifact_updated"] = str(updated_artifact.get("source_hash") or "") != previous_source_hash
    result["updated_artifact"] = {
        "file_id": str(updated_artifact.get("file_id") or ""),
        "relative_path": str(updated_artifact.get("relative_path") or ""),
        "artifact_path": str(updated_artifact.get("artifact_path") or ""),
        "identity_status": str(updated_artifact.get("identity_status") or "stable"),
        "source_hash": str(updated_artifact.get("source_hash") or ""),
    }

    updated_block = next(
        (
            block
            for block in updated_artifact.get("blocks", []) or []
            if str(block.get("block_id") or "") == str(block_id or "")
        ),
        None,
    )
    if updated_block:
        result["block_preserved"] = True
        result["updated_block"] = {
            "block_id": str(updated_block.get("block_id") or ""),
            "kind": str(updated_block.get("kind") or ""),
            "name": str(updated_block.get("name") or ""),
            "signature": str(updated_block.get("signature") or ""),
            "identity_status": str(updated_block.get("identity_status") or "stable"),
            "lines": list(updated_block.get("lines") or []),
        }
    elif require_block_preservation:
        result["success"] = False
        result["errors"].append(f"block_id {block_id} was not preserved after mutation")

    return result


# ────────────────────── Feedback Loop ──────────────────────

class FeedbackLoop:
    """Manages the stateless feedback loop for a single task."""

    def __init__(self, ai_client: AIProviderClient, backup_dir: str = None):
        self.ai = ai_client
        self.builder = MiniCodeBuilder()
        self.parser = ArrayProtocolParser()
        self.applier = MutationApplier(backup_dir=backup_dir)

    def start(self, file_paths: List[str], root_dir: str,
              instruction: str, provider_id: str, model_id: str,
              api_key: str = None) -> dict:
        """
        Start a new feedback loop session. Returns the full state.
        Each subsequent call to `step()` processes one round.
        """
        analysis = self.builder.analyze(file_paths, root_dir)
        return {
            "analysis": analysis,
            "instruction": instruction,
            "provider_id": provider_id,
            "model_id": model_id,
            "api_key": api_key,
            "revealed_ids": [],
            "visibility_map": {},
            "history": [],
            "round": 0,
            "status": "ready",
        }

    def step(self, state: dict) -> dict:
        """
        Execute one round of the feedback loop.
        Returns updated state with AI response.
        """
        state["round"] += 1

        # Build prompt
        prompt = RevealManager.build_prompt(
            analysis=state["analysis"],
            revealed_ids=state.get("revealed_ids", []),
            instruction=state["instruction"],
            history=state["history"],
        )
        visibility_map = state.get("visibility_map") or {}
        if visibility_map:
            prompt = RevealManager.build_prompt_with_visibility(
                analysis=state["analysis"],
                visibility_map=visibility_map,
                instruction=state["instruction"],
                history=state["history"],
            )

        # Call AI
        try:
            response_text = self.ai.call(
                provider_id=state["provider_id"],
                model_id=state["model_id"],
                prompt=prompt,
                api_key=state.get("api_key"),
                source="Track3-FeedbackLoop"
            )
        except Exception as e:
            state["status"] = "error"
            state["last_error"] = str(e)
            state["history"].append({"type": "error", "message": str(e)})
            return state

        # Parse response
        parsed = self.parser.parse(response_text)
        state["last_response_raw"] = response_text
        state["last_response_parsed"] = parsed

        if parsed["type"] == "read":
            # AI wants to see more blocks
            state["revealed_ids"].extend(parsed["ids"])
            state["revealed_ids"] = list(set(state["revealed_ids"]))
            for block_id in parsed["ids"]:
                state.setdefault("visibility_map", {})[block_id] = "revealed"
            state["history"].append({"type": "read_request", "ids": parsed["ids"]})
            state["status"] = "needs_more_context"

        elif parsed["type"] == "mutations":
            # AI wants to make changes — dry run first
            result = self.applier.apply(state["analysis"], parsed["blocks"], dry_run=True)
            state["pending_mutations"] = parsed["blocks"]
            state["dry_run_result"] = result
            state["validation_result"] = {
                "kind": "mutation_validation",
                "success": result["success"],
                "errors": result.get("errors", []),
            }
            if result["success"]:
                state["status"] = "pending_approval"
            else:
                state["status"] = "validation_failed"
                state["history"].append({
                    "type": "error",
                    "message": "; ".join(result["errors"]),
                })

        elif parsed["type"] == "create":
            result = self.applier.create_file(
                state["analysis"],
                parsed["path"],
                parsed["content"],
                dry_run=True,
            )
            state["pending_create"] = {
                "path": parsed["path"],
                "content": parsed["content"],
            }
            state["dry_run_result"] = result
            state["validation_result"] = {
                "kind": "create_validation",
                "success": result["success"],
                "errors": result.get("errors", []),
            }
            if result["success"]:
                state["status"] = "pending_approval"
                state["history"].append({"type": "create", "path": parsed["path"], "result": "pending"})
            else:
                state["status"] = "validation_failed"
                state["history"].append({"type": "error", "message": "; ".join(result["errors"])})

        elif parsed["type"] == "finish":
            state["status"] = "finished"
            state["finish_summary"] = parsed.get("summary", "")
            state["history"].append({"type": "finish", "summary": parsed.get("summary", "")})

        else:
            # AI sent text (info/explanation)
            state["status"] = "info"
            state["history"].append({"type": "info", "content": parsed.get("content", "")})

        return state

    def approve(self, state: dict) -> dict:
        """Apply pending mutations to disk."""
        if state.get("status") != "pending_approval":
            return state

        if state.get("pending_create"):
            pending = state["pending_create"]
            result = self.applier.create_file(
                state["analysis"],
                pending["path"],
                pending["content"],
                dry_run=False,
            )
            if result["success"]:
                analysis_root = state["analysis"].get("root_dir") or state["analysis"].get("root") or ""
                new_file_path = os.path.join(analysis_root, pending["path"])
                if os.path.exists(new_file_path):
                    state["analysis"] = self.builder.analyze(
                        [file_data.get("abs_path") for file_data in state["analysis"].get("files", []) if file_data.get("abs_path")] + [new_file_path],
                        analysis_root,
                    )
        else:
            result = self.applier.apply(
                state["analysis"],
                state["pending_mutations"],
                dry_run=False,
            )
            if result["success"]:
                analysis_root = state["analysis"].get("root_dir") or state["analysis"].get("root") or ""
                analysis_files = [
                    file_data.get("abs_path")
                    for file_data in state["analysis"].get("files", [])
                    if file_data.get("abs_path") and os.path.exists(file_data.get("abs_path"))
                ]
                if analysis_root and analysis_files:
                    unique_files = list(dict.fromkeys(analysis_files))
                    state["analysis"] = self.builder.analyze(unique_files, analysis_root)
        state["apply_result"] = result
        state["status"] = "applied" if result["success"] else "apply_failed"
        state["history"].append({
            "type": "create" if state.get("pending_create") else "mutations",
            "result": "applied" if result["success"] else "failed",
        })
        return state

    def reject(self, state: dict) -> dict:
        """Reject pending mutations and reset to ready."""
        if state.get("status") != "pending_approval":
            return state
        state["history"].append({"type": "mutations", "result": "rejected"})
        state["pending_mutations"] = None
        state["dry_run_result"] = None
        state["status"] = "ready"
        return state
