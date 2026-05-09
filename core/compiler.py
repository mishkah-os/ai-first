"""
AI-First Core Compiler
======================
Reads ALL data from PostgreSQL via CoreEngine and produces real files on disk.

Strategies:
  single-bundle    — One file per target language. Default. Deployable as-is.
  module-split     — One file per module (components inside).
  component-split  — One file per component.

Transform Pipeline:
  After compilation, code passes through transform functions.
  Default: identity (no change).
  Future: obfuscation, minification, string encryption.

Output:
  _compiled/
    ├── <target>/        — Compiled code files
    └── <artifacts>      — .env, Dockerfile, package.json, .gitignore, etc.
"""
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .engine import CoreEngine


# ================================================================
# TRANSFORM PIPELINE
# ================================================================

def identity_transform(code: str, target: str, meta: dict) -> str:
    """Default transform: no change."""
    return code


# Future transforms (not implemented yet, but the hook is here):
# def obfuscate_transform(code, target, meta) -> str: ...
# def minify_transform(code, target, meta) -> str: ...
# def encrypt_strings_transform(code, target, meta) -> str: ...


# ================================================================
# COMPILE HEADERS PER TARGET
# ================================================================

_COMMENT = {
    "cpp":    "//",
    "python": "#",
    "node":   "//",
    "mas-js": "//",
}

_EXT = {
    "cpp":    ".cpp",
    "python": ".py",
    "node":   ".js",
    "mas-js": ".js",
}


def _header(target: str, title: str) -> str:
    c = _COMMENT.get(target, "//")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"""{c} ══════════════════════════════════════════════════════
{c} AI-First Compiled Output
{c} {title}
{c} Generated: {now}
{c} WARNING: This file is auto-generated. Do not edit.
{c} The source of truth is the database.
{c} ══════════════════════════════════════════════════════
"""


def _section(target: str, title: str) -> str:
    c = _COMMENT.get(target, "//")
    return f"\n{c} {'─'*50}\n{c} {title}\n{c} {'─'*50}\n"


# ================================================================
# COMPILER CLASS
# ================================================================

