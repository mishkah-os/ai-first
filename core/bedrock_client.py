"""
Amazon Bedrock Client for QDML Platform
Handles AI code generation, modification, and analysis
"""
import json
import hashlib
import hmac
import base64
import asyncio
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def load_bedrock_credentials():
    """Load Bedrock API key from file"""
    key_path = Path("/srv/apps/ai5/ai-keys/bedrock.txt")
    if not key_path.exists():
        return None, None

    raw = key_path.read_text().strip()

    # Decode base64
    try:
        decoded = base64.b64decode(raw).decode('utf-8', errors='ignore')
    except:
        decoded = raw

    # Parse BedrockAPIKey format: BedrockAPIKey-{profile}:{secret}
    if 'BedrockAPIKey-' in decoded:
        parts = decoded.split('BedrockAPIKey-')[1]
        profile_and_secret = parts.split(':', 1)
        if len(profile_and_secret) == 2:
            profile = profile_and_secret[0]
            secret = profile_and_secret[1]
            return profile, secret

    return None, raw


class BedrockClient:
    """
    Amazon Bedrock Runtime client for Claude model invocation
    """

    def __init__(self, region="us-east-1"):
        self.region = region
        self.profile, self.api_key = load_bedrock_credentials()
        self.endpoint = f"https://bedrock-runtime.{region}.amazonaws.com"

    @property
    def available(self):
        return self.api_key is not None

    def status(self) -> dict:
        key_path = Path("/srv/apps/ai5/ai-keys/bedrock.txt")
        return {
            "name": "bedrock",
            "ok": self.available,
            "status": "configured" if self.available else "missing_credentials",
            "region": self.region,
            "endpoint": self.endpoint,
            "profile": self.profile or "",
            "key_path": str(key_path),
            "key_file_exists": key_path.exists(),
        }

    async def health(self, live: bool = False) -> dict:
        status = self.status()
        if not status["ok"] or not live:
            return status
        try:
            text = await self.invoke(
                "Reply with exactly: OK",
                system="Health check. Reply with exactly OK.",
                max_tokens=8,
                temperature=0,
            )
            status.update({
                "ok": bool(text.strip()),
                "status": "live_ok",
                "live": True,
                "sample": text.strip()[:80],
            })
        except Exception as exc:
            message = str(exc)
            status_name = "quota_exceeded" if "Too many tokens" in message or "429" in message else "live_error"
            status.update({
                "ok": False,
                "status": status_name,
                "live": True,
                "error": message[:500],
            })
        return status

    def _post_json(self, url: str, body: dict, headers: dict, timeout: int) -> dict:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Bedrock {exc.code}: {raw[:300]}") from exc

    async def invoke(self, prompt: str, system: str = "", model: str = "us.anthropic.claude-opus-4-6-v1",
                     max_tokens: int = 4096, temperature: float = 0.7) -> str:
        """
        Invoke Bedrock model with prompt
        Returns generated text
        """
        if not self.available:
            raise RuntimeError("Bedrock credentials not found")

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}]
        }

        if system:
            body["system"] = system

        raw_key = Path("/srv/apps/ai5/ai-keys/bedrock.txt").read_text().strip()

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {raw_key}",
        }

        url = f"https://bedrock-runtime.{self.region}.amazonaws.com/model/{model}/invoke"

        result = await asyncio.to_thread(self._post_json, url, body, headers, 90)
        content = result.get("content", [])
        if content:
            return content[0].get("text", "")
        return ""

    async def generate_component(self, description: str, kit_type: str = "screen",
                                  reference_code: str = "", framework: str = "mas-js") -> str:
        """Generate a new component from description"""

        system = f"""You are a code generator for QDML Platform using MAS.js framework.
Generate clean, production-ready JavaScript code following these patterns:
- Use function-based components
- Include proper event handling
- Follow RTL/Arabic support patterns
- Use CSS custom properties for theming
- Keep code modular and reusable

Framework: {framework}
Component type: {kit_type}

Return ONLY the code, no explanations or markdown."""

        prompt = f"Generate a {kit_type} component: {description}"
        if reference_code:
            prompt += f"\n\nReference code for style/patterns:\n{reference_code[:2000]}"

        return await self.invoke(prompt, system=system, temperature=0.7)

    async def modify_component(self, current_code: str, modification: str) -> str:
        """Modify existing component code"""

        system = """You are a code modifier for QDML Platform.
Apply the requested modification to the provided code.
Preserve structure, style, and all existing functionality unless explicitly asked to change it.
Return ONLY the modified code, no explanations."""

        prompt = f"""Current code:
```javascript
{current_code}
```

Modification requested: {modification}

Return the complete modified code:"""

        return await self.invoke(prompt, system=system, temperature=0.3)

    async def analyze_and_split(self, code: str) -> dict:
        """Analyze code and suggest bulk splitting"""

        system = """You are a code analyzer for QDML Platform.
Analyze the provided code and suggest how to split it into atomic bulks (50-100 lines each).
Return a JSON object with:
- "bulks": array of {name, start_line, end_line, exports, depends}
- "summary": brief description
Return ONLY valid JSON."""

        prompt = f"Analyze and suggest bulk splitting:\n```\n{code}\n```"
        result = await self.invoke(prompt, system=system, temperature=0.2)

        try:
            return json.loads(result)
        except:
            return {"bulks": [], "summary": result[:200]}


# Singleton
_client = None


def get_bedrock_client() -> BedrockClient:
    global _client
    if _client is None:
        _client = BedrockClient()
    return _client
