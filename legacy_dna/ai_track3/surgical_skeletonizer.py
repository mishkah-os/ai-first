"""
SurgicalSkeletonizer - Tree-sitter-based code skeleton extractor for Surgical Agent V3.
Provides Tree-sitter parsing for Python, JavaScript, HTML, and JSON while keeping the
legacy AST/regex strategy available behind a feature flag for compatibility.
"""

import ast
import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from tree_sitter import Language, Parser

try:
    import tree_sitter_html
except Exception:  # pragma: no cover - optional dependency
    tree_sitter_html = None

try:
    import tree_sitter_javascript
except Exception:  # pragma: no cover - optional dependency
    tree_sitter_javascript = None

try:
    import tree_sitter_json
except Exception:  # pragma: no cover - optional dependency
    tree_sitter_json = None

try:
    import tree_sitter_python
except Exception:  # pragma: no cover - optional dependency
    tree_sitter_python = None

try:
    import tree_sitter_cpp
except Exception:  # pragma: no cover - optional dependency
    tree_sitter_cpp = None

try:
    import tree_sitter_php
except Exception:  # pragma: no cover - optional dependency
    tree_sitter_php = None

try:
    import tree_sitter_c_sharp
except Exception:  # pragma: no cover - optional dependency
    tree_sitter_c_sharp = None

try:
    import tree_sitter_sql
except Exception:  # pragma: no cover - optional dependency
    tree_sitter_sql = None

try:
    from tree_sitter_languages import get_language  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    get_language = None

# Toggle to opt into the older AST/regex parser without removing it
USE_LEGACY_PARSER = False


