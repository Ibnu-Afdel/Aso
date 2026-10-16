"""The `"aso"` preset (T-58): rules A1-A13 exactly as the guide defines them."""

from __future__ import annotations

import ast
import difflib
from pathlib import Path
from typing import Any

from aso.testing.arch._ast_utils import ModuleInfo, discover_modules, resolve_call_target
from aso.testing.arch._selection import ArchitectureViolation, Violation, _class_registry, arch

__all__ = ["arch_preset"]

_SQL_CALL_NAMES = ("text", "select", "insert", "update", "delete", "statement")
_RAW_INPUT_METHODS = {"json", "form", "body", "all", "input", "only", "except_"}


def _exists(base_path: Path, *parts: str) -> bool:
    return (base_path / Path(*parts)).exists()


def _a1(base_path: Path) -> list[Violation]:
    if not _exists(base_path, "app", "http", "controllers"):
        return []
    return arch("app.http.controllers").must_not_import("sqlalchemy", rule_id="A1")._collect()


def _a2(base_path: Path) -> list[Violation]:
    if not _exists(base_path, "app", "models"):
        return []
    return arch("app.models").must_not_import(
        "fastapi", "starlette", "aso.http", "aso.inertia", "aso.session", rule_id="A2"
    )._collect()


def _resolve_name(node: ast.expr, module: ModuleInfo) -> str | None:
    parts: list[str] = []
    cur: Any = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    else:
        return None
    parts.reverse()
    head, *rest = parts
    resolved = module.aliases.get(head, head)
    return ".".join([resolved, *rest]) if rest else resolved


def _annotation_name(node: ast.expr | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _a3(base_path: Path) -> list[Violation]:
    if not _exists(base_path, "app", "http", "controllers"):
        return []
    violations: list[Violation] = []
    for module in discover_modules(base_path, ("app.http.controllers",)):
        for class_def in module.classes:
            is_controller = any(_annotation_name(b) == "Controller" for b in class_def.bases)
            if not is_controller:
                continue
            for method in class_def.body:
                if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                request_params = {
                    arg.arg for arg in method.args.args if _annotation_name(arg.annotation) == "Request"
                }
                if not request_params:
                    continue
                for node in ast.walk(method):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr in _RAW_INPUT_METHODS
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id in request_params
                    ):
                        violations.append(
                            Violation(
                                "A3",
                                module,
                                node.lineno,
                                f"`{node.func.value.id}.{node.func.attr}()` reads raw input in a controller.",
                                "Take a `FormRequest` parameter instead (T-19).",
                            )
                        )
    return [v for v in violations if not v.module.is_ignored(v.lineno, v.rule)]


def _page_names(base_path: Path) -> list[str]:
    pages_dir = base_path / "resources" / "js" / "pages"
    if not pages_dir.is_dir():
        return []
    names = []
    for ext in (".tsx", ".jsx", ".ts", ".js"):
        for path in pages_dir.rglob(f"*{ext}"):
            rel = path.relative_to(pages_dir).with_suffix("")
            names.append("/".join(rel.parts))
    return names


def _a4(base_path: Path) -> list[Violation]:
    violations: list[Violation] = []
    existing = set(_page_names(base_path))
    targets = ("app", "routes")
    present = [t for t in targets if _exists(base_path, t)]
    if not present:
        return []
    for module in discover_modules(base_path, tuple(present)):
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.Call):
                continue
            first: ast.expr | None = None
            if isinstance(node.func, ast.Name):
                resolved = module.aliases.get(node.func.id, node.func.id)
                if resolved == "aso.inertia.inertia" or node.func.id == "inertia":
                    first = node.args[0] if node.args else None
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "inertia"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "Route"
            ):
                # `Route.inertia(path, "component", ...)` -> component is the 2nd positional arg.
                first = node.args[1] if len(node.args) > 1 else None
            if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
                continue
            name = first.value
            if name in existing:
                continue
            suggestion = difflib.get_close_matches(name, existing, n=1)
            fix = f'Did you mean "{suggestion[0]}"?' if suggestion else "Create the page file."
            violations.append(
                Violation(
                    "A4",
                    module,
                    node.lineno,
                    f'inertia("{name}") - page not found: resources/js/pages/{name}.tsx',
                    fix,
                )
            )
    return [v for v in violations if not v.module.is_ignored(v.lineno, v.rule)]


