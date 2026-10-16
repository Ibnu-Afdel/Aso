"""`arch(*packages)`: the fluent rule builder (T-58 "Writing your own rules")."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from aso.testing.arch._ast_utils import ModuleInfo, discover_modules, resolve_call_target

__all__ = ["ArchitectureViolation", "Violation", "arch"]


class ArchitectureViolation(AssertionError):
    """Raised by `.check()`. Subclasses `AssertionError` so pytest shows the full message."""


class Violation:
    def __init__(self, rule: str, module: ModuleInfo, lineno: int, message: str, fix: str = "") -> None:
        self.rule = rule
        self.module = module
        self.lineno = lineno
        self.message = message
        self.fix = fix

    def format(self, base_path: Path) -> str:
        rel = self.module.rel_path(base_path)
        lines = [f"{self.rule}  {rel}:{self.lineno}", f"    {self.message}"]
        if self.fix:
            lines.append(f"    Fix: {self.fix}")
        return "\n".join(lines)


def _simple_name(target: Any) -> str:
    """A class object, or a dotted/plain string -> its simple (last-component) name."""
    if isinstance(target, str):
        return target.rsplit(".", 1)[-1]
    return getattr(target, "__name__", str(target))


def _resolve_attr_or_name(node: ast.expr, module: ModuleInfo) -> str | None:
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


def _base_names(class_def: ast.ClassDef, module: ModuleInfo) -> list[str | None]:
    return [_resolve_attr_or_name(base, module) for base in class_def.bases]


def _class_registry(base_path: Path) -> dict[str, tuple[ModuleInfo, ast.ClassDef]]:
    """Every class under the whole project (for one level of transitive `must_extend`)."""
    registry: dict[str, tuple[ModuleInfo, ast.ClassDef]] = {}
    for top in ("app", "routes", "bootstrap", "database", "config"):
        for module in discover_modules(base_path, (top,)):
            for class_def in module.classes:
                registry[f"{module.dotted}.{class_def.name}"] = (module, class_def)
    return registry


class ArchSelection:
    def __init__(
        self,
        base_path: Path,
        packages: tuple[str, ...],
        *,
        ignoring: tuple[str, ...] = (),
        target: str = "modules",
        public_only: bool = False,
    ) -> None:
        self._base_path = base_path
        self._packages = packages
        self._ignoring = ignoring
        self._target = target  # "modules" | "classes" | "functions"
        self._public_only = public_only
        self._rules: list[Any] = []  # list[Callable[[list[ModuleInfo]], list[Violation]]]

    # ------------------------------------------------------------ selection

    def ignoring(self, *packages: str) -> ArchSelection:
        self._ignoring = (*self._ignoring, *packages)
        return self

    def classes(self) -> ArchSelection:
        self._target = "classes"
        return self

    def functions(self, public: bool = False) -> ArchSelection:
        self._target = "functions"
        self._public_only = public
        return self

    def _modules(self) -> list[ModuleInfo]:
        return discover_modules(self._base_path, self._packages, self._ignoring)

    # ------------------------------------------------------------ module-level rules

    def must_import(self, *names: str) -> ArchSelection:
        def rule(modules: list[ModuleInfo]) -> list[Violation]:
            out: list[Violation] = []
            for module in modules:
                targets = {t for t, _ in module.import_records}
                if not any(any(t == n or t.startswith(n + ".") for t in targets) for n in names):
                    out.append(
                        Violation(
                            "must_import",
                            module,
                            1,
                            f"[{module.dotted}] does not import any of {list(names)}.",
                            "Add the required import.",
                        )
                    )
            return out

        self._rules.append(rule)
        return self

    def must_not_import(self, *names: str, rule_id: str = "must_not_import") -> ArchSelection:
        def rule(modules: list[ModuleInfo]) -> list[Violation]:
            out: list[Violation] = []
            for module in modules:
                for target, lineno in module.import_records:
                    if any(target == n or target.startswith(n + ".") for n in names):
                        out.append(
                            Violation(
                                rule_id,
                                module,
                                lineno,
                                f"imports [{target}], which [{module.dotted}] must not import.",
                                f"Remove the dependency on {target}.",
                            )
                        )
            return out

        self._rules.append(rule)
        return self

    def must_only_import(self, *names: str) -> ArchSelection:
        import sys

        stdlib = set(sys.stdlib_module_names)

        def rule(modules: list[ModuleInfo]) -> list[Violation]:
            out: list[Violation] = []
            for module in modules:
                for target, lineno in module.import_records:
                    root = target.split(".")[0]
                    if root in stdlib or root == module.dotted.split(".")[0]:
                        continue
                    if not any(target == n or target.startswith(n + ".") for n in names):
                        out.append(
                            Violation(
                                "must_only_import",
                                module,
                                lineno,
                                f"imports [{target}], which is outside the allowed list {list(names)}.",
                                "Remove the import, or allow it explicitly.",
                            )
                        )
            return out

        self._rules.append(rule)
        return self

    def must_not_call(self, *names: str, rule_id: str = "must_not_call") -> ArchSelection:
        def rule(modules: list[ModuleInfo]) -> list[Violation]:
            out: list[Violation] = []
            for module in modules:
                for node in ast.walk(module.tree):
                    if not isinstance(node, ast.Call):
                        continue
                    target = resolve_call_target(node, module)
                    if target is None:
                        continue
                    if any(target == n or target.endswith("." + n) for n in names):
                        out.append(
                            Violation(
                                rule_id,
                                module,
                                node.lineno,
                                f"calls [{target}()], which is not allowed here.",
                                "Remove the call, or use the framework's own helper instead.",
                            )
                        )
            return out

        self._rules.append(rule)
        return self

    # ------------------------------------------------------------ class rules

    def must_extend(self, target: Any, *, rule_id: str = "must_extend") -> ArchSelection:
        wanted = _simple_name(target)
        registry = _class_registry(self._base_path)

        def satisfies(class_def: ast.ClassDef, module: ModuleInfo, _seen: frozenset[str] = frozenset()) -> bool | None:
            bases = _base_names(class_def, module)
            if not bases:
                return False
            unresolved = False
            for base in bases:
                if base is None:
                    unresolved = True
                    continue
                if base.rsplit(".", 1)[-1] == wanted:
                    return True
                key = base if "." in base else f"{module.dotted}.{base}"
                if key in registry and key not in _seen:
                    parent_module, parent_def = registry[key]
                    result = satisfies(parent_def, parent_module, _seen | {key})
                    if result:
                        return True
                    if result is None:
                        unresolved = True
            return None if unresolved else False

        def rule(modules: list[ModuleInfo]) -> list[Violation]:
            out: list[Violation] = []
            for module in modules:
                for class_def in module.classes:
                    result = satisfies(class_def, module)
                    if result is True:
                        continue
                    if result is None:
                        out.append(
                            Violation(
                                rule_id,
                                module,
                                class_def.lineno,
                                f"class [{class_def.name}] - could not verify it extends [{wanted}].",
                                f"Make sure [{class_def.name}] extends [{wanted}] directly or through a resolvable base.",
                            )
                        )
                    else:
                        out.append(
                            Violation(
                                rule_id,
                                module,
                                class_def.lineno,
                                f"class [{class_def.name}] does not extend [{wanted}].",
                                f"Make [{class_def.name}] extend [{wanted}].",
                            )
                        )
            return out

        self._rules.append(rule)
        return self

    def must_have_suffix(self, suffix: str, *, rule_id: str = "must_have_suffix") -> ArchSelection:
        def rule(modules: list[ModuleInfo]) -> list[Violation]:
            out: list[Violation] = []
            for module in modules:
                for class_def in module.classes:
                    if not class_def.name.endswith(suffix):
                        out.append(
                            Violation(
                                rule_id,
                                module,
                                class_def.lineno,
                                f"class [{class_def.name}] does not end with [{suffix}].",
                                f"Rename it to [{class_def.name}{suffix}].",
                            )
                        )
            return out

        self._rules.append(rule)
        return self

    def must_have_prefix(self, prefix: str) -> ArchSelection:
        def rule(modules: list[ModuleInfo]) -> list[Violation]:
            out: list[Violation] = []
            for module in modules:
                for class_def in module.classes:
                    if not class_def.name.startswith(prefix):
                        out.append(
                            Violation(
                                "must_have_prefix",
                                module,
                                class_def.lineno,
                                f"class [{class_def.name}] does not start with [{prefix}].",
                                f"Rename it to [{prefix}{class_def.name}].",
                            )
                        )
            return out

        self._rules.append(rule)
        return self

    def must_have_method(self, name: str) -> ArchSelection:
        def rule(modules: list[ModuleInfo]) -> list[Violation]:
            out: list[Violation] = []
            for module in modules:
                for class_def in module.classes:
                    methods = {
                        n.name for n in class_def.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    }
                    if name not in methods:
                        out.append(
                            Violation(
                                "must_have_method",
                                module,
                                class_def.lineno,
                                f"class [{class_def.name}] has no method [{name}].",
                                f"Add a `{name}` method to [{class_def.name}].",
                            )
                        )
            return out

        self._rules.append(rule)
        return self

    def must_have_attribute(self, *names: str, rule_id: str = "must_have_attribute") -> ArchSelection:
        """Any one of `names` present satisfies the rule (OR semantics, e.g. A11's
        `__fillable__` or `__guarded__`)."""

        def rule(modules: list[ModuleInfo]) -> list[Violation]:
            out: list[Violation] = []
            for module in modules:
                for class_def in module.classes:
                    if not any(_has_class_attribute(class_def, name) for name in names):
                        label = " or ".join(names)
                        out.append(
                            Violation(
                                rule_id,
                                module,
                                class_def.lineno,
                                f"class [{class_def.name}] defines neither {label}.",
                                f"Define one of {label} on [{class_def.name}].",
                            )
                        )
            return out

        self._rules.append(rule)
        return self

    # ------------------------------------------------------------ function rules

    def must_be_async(self) -> ArchSelection:
        def rule(modules: list[ModuleInfo]) -> list[Violation]:
            out: list[Violation] = []
            for module in modules:
                for func in self._functions(module):
                    if not isinstance(func, ast.AsyncFunctionDef):
                        out.append(
                            Violation(
                                "must_be_async",
                                module,
                                func.lineno,
                                f"function [{func.name}] is not async.",
                                f"Declare it `async def {func.name}(...)`.",
                            )
                        )
            return out

        self._rules.append(rule)
        return self

    def must_have_return_annotation(self) -> ArchSelection:
        def rule(modules: list[ModuleInfo]) -> list[Violation]:
            out: list[Violation] = []
            for module in modules:
                for func in self._functions(module):
                    if func.returns is None:
                        out.append(
                            Violation(
                                "must_have_return_annotation",
                                module,
                                func.lineno,
                                f"function [{func.name}] has no return annotation.",
                                f"Annotate its return type, e.g. `def {func.name}(...) -> None:`.",
                            )
                        )
            return out

        self._rules.append(rule)
        return self

    def _functions(self, module: ModuleInfo) -> list[Any]:
        funcs: list[Any] = []
        for node in ast.walk(module.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if self._public_only and node.name.startswith("_"):
                    continue
                funcs.append(node)
        return funcs

    # ------------------------------------------------------------ running

    def _collect(self) -> list[Violation]:
        modules = self._modules()
        violations: list[Violation] = []
        for rule in self._rules:
            for violation in rule(modules):
                if not violation.module.is_ignored(violation.lineno, violation.rule):
                    violations.append(violation)
        return violations

    def check(self) -> None:
        violations = self._collect()
        if not violations:
            return
        blocks = "\n\n".join(v.format(self._base_path) for v in violations)
        raise ArchitectureViolation(f"{blocks}\n\n{len(violations)} architecture rule(s) failed.")


def _has_class_attribute(class_def: ast.ClassDef, name: str) -> bool:
    for node in class_def.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return True
    return False


def arch(*packages: str) -> ArchSelection:
    """`arch("app.models").must_not_import("fastapi").check()` (T-58)."""
    from aso.foundation.paths import base_path

    return ArchSelection(base_path(), packages)