class _LegacyParserStrategy:
    """Legacy AST/regex parser kept for reference and fallback."""

    def __init__(self, make_id):
        self._make_id = make_id

    def parse_python(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = []
        lines = content.splitlines()

        try:
            tree = ast.parse(content)

            imports = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)) and hasattr(node, "lineno"):
                    imports.append(node.lineno)

            imports_idx = 0
            if imports:
                import_content = "\n".join(lines[imports[0] - 1 : imports[-1]])
                blocks.append(
                    {
                        "id": self._make_id("BLK", f"import:{file_path}"),
                        "type": "import",
                        "lines": [imports[0], imports[-1]],
                        "content": import_content,
                        "foldable": False,
                        "selected": False,
                    }
                )

            # Occurrence counters for stable IDs
            counters = {"class": 0, "func": 0}

            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    idx = counters["class"]
                    counters["class"] += 1
                    blocks.append(self._parse_python_class(node, lines, file_path, idx))
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    idx = counters["func"]
                    counters["func"] += 1
                    blocks.append(self._parse_python_function(node, lines, file_path, idx))

        except SyntaxError as exc:
            blocks.append(
                {
                    "id": self._make_id("BLK", f"syntax_error:{file_path}:{getattr(exc, 'lineno', 1)}"),
                    "type": "error",
                    "lines": [getattr(exc, "lineno", 1), getattr(exc, "lineno", 1)],
                    "content": f"Syntax Error: {exc}",
                    "foldable": False,
                    "selected": False,
                }
            )

        return blocks

    def parse_json(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        try:
            data = json.loads(content)
        except Exception as exc:  # noqa: BLE001
            return [
                {
                    "id": self._make_id("BLK", f"json_error:{file_path}"),
                    "type": "error",
                    "lines": [1, 1],
                    "content": f"Invalid JSON: {exc}",
                    "foldable": False,
                    "selected": False,
                }
            ]

        mini_view = self._create_mini_json(data, top_n=1, include_values=False)
        mini_content = json.dumps(mini_view, ensure_ascii=False, indent=2)

        return [
            {
                "id": self._make_id("BLK", f"json:{file_path}"),
                "type": "json_structure",
                "name": os.path.basename(file_path),
                "lines": [1, len(content.splitlines())],
                "content": mini_content,
                "raw_json": data,
                "foldable": True,
                "selected": False,
                "default_top": 1,
                "include_values": False,
            }
        ]

    def parse_html(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        return [
            {
                "id": self._make_id("BLK", f"html:{file_path}"),
                "type": "html_section",
                "name": os.path.basename(file_path),
                "lines": [1, len(content.splitlines())],
                "content": content,
                "foldable": True,
                "selected": False,
            }
        ]

    def parse_javascript(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Lightweight JS/TS parser using regex to extract imports, functions, and classes."""
        lines = content.splitlines()
        blocks: List[Dict[str, Any]] = []

        # Imports (group contiguous import lines)
        import_lines = [idx + 1 for idx, line in enumerate(lines) if line.strip().startswith("import ")]
        if import_lines:
            start = import_lines[0]
            end = import_lines[-1]
            blocks.append(
                {
                    "id": self._make_id("BLK", f"import_js:{file_path}:{start}:{end}"),
                    "type": "import",
                    "lines": [start, end],
                    "content": "\n".join(lines[start - 1 : end]),
                    "foldable": False,
                    "selected": False,
                }
            )

        func_pattern = re.compile(r"^\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(")
        class_pattern = re.compile(r"^\s*class\s+([A-Za-z_$][\w$]*)")

        counters = {"func": 0, "class": 0}
        for idx, line in enumerate(lines, start=1):
            func_match = func_pattern.match(line)
            class_match = class_pattern.match(line)
            if func_match:
                name = func_match.group(1)
                occ = counters["func"]
                counters["func"] += 1
                blocks.append(
                    {
                        "id": self._make_id("BLK", f"func:{name}:{file_path}:{occ}"),
                        "type": "function_def",
                        "name": name,
                        "signature": line.strip(),
                        "lines": [idx, idx],
                        "content": line,
                        "body_content": line,
                        "foldable": True,
                        "selected": False,
                    }
                )
            elif class_match:
                name = class_match.group(1)
                occ = counters["class"]
                counters["class"] += 1
                blocks.append(
                    {
                        "id": self._make_id("BLK", f"class:{name}:{file_path}:{occ}"),
                        "type": "class_def",
                        "name": name,
                        "signature": line.strip(),
                        "lines": [idx, idx],
                        "content": line,
                        "body_content": line,
                        "foldable": True,
                        "selected": False,
                    }
                )

        if blocks:
            return blocks

        return [
            {
                "id": self._make_id("BLK", f"raw_js:{file_path}"),
                "type": "raw_text",
                "name": os.path.basename(file_path),
                "signature": os.path.basename(file_path),
                "lines": [1, len(lines) or 1],
                "content": content,
                "body_content": content,
                "foldable": True,
                "selected": False,
            }
        ]

    def _parse_python_class(self, node: ast.ClassDef, lines: List[str], file_path: str, occ: int) -> Dict[str, Any]:
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)
        signature = f"class {node.name}"
        return {
            "id": self._make_id("BLK", f"class:{node.name}:{file_path}:{occ}"),
            "type": "class_def",
            "name": node.name,
            "signature": signature,
            "lines": [start_line, end_line],
            "content": "\n".join(lines[start_line - 1 : end_line]),
            "body_content": "\n".join(lines[start_line - 1 : end_line]),
            "foldable": True,
            "selected": False,
        }

    def _parse_python_function(self, node: ast.AST, lines: List[str], file_path: str, occ: int) -> Dict[str, Any]:
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)
        name = getattr(node, "name", "function")
        signature = self._build_function_signature(node)
        return {
            "id": self._make_id("BLK", f"func:{name}:{file_path}:{occ}"),
            "type": "function_def",
            "name": name,
            "signature": signature,
            "lines": [start_line, end_line],
            "content": "\n".join(lines[start_line - 1 : end_line]),
            "body_content": "\n".join(lines[start_line - 1 : end_line]),
            "foldable": True,
            "selected": False,
        }

    def _build_function_signature(self, node: ast.AST) -> str:
        name = getattr(node, "name", "function")
        params = []
        for arg in getattr(node.args, "args", []):
            params.append(arg.arg)
        return f"def {name}({', '.join(params)})"

    def _create_mini_json(self, obj: Any, top_n: int = 1, include_values: bool = False) -> Any:
        if isinstance(obj, list):
            if not obj:
                return []
            limited = obj[: max(1, top_n)]
            return [self._create_mini_json(item, top_n=top_n, include_values=include_values) for item in limited]
        if isinstance(obj, dict):
            mini_obj: Dict[str, Any] = {}
            for key, value in obj.items():
                if include_values:
                    mini_obj[key] = self._create_mini_json(value, top_n=top_n, include_values=include_values)
                else:
                    mini_obj[key] = self._mask_value(value, top_n, include_values)
            return mini_obj
        return self._mask_value(obj, top_n, include_values)

    def _mask_value(self, value: Any, top_n: int, include_values: bool):
        if isinstance(value, (dict, list)):
            return self._create_mini_json(value, top_n=top_n, include_values=include_values)
        return value if include_values else "***"


def _safe_slice(content: str, start_byte: int, end_byte: int) -> str:
    return content.encode("utf-8")[start_byte:end_byte].decode("utf-8", errors="ignore")


class SurgicalSkeletonizer:
    """Extracts structured code skeletons from source files using Tree-sitter."""

    def __init__(self, use_legacy_parser: bool = False):
        self.use_legacy_parser = use_legacy_parser or USE_LEGACY_PARSER
        self.supported_extensions = {
            ".py": "python",
            ".pyw": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "javascript",
            ".tsx": "javascript",
            ".html": "html",
            ".htm": "html",
            ".json": "json",
            ".c": "cpp",
            ".h": "cpp",
            ".cc": "cpp",
            ".cpp": "cpp",
            ".cxx": "cpp",
            ".hpp": "cpp",
            ".php": "php",
            ".phtml": "php",
            ".php5": "php",
            ".sql": "sql",
            ".cs": "csharp",
        }
        self._legacy_strategy = _LegacyParserStrategy(self._make_id)
        self.languages: Dict[str, Language] = {}
        self.parsers: Dict[str, Parser] = {}
        self.queries: Dict[str, Any] = {}
        self._important_html_tags = {
            "html",
            "head",
            "body",
            "header",
            "footer",
            "main",
            "nav",
            "section",
            "article",
            "aside",
            "div",
            "form",
            "fieldset",
            "legend",
            "label",
            "input",
            "textarea",
            "select",
            "option",
            "button",
            "table",
            "thead",
            "tbody",
            "tr",
            "td",
            "th",
            "ul",
            "ol",
            "li",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "p",
            "span",
            "code",
            "pre",
            "script",
            "style",
        }
        self.max_html_depth = 8  # allow deeper HTML outlines while avoiding extreme noise
        self._init_tree_sitter()

    def _init_tree_sitter(self) -> None:
        if self.use_legacy_parser:
            return

        self.languages = {}
        self.parsers = {}

        try:
            def _coerce_language(candidate) -> Optional[Language]:
                """Normalize different binding return types (Language or PyCapsule) into Language."""
                if isinstance(candidate, Language):
                    return candidate
                return None

            def _try_load_language(lang_key: str, loader=None):
                if get_language:
                    try:
                        loaded = get_language(lang_key)
                        language = _coerce_language(loaded)
                        if language:
                            return language
                        print(f"Loaded {lang_key} via tree_sitter_languages is not coercible to tree_sitter.Language; skipping.")
                    except Exception as exc:  # noqa: BLE001
                        print(f"Failed to load {lang_key} via tree_sitter_languages: {exc}")
                if loader:
                    try:
                        loaded = loader()
                        language = _coerce_language(loaded)
                        if language:
                            return language
                        print(f"Loaded {lang_key} is not coercible to tree_sitter.Language; skipping.")
                    except Exception as exc:  # noqa: BLE001
                        print(f"Failed to load {lang_key} binding via loader: {exc}")
                return None

            def _assign_language(parser: Parser, language: Language) -> None:
                """Support both legacy set_language and new property setter."""
                if hasattr(parser, "set_language"):
                    parser.set_language(language)  # type: ignore[attr-defined]
                elif hasattr(parser, "language"):
                    parser.language = language  # type: ignore[assignment]
                else:  # pragma: no cover - defensive for unexpected API changes
                    raise AttributeError("Parser API does not expose language setter")

            def _register_language(lang_key: str, extensions: List[str], loader=None):
                language = _try_load_language(lang_key, loader)
                if not language:
                    return
                if not isinstance(language, Language):
                    print(f"Loaded {lang_key} is not a tree_sitter.Language instance; skipping.")
                    return
                self.languages[lang_key] = language
                for ext in extensions:
                    parser = Parser()
                    _assign_language(parser, language)
                    self.parsers[ext] = parser

            # Preferred: direct bindings, fallback to tree_sitter_languages
            if tree_sitter_python:
                _register_language("python", [".py", ".pyw"], lambda: tree_sitter_python.language())  # type: ignore[arg-type]
            else:
                _register_language("python", [".py", ".pyw"])

            if tree_sitter_javascript:
                _register_language(
                    "javascript",
                    [".js", ".jsx", ".ts", ".tsx"],
                    lambda: tree_sitter_javascript.language(),  # type: ignore[arg-type]
                )
            else:
                _register_language("javascript", [".js", ".jsx", ".ts", ".tsx"])

            if tree_sitter_html:
                _register_language("html", [".html", ".htm"], lambda: tree_sitter_html.language())  # type: ignore[arg-type]
            else:
                _register_language("html", [".html", ".htm"])

            if tree_sitter_json:
                _register_language("json", [".json"], lambda: tree_sitter_json.language())  # type: ignore[arg-type]
            else:
                _register_language("json", [".json"])

            if tree_sitter_cpp:
                _register_language("cpp", [".c", ".h", ".cc", ".cpp", ".cxx", ".hpp"], lambda: tree_sitter_cpp.language())  # type: ignore[arg-type]
            else:
                _register_language("cpp", [".c", ".h", ".cc", ".cpp", ".cxx", ".hpp"])
            if tree_sitter_php:
                _register_language("php", [".php", ".phtml", ".php5"], lambda: tree_sitter_php.language())  # type: ignore[arg-type]
            else:
                _register_language("php", [".php", ".phtml", ".php5"])
            if tree_sitter_sql:
                _register_language("sql", [".sql"], lambda: tree_sitter_sql.language())  # type: ignore[arg-type]
            else:
                _register_language("sql", [".sql"])
            if tree_sitter_c_sharp:
                _register_language("csharp", [".cs"], lambda: tree_sitter_c_sharp.language())  # type: ignore[arg-type]
            else:
                _register_language("csharp", [".cs"])

            if self.languages:
                self._prepare_queries()
                print(f"Tree-sitter initialized with languages: {', '.join(sorted(self.languages.keys()))}")
                return
        except Exception as exc:  # noqa: BLE001
            print(f"Tree-sitter initialization failed early ({exc}); attempting compilation fallback.")

        # Fallback to compilation for the core grammars if nothing loaded
        try:
            build_dir = os.environ.get(
                "TREE_SITTER_LIB_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "build"))
            )
            lib_ext = ".dll" if os.name == "nt" else ".so"
            lib_path = os.path.join(build_dir, f"tree_sitter_langs{lib_ext}")

            if not os.path.exists(lib_path):
                os.makedirs(os.path.dirname(lib_path), exist_ok=True)
                if hasattr(Language, "build_library"):
                    Language.build_library(  # type: ignore[attr-defined]
                        lib_path,
                        self._grammar_paths(),
                    )
                else:
                    raise RuntimeError("tree_sitter.Language.build_library is unavailable in this binding")

            self.languages = {
                "python": Language(lib_path, "python"),  # type: ignore[arg-type]
                "javascript": Language(lib_path, "javascript"),  # type: ignore[arg-type]
                "html": Language(lib_path, "html"),  # type: ignore[arg-type]
                "json": Language(lib_path, "json"),  # type: ignore[arg-type]
            }
            if tree_sitter_cpp:
                self.languages["cpp"] = Language(lib_path, "cpp")  # type: ignore[arg-type]
            if tree_sitter_php:
                self.languages["php"] = Language(lib_path, "php")  # type: ignore[arg-type]
            if tree_sitter_sql:
                self.languages["sql"] = Language(lib_path, "sql")  # type: ignore[arg-type]
            if tree_sitter_c_sharp:
                self.languages["csharp"] = Language(lib_path, "c_sharp")  # type: ignore[arg-type]

            for ext, lang_key in self.supported_extensions.items():
                language = self.languages.get(lang_key)
                if language:
                    parser = Parser()
                    _assign_language(parser, language)
                    self.parsers[ext] = parser

            self._prepare_queries()
        except Exception as exc:  # noqa: BLE001
            print(f"Tree-sitter initialization failed ({exc}); falling back to legacy parser.")
            self.use_legacy_parser = True

    def _grammar_paths(self) -> List[str]:
        grammar_modules = [module for module in [
            tree_sitter_python,
            tree_sitter_javascript,
            tree_sitter_html,
            tree_sitter_json,
            tree_sitter_cpp,
            tree_sitter_php,
            tree_sitter_sql,
            tree_sitter_c_sharp,
        ] if module]
        paths: List[str] = []
        for module in grammar_modules:
            # Try multiple common locations for grammar source
            possible_paths = [
                os.path.join(os.path.dirname(module.__file__), "src"), # Standard package structure
                os.path.join(os.path.dirname(module.__file__)),        # Flat structure
            ]
            
            # Check for package-specific paths (some packages include the grammar in root or other subdirs)
            try:
                # Some newer bindings might expose the path
                if hasattr(module, 'path'):
                     paths.append(module.path)
                     continue
            except:
                pass

            found = False
            for candidate in possible_paths:
                if os.path.exists(candidate):
                    paths.append(candidate)
                    found = True
                    break
            
            if not found:
                # Warning instead of dying, so valid grammars can still work
                print(f"Warning: Could not find grammar source for {module.__name__}")

        if not paths:
            raise RuntimeError("No Tree-sitter grammar sources found")
        return paths

    def _prepare_queries(self) -> None:
        self.queries["python"] = self._build_query(
            self.languages["python"],
            """
            (import_statement) @import
            (import_from_statement) @import
            (function_definition name: (identifier) @func.name) @func
            (class_definition name: (identifier) @class.name) @class
            """,
        )
        self.queries["javascript"] = self._build_query(
            self.languages["javascript"],
            """
            (import_statement) @import
            (function_declaration name: (identifier) @func.name) @func
            (generator_function_declaration name: (identifier) @func.name) @func
            (function name: (identifier)? @func.name) @func  ; function expression
            (method_definition name: (property_identifier) @method.name) @method
            (class_declaration name: (identifier) @class.name) @class
            (lexical_declaration
                (variable_declarator
                    name: (identifier) @func.name
                    value: [(arrow_function) (function)]
                )
            ) @func
            (variable_declaration
                (variable_declarator
                    name: (identifier) @func.name
                    value: (arrow_function)
                )
            ) @func
            (lexical_declaration (variable_declarator name: (identifier) @var.name)) @var
            (variable_declaration (variable_declarator name: (identifier) @var.name)) @var
            (for_statement) @control
            (for_in_statement) @control
            (while_statement) @control
            (do_statement) @control
            (if_statement) @control
            (switch_statement) @control
            (try_statement) @control
            """,
        )
        self.queries["html"] = self._build_query(
            self.languages["html"],
            """
            (element (start_tag (tag_name) @tag.name)) @element
            (script_element) @script
            (style_element) @style
            """,
        )
        self.queries["json"] = self._build_query(self.languages["json"], "(document) @json")
        if "cpp" in self.languages:
            self.queries["cpp"] = self._build_query(
                self.languages["cpp"],
                """
                (function_definition
                  declarator: (function_declarator
                    declarator: [(identifier) (field_identifier)] @func.name
                  )
                ) @func
                (function_declarator declarator: (identifier) @func.name) @func
                (class_specifier name: (type_identifier) @class.name) @class
                (struct_specifier name: (type_identifier) @class.name) @class
                (namespace_definition name: (namespace_identifier) @class.name) @class
                """,
            )
        if "php" in self.languages:
            self.queries["php"] = self._build_query(
                self.languages["php"],
                """
                (function_definition name: (name) @func.name) @func
                (method_declaration name: (name) @method.name) @method
                (class_declaration name: (name) @class.name) @class
                """,
            )
        if "csharp" in self.languages:
            self.queries["csharp"] = self._build_query(
                self.languages["csharp"],
                """
                (method_declaration name: (identifier) @method.name) @method
                (local_function_statement name: (identifier) @func.name) @func
                (function_definition name: (identifier) @func.name) @func
                (class_declaration name: (identifier) @class.name) @class
                (struct_declaration name: (identifier) @class.name) @class
                (namespace_declaration name: (identifier) @class.name) @class
                """,
            )
        if "sql" in self.languages:
            self.queries["sql"] = self._build_query(
                self.languages["sql"],
                """
                (create_table_statement) @class
                (create_view_statement) @class
                (create_function_statement) @func
                (select_statement) @func
                """,
            )

    def _build_query(self, language: Language, query_str: str):
        try:
            return language.query(query_str)
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to build query for language {getattr(language, 'name', 'unknown')}: {exc}")
            return None

    def _make_id(self, prefix: str, seed: str) -> str:
        digest = hashlib.md5(seed.encode("utf-8")).hexdigest()[:8]
        return f"{prefix}_{digest}"

    def analyze_file(
        self,
        file_path: str,
        include_outline: bool = False,
        outline_max_depth: int = 6,
        outline_max_nodes: int = 400,
        outline_include_text: bool = False,
        outline_include_unnamed: bool = False,
        root_dir: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.supported_extensions:
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
        except OSError as exc:
            print(f"Error reading {file_path}: {exc}")
            return None

        blocks = self._parse_file(content, file_path, ext, root_dir=root_dir)
        blocks = self._inject_file_body_block(blocks, content, file_path)
        blocks, fidelity_block = self._append_integrity_block(blocks, content, file_path)
        if fidelity_block:
            blocks.insert(1, fidelity_block)

        if include_outline:
            try:
                outline = self.raw_outline(
                    file_path,
                    include_text=outline_include_text,
                    max_depth=outline_max_depth,
                    max_nodes=outline_max_nodes,
                    include_unnamed=outline_include_unnamed,
                )
                if outline.get("truncated"):
                    warning = self._outline_truncation_block(file_path)
                    blocks.insert(1, warning)
            except Exception as exc:  # noqa: BLE001
                skeleton: Dict[str, Any] = {
                    "id": self._make_id("FILE", file_path),
                    "file_path": file_path,
                    "language": self._get_language(ext),
                    "total_lines": len(content.splitlines()),
                    "blocks": self._normalize_blocks(blocks),
                    "source_digest": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    "outline_error": str(exc),
                }
                return skeleton

        skeleton: Dict[str, Any] = {
            "id": self._make_id("FILE", file_path),
            "file_path": file_path,
            "language": self._get_language(ext),
            "total_lines": len(content.splitlines()),
            "blocks": self._normalize_blocks(blocks),
            "source_digest": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }
        if include_outline:
            try:
                skeleton["outline"] = outline
            except NameError:
                pass
        return skeleton

    def analyze_files(
        self,
        file_paths: List[str],
        include_outline: bool = False,
        outline_max_depth: int = 6,
        outline_max_nodes: int = 400,
        outline_include_text: bool = False,
        outline_include_unnamed: bool = False,
        root_dir: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        results = []
        for file_path in file_paths:
            skeleton = self.analyze_file(
                file_path,
                include_outline=include_outline,
                outline_max_depth=outline_max_depth,
                outline_max_nodes=outline_max_nodes,
                outline_include_text=outline_include_text,
                outline_include_unnamed=outline_include_unnamed,
                root_dir=root_dir,
            )
            if skeleton:
                results.append(skeleton)
        return results

    def raw_tree(
        self,
        file_path: str,
        include_text: bool = False,
        max_nodes: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Return the raw Tree-sitter parse tree for a single file as a JSON-serializable
        dictionary. This intentionally skips the legacy parser and any post-processing.
        """
        if self.use_legacy_parser:
            raise RuntimeError("Tree-sitter is disabled; raw tree is unavailable.")

        ext = os.path.splitext(file_path)[1].lower()
        lang_key = self.supported_extensions.get(ext)
        if not lang_key:
            raise ValueError(f"Unsupported file extension: {ext}")

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise RuntimeError(f"Error reading file: {exc}") from exc

        parser = self.parsers.get(ext)
        if not parser:
            raise RuntimeError(f"No Tree-sitter parser loaded for extension: {ext}")

        try:
            limit = int(max_nodes) if max_nodes not in (None, "") else None
            if limit is not None and limit < 1:
                limit = None
        except (TypeError, ValueError):
            raise ValueError("max_nodes must be an integer if provided")

        tree = parser.parse(content.encode("utf-8"))
        node_count = 0
        truncated = False

        def _node_to_dict(node):
            nonlocal node_count, truncated
            if limit is not None and node_count >= limit:
                truncated = True
                return None
            node_count += 1

            entry: Dict[str, Any] = {
                "type": node.type,
                "is_named": node.is_named,
                "start": {
                    "line": node.start_point[0] + 1,
                    "column": node.start_point[1] + 1,
                    "byte": node.start_byte,
                },
                "end": {
                    "line": node.end_point[0] + 1,
                    "column": node.end_point[1] + 1,
                    "byte": node.end_byte,
                },
            }
            if include_text:
                entry["text"] = content[node.start_byte : node.end_byte]

            children_payload = []
            for child in node.children:
                child_dict = _node_to_dict(child)
                if child_dict:
                    children_payload.append(child_dict)
                if limit is not None and node_count >= limit:
                    break

            if children_payload:
                entry["children"] = children_payload
            return entry

        root_payload = _node_to_dict(tree.root_node)

        return {
            "file_path": file_path,
            "language": lang_key,
            "node_count": node_count,
            "truncated": truncated,
            "root": root_payload,
        }

    def raw_outline(
        self,
        file_path: str,
        include_text: bool = False,
        max_depth: int = 6,
        max_nodes: Optional[int] = 400,
        include_unnamed: bool = False,
    ) -> Dict[str, Any]:
        """Build a hierarchical outline of named Tree-sitter nodes with location spans."""
        if self.use_legacy_parser:
            raise RuntimeError("Tree-sitter is disabled; outline is unavailable.")

        ext = os.path.splitext(file_path)[1].lower()
        lang_key = self.supported_extensions.get(ext)
        if not lang_key:
            raise ValueError(f"Unsupported file extension: {ext}")

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise RuntimeError(f"Error reading file: {exc}") from exc

        parser = self.parsers.get(ext)
        if not parser:
            raise RuntimeError(f"No Tree-sitter parser loaded for extension: {ext}")

        max_depth_val = max(1, int(max_depth)) if isinstance(max_depth, int) else 6
        max_nodes_val: Optional[int] = None
        try:
            if max_nodes not in (None, ""):
                max_nodes_val = int(max_nodes)
                if max_nodes_val < 1:
                    max_nodes_val = None
        except (TypeError, ValueError):
            raise ValueError("max_nodes must be an integer if provided")

        tree = parser.parse(content.encode("utf-8"))
        node_count = 0
        truncated = False

        def _walk(node, depth=0):
            nonlocal node_count, truncated
            if max_nodes_val is not None and node_count >= max_nodes_val:
                truncated = True
                return None

            is_root = depth == 0
            if not node.is_named and not include_unnamed and not is_root:
                return None

            node_count += 1
            entry: Dict[str, Any] = {
                "type": node.type,
                "is_named": node.is_named,
                "start": {
                    "line": node.start_point[0] + 1,
                    "column": node.start_point[1] + 1,
                    "byte": node.start_byte,
                },
                "end": {
                    "line": node.end_point[0] + 1,
                    "column": node.end_point[1] + 1,
                    "byte": node.end_byte,
                },
            }
            if include_text:
                snippet = content[node.start_byte : node.end_byte]
                entry["text"] = snippet

            if depth >= max_depth_val:
                return entry

            children_payload = []
            for child in node.children:
                if max_nodes_val is not None and node_count >= max_nodes_val:
                    truncated = True
                    break
                child_dict = _walk(child, depth + 1)
                if child_dict:
                    children_payload.append(child_dict)
            if children_payload:
                entry["children"] = children_payload
            return entry

        root_payload = _walk(tree.root_node, 0)

        return {
            "file_path": file_path,
            "language": lang_key,
            "node_count": node_count,
            "truncated": truncated,
            "root": root_payload,
        }

    def _parse_file(self, content: str, file_path: str, ext: str, root_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.use_legacy_parser:
            return self._parse_with_legacy(content, file_path, ext)

        lang_key = self.supported_extensions.get(ext)
        parser = self.parsers.get(ext)
        query = self.queries.get(lang_key)
        if not parser or not query:
            return self._parse_with_legacy(content, file_path, ext)

        try:
            return self._parse_with_tree_sitter(content, file_path, ext, parser, query, lang_key, root_dir=root_dir)
        except Exception as exc:  # noqa: BLE001
            print(f"Tree-sitter parse error for {file_path}: {exc}; falling back to legacy parser.")
            return self._parse_with_legacy(content, file_path, ext)

    def _parse_with_tree_sitter(
        self,
        content: str,
        file_path: str,
        ext: str,
        parser: Parser,
        query,
        lang_key: str,
        root_dir: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        tree = parser.parse(content.encode("utf-8"))
        captures = query.captures(tree.root_node)

        blocks: List[Tuple[int, Dict[str, Any]]] = []
        seen = set()
        
        # Track occurrences of signatures/names to ensure stable IDs provided content structure is similar
        # Key: (block_type, normalize_signature) -> count
        occurrence_tracker: Dict[Tuple[str, str], int] = {}
        
        def _get_occurrence_index(b_type: str, b_sig: str) -> int:
            norm = re.sub(r'\s+', ' ', b_sig).strip()
            key = (b_type, norm)
            idx = occurrence_tracker.get(key, 0)
            occurrence_tracker[key] = idx + 1
            return idx

        for node, capture_name in captures:
            if capture_name.endswith(".name"):
                continue
            if node in seen:
                continue
            seen.add(node)

            if capture_name == "import":
                # Imports are often single lines, we group them later. 
                # For individual import nodes, we use the raw text as signature proxy.
                raw_text = _safe_slice(content, node.start_byte, node.end_byte)
                idx = _get_occurrence_index("import", raw_text)
                block = self._build_block_from_node(content, node, file_path, "import", "import", occurrence_index=idx, seed_name=raw_text, root_dir=root_dir)
            elif capture_name in {"func", "method"}:
                name = self._capture_name(content, query, node, "func.name") or self._capture_name(
                    content, query, node, "method.name"
                )
                signature = self._first_line_signature(content, node, fallback=name or "function")
                idx = _get_occurrence_index("function_def", name or signature)
                block = self._build_block_from_node(
                    content, node, file_path, "function_def", name or "function", signature, occurrence_index=idx, seed_name=name, root_dir=root_dir
                )
                block["body_content"] = block["content"]
            elif capture_name == "class":
                name = self._capture_name(content, query, node, "class.name")
                signature = self._first_line_signature(content, node, fallback=f"class {name or 'Class'}")
                idx = _get_occurrence_index("class_def", name or signature)
                block = self._build_block_from_node(
                    content, node, file_path, "class_def", name or "class", signature, occurrence_index=idx, seed_name=name, root_dir=root_dir
                )
                block["body_content"] = block["content"]
            elif capture_name == "json":
                # JSON usually one block
                block = self._parse_with_legacy(content, file_path, ext)[0]
            elif capture_name in {"element", "script", "style"}:
                if capture_name == "element":
                    depth = self._node_depth(node, limit=self.max_html_depth + 4)
                    if depth > self.max_html_depth:
                        continue
                    tag_label = self._capture_html_tag(node, content)
                else:
                    tag_label = capture_name

                friendly_label = tag_label or "element"
                idx = _get_occurrence_index("html_section", friendly_label)
                
                block = self._build_block_from_node(content, node, file_path, "html_section", friendly_label, occurrence_index=idx, seed_name=friendly_label, root_dir=root_dir)
                snippet = self._extract_html_text(block["content"])
                friendly_name = tag_label or (snippet[:30] if snippet else "html_block")
                block["name"] = friendly_name
                block["signature"] = friendly_name

                if capture_name == "script":
                    script_text = self._extract_script_content(block["content"])
                    if script_text.strip():
                        try:
                            script_blocks = self._parse_file(script_text, f"{file_path}#script", ".js")
                            block["script_blocks"] = script_blocks
                        except Exception as exc:  # noqa: BLE001
                            block["script_error"] = str(exc)
            elif capture_name == "var":
                name = self._capture_name(content, query, node, "var.name")
                signature = self._first_line_signature(content, node, fallback=name or "var")
                idx = _get_occurrence_index("var_decl", signature)
                block = self._build_block_from_node(
                    content, node, file_path, "var_decl", name or "var", signature, occurrence_index=idx, root_dir=root_dir
                )
                if not block["content"].strip() or block["content"].strip() in {"{", "}", ";"}:
                    continue
                if lang_key == "javascript" and not self._is_js_function_scope(node):
                    block["_merge_inline"] = True
            elif capture_name == "control":
                signature = self._first_line_signature(content, node, node.type)
                idx = _get_occurrence_index("control", signature)
                block = self._build_block_from_node(
                    content, node, file_path, "control", node.type, signature, occurrence_index=idx, root_dir=root_dir
                )
                if not block["content"].strip() or block["content"].strip() in {"{", "}", ";"}:
                    continue
                if lang_key == "javascript" and not self._is_js_function_scope(node):
                    block["_merge_inline"] = True
            else:
                continue

            blocks.append((block["lines"][0], block))

        blocks.sort(key=lambda item: item[0])
        flat_blocks = [block for _, block in blocks] or self._fallback_raw_block(content, file_path, ext)
        if lang_key == "python":
            flat_blocks = self._merge_contiguous_imports(flat_blocks, content, file_path)
            flat_blocks = self._ensure_python_body_block(flat_blocks, content, file_path)
        if lang_key == "javascript":
            flat_blocks = self._merge_js_inline_blocks(flat_blocks, content, file_path)
            flat_blocks = self._merge_js_misc_blocks(flat_blocks, content, file_path)
            flat_blocks = self._merge_js_generic_blocks(flat_blocks, content, file_path)
        if lang_key == "html" and not any(block.get("type") == "html_section" for block in flat_blocks):
            # Ensure HTML always shows content even if parsing produced no sections
            flat_blocks = self._fallback_raw_block(content, file_path, ext)
        elif lang_key == "html":
            flat_blocks = self._ensure_html_full_block(flat_blocks, content, file_path)
        return flat_blocks

    def _parse_with_legacy(self, content: str, file_path: str, ext: str) -> List[Dict[str, Any]]:
        if ext in {".py"}:
            return self._legacy_strategy.parse_python(content, file_path)
        if ext in {".json"}:
            return self._legacy_strategy.parse_json(content, file_path)
        if ext in {".html", ".htm"}:
            return self._legacy_strategy.parse_html(content, file_path)
        if ext in {".js", ".jsx", ".ts", ".tsx"}:
            return self._legacy_strategy.parse_javascript(content, file_path)
        return self._fallback_raw_block(content, file_path, ext)

    def _fallback_raw_block(self, content: str, file_path: str, ext: str) -> List[Dict[str, Any]]:
        return [
            {
                "id": self._make_id("BLK", f"raw:{file_path}"),
                "type": "raw_text",
                "name": os.path.basename(file_path),
                "signature": os.path.basename(file_path),
                "lines": [1, len(content.splitlines()) or 1],
                "content": content,
                "body_content": content,
                "foldable": True,
                "start_open": True,
                "selected": False,
            }
        ]

    def _inject_file_body_block(
        self, blocks: List[Dict[str, Any]], content: str, file_path: str
    ) -> List[Dict[str, Any]]:
        """Ensure every file has a root body block that mirrors the exact text."""

        total_lines = len(content.splitlines()) or 1
        file_block = {
            "id": self._make_id("BLK", f"file_body:{file_path}"),
            "type": "file_body",
            "name": "file_body",
            "signature": "full file (read-only) — other blocks are focused views",
            "lines": [1, total_lines],
            "content": content,
            "body_content": content,
            "foldable": True,
            "start_open": True,
            "selected": False,
        }

        return [file_block] + blocks

    def _append_integrity_block(
        self, blocks: List[Dict[str, Any]], content: str, file_path: str
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Add an integrity verification block that compares captured text to the source."""

        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        fidelity = self._verify_block_fidelity(blocks, content)

        integrity_block = {
            "id": self._make_id("BLK", f"integrity:{file_path}"),
            "type": "integrity_check",
            "name": "integrity",
            "signature": "integrity check (no mutation allowed)",
            "lines": [1, len(content.splitlines()) or 1],
            "content": "✅ النص مطابق بالكامل." if fidelity["ok"] else "❌ اختلاف مع النص الأصلي.",
            "body_content": (
                "\n".join(
                    [
                        f"sha256: {digest}",
                        f"source length: {len(content)} chars",
                        f"blocks_checked: {fidelity['checked']}",
                        f"mismatches: {len(fidelity['mismatches'])}",
                    ]
                )
                + (
                    "\n" + json.dumps(fidelity["mismatches"], ensure_ascii=False, indent=2)
                    if fidelity["mismatches"]
                    else ""
                )
            ),
            "foldable": True,
            "start_open": True,
            "selected": False,
        }

        return blocks, integrity_block

    def _verify_block_fidelity(self, blocks: List[Dict[str, Any]], content: str) -> Dict[str, Any]:
        """Ensure each block's captured text matches the source slice exactly."""

        lines = content.splitlines(keepends=True)
        total_lines = len(lines) or 1
        mismatches: List[Dict[str, Any]] = []
        checked = 0

        for block in blocks:
            if block.get("type") in {"file_body", "integrity_check", "warning"}:
                continue
            if "lines" not in block or "content" not in block:
                continue

            start, end = block["lines"][0], block["lines"][1]
            if start < 1 or end > total_lines:
                mismatches.append(
                    {
                        "type": block.get("type", "block"),
                        "name": block.get("name"),
                        "lines": block.get("lines"),
                        "reason": "range_out_of_bounds",
                    }
                )
                continue

            expected = "".join(lines[start - 1 : end])
            actual = block.get("content", "")
            checked += 1

            if expected != actual:
                mismatches.append(
                    {
                        "type": block.get("type", "block"),
                        "name": block.get("name"),
                        "lines": block.get("lines"),
                        "expected_len": len(expected),
                        "actual_len": len(actual),
                    }
                )

        return {"ok": not mismatches, "checked": checked, "mismatches": mismatches}

    def _build_block_from_node(
        self,
        content: str,
        node,
        file_path: str,
        block_type: str,
        name: str,
        signature: Optional[str] = None,
        occurrence_index: int = 0,
        seed_name: Optional[str] = None,
        root_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        block_content = _safe_slice(content, node.start_byte, node.end_byte)
        
        # STABLE ID GENERATION:
        # Uses file_path, block_type, seed_name (stable), and occurrence_index.
        # This decouples the ID from the exact body content and line numbers.
        target_name = seed_name or signature or name
        norm_name = re.sub(r'\s+', ' ', target_name).strip()
        
        if root_dir:
            try:
                # Calculate relative path and normalize to POSIX style for cross-platform stability
                rel_path = os.path.relpath(file_path, root_dir)
                seed_path = rel_path.replace(os.sep, '/')
            except ValueError:
                seed_path = file_path # Fallback if paths on different drives
        else:
            seed_path = file_path

        seed = f"{block_type}::{seed_path}::{norm_name}::{occurrence_index}"
        
        return {
            "id": self._make_id("BLK", seed),
            "type": block_type,
            "name": name,
            "signature": signature or name,
            "lines": [start_line, end_line],
            "content": block_content,
            "foldable": True,
            "selected": False,
        }

    def _capture_name(self, content: str, query, node, capture_name: str) -> Optional[str]:
        for child, name in query.captures(node):
            if name == capture_name:
                return _safe_slice(content, child.start_byte, child.end_byte)
        return None

    def _is_js_function_scope(self, node) -> bool:
        function_types = {
            "function",
            "function_declaration",
            "method_definition",
            "generator_function",
            "generator_function_declaration",
            "arrow_function",
        }
        current = getattr(node, "parent", None)
        while current is not None:
            if current.type in function_types:
                return True
            current = getattr(current, "parent", None)
        return False

    def _capture_html_tag(self, node, content: str) -> str:
        text = _safe_slice(content, node.start_byte, node.end_byte)
        first_line = text.strip().split("\n", 1)[0]
        tag_match = re.match(r"<\s*([a-zA-Z0-9:_-]+)", first_line)
        tag_name = tag_match.group(1).lower() if tag_match else "element"
        id_match = re.search(r'id\s*=\s*["\\\']([^"\\\']+)["\\\']', first_line)
        class_match = re.search(r'class\s*=\s*["\\\']([^"\\\']+)["\\\']', first_line)
        parts = [f"<{tag_name}"]
        if id_match:
            parts.append(f'id={id_match.group(1)}')
        if class_match:
            parts.append(f'class={class_match.group(1)}')
        return " ".join(parts) + ">"

    def _first_line_signature(self, content: str, node, fallback: str) -> str:
        text = _safe_slice(content, node.start_byte, node.end_byte).strip()
        first_line = text.split("\n", 1)[0]
        return first_line or fallback

    def _extract_script_content(self, full_tag_text: str) -> str:
        """Extract inner text of a <script> tag."""
        if ">" not in full_tag_text or "<" not in full_tag_text:
            return full_tag_text
        try:
            inner = full_tag_text.split(">", 1)[1]
            inner = inner.rsplit("<", 1)[0]
            return inner
        except Exception:  # noqa: BLE001
            return full_tag_text

    def _node_depth(self, node, limit: int = 20) -> int:
        """Count depth of a node by walking parents until limit."""
        depth = 0
        current = getattr(node, "parent", None)
        while current is not None and depth < limit:
            depth += 1
            current = getattr(current, "parent", None)
        return depth

    def _extract_html_text(self, html: str) -> str:
        """Extract plain text snippet from HTML content for naming purposes."""
        if not html:
            return ""
        # Strip tags and condense whitespace
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\\s+", " ", text).strip()
        return text[:120]

    def _html_root_label(self, content: str) -> str:
        first_tag = re.search(r"<\s*([a-zA-Z0-9:_-]+)([^>]*)>", content)
        if not first_tag:
            return "<document>"
        tag_name = first_tag.group(1).lower()
        attrs = first_tag.group(2) or ""
        id_match = re.search(r'id\s*=\s*["\']([^"\']+)["\']', attrs)
        class_match = re.search(r'class\s*=\s*["\']([^"\']+)["\']', attrs)
        pieces = [f"<{tag_name}"]
        if id_match:
            pieces.append(f"id={id_match.group(1)}")
        if class_match:
            pieces.append(f"class={class_match.group(1)}")
        return " ".join(pieces) + ">"

    def _merge_contiguous_imports(
        self, blocks: List[Dict[str, Any]], content: Optional[str] = None, file_path: str = ""
    ) -> List[Dict[str, Any]]:
        """Merge import statements into a single top-of-file region when possible."""

        if not content:
            return self._merge_contiguous_generic_imports(blocks)

        import_blocks = [b for b in blocks if b.get("type") == "import"]
        if not import_blocks:
            return blocks

        lines = content.splitlines(keepends=True)
        total_lines = len(lines) or 1

        # Discover the first import line from actual text to avoid inflated ranges
        first_import_idx: Optional[int] = None
        import_pattern = re.compile(r"^\s*(import |from \S+ import )")
        for idx, line in enumerate(lines):
            if import_pattern.match(line):
                first_import_idx = idx
                break

        if first_import_idx is None:
            return blocks

        region_start = first_import_idx + 1
        # Pull in leading comment/blank lines that are glued to the imports
        for idx in range(first_import_idx - 1, -1, -1):
            stripped = lines[idx].strip()
            if stripped.startswith("#") or not stripped:
                region_start = idx + 1
            else:
                break

        region_end = first_import_idx + 1
        paren_depth = 0
        continuation = False
        for idx in range(first_import_idx, total_lines):
            stripped = lines[idx].strip()
            paren_depth += lines[idx].count("(") - lines[idx].count(")")
            continuation = stripped.endswith("\\") or paren_depth > 0

            if import_pattern.match(lines[idx]) or continuation or stripped.startswith("#") or not stripped:
                region_end = idx + 1
                continue
            break

        region_text = "".join(lines[region_start - 1 : region_end]) if lines else ""
        
        # STABLE ID: Import region is unique per file in this logic, so we just use the file path.
        # This allows adding imports without changing the block ID.
        seed = f"import_region::{file_path}"
        
        merged_block = {
            "id": self._make_id("BLK", seed),
            "type": "import",
            "name": "imports",
            "signature": "import region",
            "lines": [region_start, max(region_end, region_start)],
            "content": region_text,
            "body_content": region_text,
            "foldable": True,
            "start_open": True,
        }

        others = [b for b in blocks if b.get("type") != "import"]
        merged = [merged_block] + others
        merged.sort(key=lambda b: b["lines"][0])
        return merged

    def _merge_contiguous_generic_imports(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None

        for block in blocks:
            if block.get("type") != "import":
                merged.append(block)
                current = None
                continue

            if current and current["type"] == "import" and block["lines"][0] <= current["lines"][1] + 1:
                current["lines"][1] = max(current["lines"][1], block["lines"][1])
                separator = "" if current.get("content", "").endswith("\n") else "\n"
                current["content"] = f"{current.get('content', '')}{separator}{block.get('content', '')}"
                current["body_content"] = current.get("content", "")
            else:
                current = {
                    **block,
                    "name": block.get("name") or "import",
                    "signature": block.get("signature") or "import block",
                    "body_content": block.get("body_content") or block.get("content", ""),
                    "foldable": True,
                }
                merged.append(current)

        return merged

    def _ensure_python_body_block(
        self, blocks: List[Dict[str, Any]], content: str, file_path: str
    ) -> List[Dict[str, Any]]:
        """Guarantee Python files show their module body, not just imports."""

        if any(block.get("type") != "import" for block in blocks):
            return blocks

        total_lines = len(content.splitlines()) or 1
        last_import_end = max((block["lines"][1] for block in blocks if block.get("type") == "import"), default=0)
        start_line = last_import_end + 1 if last_import_end < total_lines else 1

        remainder = "".join(content.splitlines(keepends=True)[start_line - 1 :])
        
        # STABLE ID: Module body is unique per file.
        seed = f"module_body::{file_path}"
        
        module_block = {
            "id": self._make_id("BLK", seed),
            "type": "module_body",
            "name": "module",
            "signature": "module body",
            "lines": [start_line, total_lines],
            "content": remainder or content,
            "body_content": remainder or content,
            "foldable": True,
            "selected": False,
        }

        return blocks + [module_block]

    def _ensure_html_full_block(
        self, blocks: List[Dict[str, Any]], content: str, file_path: str
    ) -> List[Dict[str, Any]]:
        """Add a full-document HTML block when captures miss the outermost wrapper."""

        total_lines = len(content.splitlines()) or 1
        has_full = any(
            block.get("lines")
            and block["lines"][0] <= 1
            and block["lines"][1] >= total_lines
            for block in blocks
        )
        if has_full:
            return blocks

        root_label = self._html_root_label(content)

        document_block = {
            "id": self._make_id("BLK", f"html_document:{file_path}"),
            "type": "html_section",
            "name": root_label,
            "signature": root_label,
            "lines": [1, total_lines],
            "content": content,
            "body_content": content,
            "foldable": True,
            "selected": False,
            "start_open": True,
        }

        return [document_block] + blocks

    def _outline_truncation_block(self, file_path: str) -> Dict[str, Any]:
        """Warn users when outlines are truncated so they can request raw view."""

        message = (
            "⚠️ تم تقليص شجرة التحليل بسبب حدود العمق/العقد."
            " استخدم \"إظهار الخام\" لعرض الملف كاملاً.\n"
            "رابط مقترح: إظهار الخام"
        )
        return {
            "id": self._make_id("BLK", f"outline_warning:{file_path}"),
            "type": "warning",
            "name": "outline warning",
            "signature": "outline truncated — show raw to view الكل",
            "lines": [1, 1],
            "content": message,
            "body_content": message,
            "foldable": True,
            "start_open": True,
            "selected": False,
        }

    def _normalize_blocks(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Guarantee every block has a title, checkbox, and body text for the viewer."""

        normalized: List[Dict[str, Any]] = []
        for block in blocks:
            updated = dict(block)
            updated.setdefault("type", "block")
            updated.setdefault("name", updated["type"])
            updated.setdefault("signature", updated["name"])
            updated.setdefault("body_content", updated.get("content", ""))
            updated.setdefault("foldable", True)
            updated.setdefault("start_open", updated.get("type") in {"file_body", "import", "raw_text"})
            updated.setdefault("selected", False)
            updated.setdefault("selectable", True)
            normalized.append(updated)

        return normalized

    def _merge_js_inline_blocks(self, blocks: List[Dict[str, Any]], content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Merge contiguous top-level JS var/control blocks into a single inline_logic block
        to reduce noise and keep inline script context together.
        """
        if not blocks:
            return blocks

        merged: List[Dict[str, Any]] = []
        current_group: List[Dict[str, Any]] = []
        
        # Counter for inline logical blocks to ensure stable IDs
        inline_group_counter = 0

        def flush_group():
            nonlocal current_group, inline_group_counter
            if not current_group:
                return
            start_line = current_group[0]["lines"][0]
            end_line = current_group[-1]["lines"][1]
            lines = content.splitlines()
            group_content = "\n".join(lines[start_line - 1 : end_line])
            
            # Use a positional counter provided the file structure (order of blocks) is relatively stable
            inline_group_counter += 1
            seed = f"inline_logic::{file_path}::{inline_group_counter}"
            
            block = {
                "id": self._make_id("BLK", seed),
                "type": "inline_logic",
                "name": "inline_logic",
                "signature": (lines[start_line - 1].strip() if lines[start_line - 1 : end_line] else "inline"),
                "lines": [start_line, end_line],
                "content": group_content,
                "body_content": group_content,
                "foldable": True,
                "selected": False,
            }
            merged.append(block)
            current_group = []

        for block in blocks:
            if block.get("_merge_inline"):
                if not current_group:
                    current_group.append(block)
                else:
                    prev_end = current_group[-1]["lines"][1]
                    if block["lines"][0] <= prev_end + 1:
                        current_group.append(block)
                    else:
                        flush_group()
                        current_group.append(block)
            else:
                flush_group()
                merged.append(block)
        flush_group()
        return merged

    def _merge_js_misc_blocks(self, blocks: List[Dict[str, Any]], content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Group contiguous non-function/class/import JS blocks (var/control/inline_logic)
        into larger chunks to reduce noise.
        """
        mergeable_types = {"var_decl", "control", "inline_logic"}
        logic_counter = 0
        merged: List[Dict[str, Any]] = []
        group: List[Dict[str, Any]] = []

        def flush():
            nonlocal group, logic_counter
            if not group:
                return
            start = group[0]["lines"][0]
            end = group[-1]["lines"][1]
            lines = content.splitlines()
            group_content = "\n".join(lines[start - 1 : end])
            logic_counter += 1
            
            # Semantic ID for misc logic blocks: based on logic_counter order in file
            seed = f"misc_logic::{file_path}::{logic_counter}"
            
            block = {
                "id": self._make_id("BLK", seed),
                "type": "inline_logic",
                "name": f"block_{logic_counter}",
                "signature": lines[start - 1].strip() if lines[start - 1 : end] else "block",
                "lines": [start, end],
                "content": group_content,
                "body_content": group_content,
                "foldable": True,
                "selected": False,
            }
            merged.append(block)
            group = []

        for block in blocks:
            if block["type"] in mergeable_types:
                if not group:
                    group.append(block)
                else:
                    prev_end = group[-1]["lines"][1]
                    if block["lines"][0] <= prev_end + 2:  # allow a blank line gap
                        group.append(block)
                    else:
                        flush()
                        group.append(block)
            else:
                flush()
                merged.append(block)
        flush()
        return merged

    def _merge_js_generic_blocks(self, blocks: List[Dict[str, Any]], content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Final pass: merge any contiguous blocks that are not functions/classes/json/html
        (e.g., imports + inline logic) into compact chunks.
        """
        keep_types = {"function_def", "class_def", "json_structure", "html_section"}
        function_like_ranges = [
            (b["lines"][0], b["lines"][1])
            for b in blocks
            if b["type"] in {"function_def", "class_def"}
        ]

        mergeable: List[Dict[str, Any]] = []
        merged: List[Dict[str, Any]] = []
        logic_counter = 0
        lines = content.splitlines()

        def flush():
            nonlocal mergeable, logic_counter
            if not mergeable:
                return
            start = mergeable[0]["lines"][0]
            end = mergeable[-1]["lines"][1]
            chunk = "\n".join(lines[start - 1 : end])
            logic_counter += 1
            block = {
                "id": self._make_id("BLK", f"chunk:{file_path}:{start}:{end}"),
                "type": "module_scope",
                "name": f"block_{logic_counter}",
                "signature": lines[start - 1].strip() if lines[start - 1 : end] else "module scope",
                "lines": [start, end],
                "content": chunk,
                "body_content": chunk,
                "foldable": True,
                "selected": False,
            }
            merged.append(block)
            mergeable = []

        for block in blocks:
            if block["type"] in keep_types:
                flush()
                merged.append(block)
                continue
            # Skip inline/control blocks that are already inside a function/class,
            # since the parent block already contains their text.
            b_start, b_end = block["lines"]
            if any(start <= b_start and b_end <= end for start, end in function_like_ranges):
                continue
            # Always accumulate mergeable blocks together until a keep_type is encountered
            mergeable.append(block)
        flush()
        return merged

    def _get_language(self, ext: str) -> str:
        mapping = {
            ".py": "python",
            ".pyw": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "javascript",
            ".tsx": "javascript",
            ".html": "html",
            ".htm": "html",
            ".json": "json",
            ".c": "cpp",
            ".h": "cpp",
            ".cc": "cpp",
            ".cpp": "cpp",
            ".cxx": "cpp",
            ".hpp": "cpp",
            ".php": "php",
            ".phtml": "php",
            ".php5": "php",
            ".sql": "sql",
        }
        return mapping.get(ext, "unknown")
