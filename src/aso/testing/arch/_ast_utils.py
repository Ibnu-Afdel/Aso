"""AST plumbing shared by the architecture rules (T-58): discovering files for a dotted package
name, resolving imports (aliases, relative imports, `TYPE_CHECKING`), and reading `# arch:
ignore[ID] -- reason` suppression comments.
"""

from __future__ import annotations

import ast
import fnmatch
import io
import re
import tokenize
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["ModuleInfo", "discover_modules", "resolve_call_target"]

_IGNORE_RE = re.compile(r"#\s*arch:\s*ignore\[(\w+)\]\s*--\s*(\S.*)")


@dataclass
class ModuleInfo:
    dotted: str
    path: Path
    tree: ast.Module
    source: str
    aliases: dict[str, str]  # local name -> resolved dotted target
    import_records: list[tuple[str, int]]  # (resolved dotted target, lineno), TYPE_CHECKING excluded
    classes: list[ast.ClassDef] = field(default_factory=list)
    ignores: dict[int, set[str]] = field(default_factory=dict)

    def rel_path(self, base_path: Path) -> str:
        try:
            return str(self.path.relative_to(base_path))
        except ValueError:
            return str(self.path)

    def is_ignored(self, lineno: int, rule: str) -> bool:
        return rule in self.ignores.get(lineno, set())


def _dotted_for(base_path: Path, path: Path) -> str:
    rel = path.relative_to(base_path).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _files_for_dotted(base_path: Path, dotted: str) -> list[Path]:
    rel = Path(*dotted.split("."))
    direct = base_path / rel.with_suffix(".py")
    if direct.is_file():
        return [direct]
    pkg_dir = base_path / rel
    if pkg_dir.is_dir():
        return sorted(p for p in pkg_dir.rglob("*.py") if "__pycache__" not in p.parts)
    return []


def _all_py_files(base_path: Path) -> list[Path]:
    if not base_path.is_dir():
        return []
    return sorted(p for p in base_path.rglob("*.py") if "__pycache__" not in p.parts)


def _files_for_glob(base_path: Path, pattern: str) -> list[Path]:
    root = pattern.split(".")[0]
    candidates = _all_py_files(base_path / root) if (base_path / root).exists() else []
    matched: list[Path] = []
    for path in candidates:
        dotted = _dotted_for(base_path, path)
        if fnmatch.fnmatch(dotted, pattern):
            matched.append(path)
    return matched


def _is_type_checking(expr: ast.expr) -> bool:
    if isinstance(expr, ast.Attribute):
        return expr.attr == "TYPE_CHECKING"
    if isinstance(expr, ast.Name):
        return expr.id == "TYPE_CHECKING"
    return False


def _resolve_relative(module_dotted: str, module: str | None, level: int) -> str:
    if level == 0:
        return module or ""
    parts = module_dotted.split(".")
    package_parts = parts[:-1]  # the package this module lives in
    up = level - 1
    if up > 0:
        package_parts = package_parts[:-up] if up <= len(package_parts) else []
    base = ".".join(package_parts)
    if module:
        return f"{base}.{module}" if base else module
    return base


class _ImportVisitor(ast.NodeVisitor):
    def __init__(self, module_dotted: str) -> None:
        self.module_dotted = module_dotted
        self.aliases: dict[str, str] = {}
        self.records: list[tuple[str, int]] = []
        self._type_checking = 0

    def _record(self, target: str, lineno: int) -> None:
        if self._type_checking == 0:
            self.records.append((target, lineno))

    def visit_If(self, node: ast.If) -> None:  # noqa: N802 - ast.NodeVisitor naming
        if _is_type_checking(node.test):
            self._type_checking += 1
            for child in node.body:
                self.visit(child)
            self._type_checking -= 1
            for child in node.orelse:
                self.visit(child)
        else:
            self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            bound = alias.asname or alias.name.split(".")[0]
            target = alias.name if alias.asname else alias.name.split(".")[0]
            self.aliases[bound] = target
            self._record(alias.name, node.lineno)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        base = _resolve_relative(self.module_dotted, node.module, node.level)
        for alias in node.names:
            if alias.name == "*":
                continue
            full = f"{base}.{alias.name}" if base else alias.name
            bound = alias.asname or alias.name
            self.aliases[bound] = full
            self._record(full, node.lineno)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "importlib"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            self._record(node.args[0].value, node.lineno)
        self.generic_visit(node)


def _collect_ignores(source: str) -> dict[int, set[str]]:
    ignores: dict[int, set[str]] = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                match = _IGNORE_RE.search(tok.string)
                if match:
                    ignores.setdefault(tok.start[0], set()).add(match.group(1))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        pass
    return ignores


def _parse_module(base_path: Path, path: Path) -> ModuleInfo | None:
    try:
        source = path.read_text()
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return None
    dotted = _dotted_for(base_path, path)
    visitor = _ImportVisitor(dotted)
    visitor.visit(tree)
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    return ModuleInfo(
        dotted=dotted,
        path=path,
        tree=tree,
        source=source,
        aliases=visitor.aliases,
        import_records=visitor.records,
        classes=classes,
        ignores=_collect_ignores(source),
    )


def discover_modules(base_path: Path, packages: tuple[str, ...], ignoring: tuple[str, ...] = ()) -> list[ModuleInfo]:
    """Every `.py` file for the given dotted package names (globs allowed), minus `ignoring`."""
    files: dict[Path, None] = {}
    for dotted in packages:
        found = _files_for_glob(base_path, dotted) if "*" in dotted else _files_for_dotted(base_path, dotted)
        for path in found:
            files[path] = None
    modules: list[ModuleInfo] = []
    for path in files:
        info = _parse_module(base_path, path)
        if info is None:
            continue
        if any(info.dotted == pkg or info.dotted.startswith(pkg + ".") for pkg in ignoring):
            continue
        modules.append(info)
    return modules


def resolve_call_target(call: ast.Call, module: ModuleInfo) -> str | None:
    """`sa.text(...)` -> `"sqlalchemy.text"`, `DB.select(...)` -> `"DB.select"` (dotted name, with
    the leftmost component resolved through the module's import aliases when it is one)."""
    func = call.func
    parts: list[str] = []
    node: Any = func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    else:
        return None
    parts.reverse()
    head, *rest = parts
    resolved_head = module.aliases.get(head, head)
    return ".".join([resolved_head, *rest])