def _a5(base_path: Path) -> list[Violation]:
    present = [t for t in ("app", "routes", "bootstrap") if _exists(base_path, t)]
    if not present:
        return []
    violations: list[Violation] = []
    for module in discover_modules(base_path, tuple(present)):
        for target, lineno in module.import_records:
            root = target.split(".")[0]
            if root in {"cross_inertia", "inertia", "fastapi_inertia"}:
                violations.append(
                    Violation(
                        "A5",
                        module,
                        lineno,
                        f"imports [{target}], a third-party Inertia adapter.",
                        "Use `aso.inertia` instead; it owns the protocol (D-002).",
                    )
                )
    return [v for v in violations if not v.module.is_ignored(v.lineno, v.rule)]


def _last_assignment_value(func: ast.AST, name: str, before_line: int) -> ast.expr | None:
    found: ast.expr | None = None
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and node.lineno <= before_line:
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    found = node.value
    return found


def _is_unsafe_sql(node: ast.expr | None) -> bool:
    if node is None:
        return False
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mod, ast.Add)):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        return True
    return False


def _enclosing_function(tree: ast.Module, call: ast.Call) -> ast.AST:
    best: ast.AST = tree
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.lineno <= call.lineno <= (
            getattr(node, "end_lineno", None) or call.lineno
        ):
            best = node
    return best


def _a6(base_path: Path) -> list[Violation]:
    present = [t for t in ("app", "routes") if _exists(base_path, t)]
    if not present:
        return []
    violations: list[Violation] = []
    for module in discover_modules(base_path, tuple(present)):
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            target = resolve_call_target(node, module)
            if target is None:
                continue
            parts = target.split(".")
            simple = parts[-1]
            if simple not in _SQL_CALL_NAMES:
                continue
            is_db_call = (simple == "text" and "sqlalchemy" in parts) or (
                simple in {"select", "insert", "update", "delete", "statement"}
                and len(parts) >= 2
                and parts[-2] == "DB"
            )
            if not is_db_call:
                continue
            arg = node.args[0]
            unsafe = _is_unsafe_sql(arg)
            if not unsafe and isinstance(arg, ast.Name):
                func = _enclosing_function(module.tree, node)
                unsafe = _is_unsafe_sql(_last_assignment_value(func, arg.id, node.lineno))
            if unsafe:
                violations.append(
                    Violation(
                        "A6",
                        module,
                        node.lineno,
                        f"[{simple}()] receives a dynamically built SQL string.",
                        "Use `:name` bound parameters instead of an f-string/%/+ concatenation (T-30).",
                    )
                )
    return [v for v in violations if not v.module.is_ignored(v.lineno, v.rule)]


def _a7(base_path: Path) -> list[Violation]:
    if not _exists(base_path, "app"):
        return []
    return arch("app").must_not_call("print", "breakpoint", rule_id="A7")._collect()


def _a8(base_path: Path) -> list[Violation]:
    present = [t for t in ("app",) if _exists(base_path, t)]
    if not present:
        return []
    violations: list[Violation] = []
    for module in discover_modules(base_path, tuple(present)):
        for class_def in module.classes:
            for base in class_def.bases:
                resolved = _resolve_name(base, module)
                if resolved and resolved.rsplit(".", 1)[-1] == "BaseHTTPMiddleware":
                    violations.append(
                        Violation(
                            "A8",
                            module,
                            class_def.lineno,
                            f"class [{class_def.name}] subclasses `BaseHTTPMiddleware`.",
                            "Write a pure-ASGI middleware class instead (D-025, T-11).",
                        )
                    )
    return [v for v in violations if not v.module.is_ignored(v.lineno, v.rule)]


def _a9(base_path: Path) -> list[Violation]:
    if not _exists(base_path, "app"):
        return []
    return arch("app").must_not_call(
        "create_async_engine", "AsyncSession", "async_sessionmaker", rule_id="A9"
    )._collect()


def _a10(base_path: Path) -> list[Violation]:
    if not _exists(base_path, "app", "http", "requests"):
        return []
    selection = arch("app.http.requests")
    selection.classes().must_extend("FormRequest", rule_id="A10")
    violations = selection._collect()
    selection2 = arch("app.http.requests")
    selection2.classes().must_have_suffix("Request", rule_id="A10")
    violations += selection2._collect()
    return violations