class Compiler:
    """
    Reads from CoreEngine, writes compiled files to disk.
    """

    def __init__(self, engine: CoreEngine,
                 transforms: list[Callable] = None):
        self.engine = engine
        self.transforms = transforms or [identity_transform]

    def _apply_transforms(self, code: str, target: str, meta: dict = None) -> str:
        for fn in self.transforms:
            code = fn(code, target, meta or {})
        return code

    # ================================================================
    # MAIN COMPILE
    # ================================================================

    async def compile(self, output_dir: str,
                      strategy: str = "single-bundle") -> list[str]:
        """
        Compile the entire project from database to files.
        Returns list of generated file paths.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # Read all data from DB
        modules = await self.engine.read_all_modules()
        shared = await self.engine.read_shared_functions()
        gvars = await self.engine.read_global_vars()
        tokens = await self.engine.read_design_tokens()
        i18n = await self.engine.read_i18n()
        artifacts = await self.engine.read_artifacts()

        # Read all components per module
        module_data = []
        for mod in modules:
            comps = await self.engine.read_components(mod["id"])
            module_data.append({"module": mod, "components": comps})

        # Compile code
        if strategy == "single-bundle":
            generated = self._compile_single_bundle(out, module_data, shared, gvars, tokens, i18n)
        elif strategy == "module-split":
            generated = self._compile_module_split(out, module_data, shared, gvars, tokens, i18n)
        elif strategy == "component-split":
            generated = self._compile_component_split(out, module_data, shared, gvars, tokens, i18n)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        # Write artifacts (.env, Dockerfile, etc.)
        generated += self._write_artifacts(out, artifacts)

        return generated

    # ================================================================
    # STRATEGY: SINGLE-BUNDLE
    # ================================================================

    def _compile_single_bundle(self, out: Path, module_data: list,
                                shared: list, gvars: list,
                                tokens: list, i18n: dict) -> list[str]:
        """One file per target language. All modules/components bundled inside."""
        # Group components by target
        by_target: dict[str, list] = {}
        for md in module_data:
            for comp in md["components"]:
                by_target.setdefault(comp["target"], []).append({
                    "module": md["module"],
                    "component": comp
                })

        generated = []
        for target, entries in by_target.items():
            ext = _EXT.get(target, ".txt")
            filename = f"bundle-{target}{ext}"
            filepath = out / filename

            parts = []
            parts.append(_header(target, f"Strategy: single-bundle | Target: {target}"))

            # Global vars
            gv_for_target = [g for g in gvars]  # all global vars included
            if gv_for_target:
                parts.append(_section(target, "Global Variables"))
                parts.append(self._render_global_vars(target, gv_for_target))

            # Shared functions for this target's language
            target_lang = {"cpp": "cpp", "python": "python", "node": "javascript", "mas-js": "javascript"}
            sf = [s for s in shared if s["lang"] == target_lang.get(target, target)]
            if sf:
                parts.append(_section(target, "Shared Functions"))
                for fn in sf:
                    parts.append(f"\n{_COMMENT[target]} fn: {fn['name']}")
                    if fn.get("description"):
                        parts.append(f"{_COMMENT[target]}   {fn['description']}")
                    parts.append(fn["content"])

            # Design tokens (MAS JS only → CSS vars)
            if target == "mas-js" and tokens:
                parts.append(_section(target, "Design Tokens"))
                parts.append(self._render_design_tokens(tokens))

            # i18n (MAS JS only)
            if target == "mas-js" and i18n:
                parts.append(_section(target, "i18n Translations"))
                parts.append(self._render_i18n(i18n))

            # Components grouped by module
            for entry in entries:
                mod = entry["module"]
                comp = entry["component"]
                parts.append(_section(target, f"Module: {mod['name']} | Component: {comp['name']}"))
                parts.append(self._render_component(target, comp))

            code = "\n".join(parts)
            code = self._apply_transforms(code, target, {"strategy": "single-bundle"})
            filepath.write_text(code, encoding="utf-8")
            generated.append(str(filepath))

        return generated

    # ================================================================
    # STRATEGY: MODULE-SPLIT
    # ================================================================

    def _compile_module_split(self, out: Path, module_data: list,
                               shared: list, gvars: list,
                               tokens: list, i18n: dict) -> list[str]:
        """One file per module. Components of that module inside."""
        generated = []

        for md in module_data:
            mod = md["module"]
            # Group this module's components by target
            by_target: dict[str, list] = {}
            for comp in md["components"]:
                by_target.setdefault(comp["target"], []).append(comp)

            for target, comps in by_target.items():
                ext = _EXT.get(target, ".txt")
                filepath = out / f"{mod['slug']}{ext}"

                parts = [_header(target, f"Module: {mod['name']} | Strategy: module-split")]

                for comp in comps:
                    parts.append(_section(target, f"Component: {comp['name']}"))
                    parts.append(self._render_component(target, comp))

                code = "\n".join(parts)
                code = self._apply_transforms(code, target, {"strategy": "module-split", "module": mod["slug"]})
                filepath.write_text(code, encoding="utf-8")
                generated.append(str(filepath))

        return generated

    # ================================================================
    # STRATEGY: COMPONENT-SPLIT
    # ================================================================

    def _compile_component_split(self, out: Path, module_data: list,
                                  shared: list, gvars: list,
                                  tokens: list, i18n: dict) -> list[str]:
        """One file per component. Organized in module directories."""
        generated = []

        for md in module_data:
            mod = md["module"]
            mod_dir = out / mod["slug"]
            mod_dir.mkdir(exist_ok=True)

            for comp in md["components"]:
                target = comp["target"]
                ext = _EXT.get(target, ".txt")
                filepath = mod_dir / f"{comp['slug']}{ext}"

                parts = [_header(target, f"Module: {mod['name']} | Component: {comp['name']}")]
                parts.append(self._render_component(target, comp))

                code = "\n".join(parts)
                code = self._apply_transforms(code, target,
                    {"strategy": "component-split", "module": mod["slug"], "component": comp["slug"]})
                filepath.write_text(code, encoding="utf-8")
                generated.append(str(filepath))

        return generated

    # ================================================================
    # RENDER: Component → Code String
    # ================================================================

    def _render_component(self, target: str, comp: dict) -> str:
        """Render a single component's pillars into target-language code."""
        p = comp.get("pillars", {})
        schema  = p.get("schema", "")
        logic   = p.get("logic", "")
        template = p.get("template", "")
        style   = p.get("style", "")

        if target == "mas-js":
            return self._render_mas_js(comp["slug"], schema, logic, template, style)
        elif target == "cpp":
            return self._render_raw(schema, logic)
        elif target == "python":
            return self._render_raw(schema, logic)
        elif target == "node":
            return self._render_raw(schema, logic)
        else:
            return self._render_raw(schema, logic)

    def _render_mas_js(self, slug: str, schema: str, logic: str,
                       template: str, style: str) -> str:
        """Render a MAS JS module with all 4 pillars."""
        parts = [f"MAS.module('{slug}', {{"]
        if schema:
            parts.append(f"  db: {schema},\n")
        if logic:
            parts.append(f"  orders: {logic},\n")
        if template:
            parts.append(f"  body: {template},\n")
        if style:
            parts.append(f"  style: `{style}`")
        parts.append("});")
        return "\n".join(parts)

    def _render_raw(self, schema: str, logic: str) -> str:
        """Render raw code (C++, Python, Node) — schema first, then logic."""
        parts = []
        if schema:
            parts.append(schema)
        if schema and logic:
            parts.append("")
        if logic:
            parts.append(logic)
        return "\n".join(parts)

    # ================================================================
    # RENDER: Globals, Tokens, i18n
    # ================================================================

    def _render_global_vars(self, target: str, gvars: list) -> str:
        if target == "python":
            return "\n".join(f"{g['key']} = {json.dumps(g['value'])}" for g in gvars)
        elif target in ("node", "mas-js"):
            return "\n".join(f"const {g['key']} = {json.dumps(g['value'])};" for g in gvars)
        elif target == "cpp":
            return "\n".join(
                f'const char* {g["key"]} = {json.dumps(g["value"])};' for g in gvars)
        return ""

    def _render_design_tokens(self, tokens: list) -> str:
        lines = [":root {"]
        for t in tokens:
            lines.append(f"  --{t['key']}: {t['value']};")
        lines.append("}")
        return "const _DESIGN_TOKENS_CSS = `\n" + "\n".join(lines) + "\n`;"

    def _render_i18n(self, i18n: dict) -> str:
        return f"const I18N = {json.dumps(i18n, ensure_ascii=False, indent=2)};"

    # ================================================================
    # WRITE ARTIFACTS
    # ================================================================

    def _write_artifacts(self, out: Path, artifacts: list) -> list[str]:
        """Write all project artifacts (.env, Dockerfile, etc.) to disk."""
        generated = []
        for a in artifacts:
            rel = a["path"].strip("./").strip("/").strip("\\")
            target_dir = out / rel if rel else out
            target_dir.mkdir(parents=True, exist_ok=True)
            filepath = target_dir / a["filename"]
            filepath.write_text(a["content"], encoding="utf-8")
            generated.append(str(filepath))
        return generated