def _a11(base_path: Path) -> list[Violation]:
    if not _exists(base_path, "app", "models"):
        return []
    selection = arch("app.models")
    selection.classes().must_have_attribute("__fillable__", "__guarded__", rule_id="A11")
    return selection._collect()


def _a12(base_path: Path) -> list[Violation]:
    if not _exists(base_path, "app", "jobs"):
        return []
    model_names = {name.rsplit(".", 1)[-1] for name in _class_registry(base_path) if ".models." in name}
    violations: list[Violation] = []
    for module in discover_modules(base_path, ("app.jobs",)):
        for class_def in module.classes:
            if not any(_annotation_name(b) == "Job" for b in class_def.bases):
                continue
            for method in class_def.body:
                if not (isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name == "__init__"):
                    continue
                for arg in method.args.args:
                    name = _annotation_name(arg.annotation)
                    if name and name in model_names:
                        violations.append(
                            Violation(
                                "A12",
                                module,
                                method.lineno,
                                f"Job [{class_def.name}].__init__ parameter [{arg.arg}] is annotated as a Model ([{name}]).",
                                "Take an id instead and load the model inside `handle()` (T-42).",
                            )
                        )
    return [v for v in violations if not v.module.is_ignored(v.lineno, v.rule)]


def _a13(base_path: Path) -> list[Violation]:
    present = [t for t in ("app", "routes", "bootstrap", "database") if _exists(base_path, t)]
    if not present:
        return []
    violations: list[Violation] = []
    for module in discover_modules(base_path, tuple(present)):
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Attribute) and node.attr == "environ":
                resolved = _resolve_name(node.value, module) if isinstance(node.value, ast.Name) else None
                if resolved == "os":
                    violations.append(
                        Violation("A13", module, node.lineno, "reads `os.environ` directly.", "Use `config()` instead (T-03).")
                    )
            if isinstance(node, ast.Call):
                target = resolve_call_target(node, module)
                if target in ("os.getenv", "getenv"):
                    violations.append(
                        Violation("A13", module, node.lineno, "calls `os.getenv()` directly.", "Use `config()` instead (T-03).")
                    )
    return [v for v in violations if not v.module.is_ignored(v.lineno, v.rule)]


_RULES: dict[str, Any] = {
    "A1": _a1,
    "A2": _a2,
    "A3": _a3,
    "A4": _a4,
    "A5": _a5,
    "A6": _a6,
    "A7": _a7,
    "A8": _a8,
    "A9": _a9,
    "A10": _a10,
    "A11": _a11,
    "A12": _a12,
    "A13": _a13,
}


class ArchPreset:
    """`arch_preset("aso")` (T-58): the shipped A1-A13 rule set."""

    def __init__(self, base_path: Path, rule_ids: tuple[str, ...]) -> None:
        self._base_path = base_path
        self._rule_ids = rule_ids
        self._ignoring: tuple[str, ...] = ()
        self._without: set[str] = set()

    def ignoring(self, *packages: str) -> ArchPreset:
        self._ignoring = (*self._ignoring, *packages)
        return self

    def without(self, *rule_ids: str) -> ArchPreset:
        self._without.update(rule_ids)
        return self

    def check(self) -> None:
        violations: list[Violation] = []
        for rule_id in self._rule_ids:
            if rule_id in self._without:
                continue
            rule_fn = _RULES[rule_id]
            for violation in rule_fn(self._base_path):
                if any(violation.module.dotted == pkg or violation.module.dotted.startswith(pkg + ".") for pkg in self._ignoring):
                    continue
                violations.append(violation)
        if not violations:
            return
        blocks = "\n\n".join(v.format(self._base_path) for v in violations)
        raise ArchitectureViolation(f"{blocks}\n\n{len(violations)} architecture rule(s) failed.")


def arch_preset(name: str = "aso") -> ArchPreset:
    if name != "aso":
        raise ValueError(f"Unknown architecture preset [{name!r}]. Only \"aso\" is defined.")
    from aso.foundation.paths import base_path

    return ArchPreset(base_path(), tuple(_RULES.keys()))
