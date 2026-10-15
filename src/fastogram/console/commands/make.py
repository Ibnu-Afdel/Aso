"""Code generators (T-51): every `make:*` command plus `stub:publish`.

Each `generate_*()` function is the pure part: it derives names from the argument, builds the
file's content, and writes it (atomically: a temp file, then `os.replace` via `Path.replace`).
The `Command` subclasses below are thin wrappers that parse flags and print the created path(s).

Stubs live in `src/fastogram/console/stubs/*.stub` and are rendered with Jinja2 (`render_stub`):
each one is a template containing a single `{{ content }}` placeholder, so `stub:publish`-ed app
stubs (`<project>/stubs/*.stub`) can wrap the framework-derived content in whatever boilerplate an
app wants, while every naming/branching decision still happens here in Python (T-51 "How it
works": "the command derives the names ... renders the stub").
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastogram.console.command import Command
from fastogram.console.registry import register

STUBS_DIR = Path(__file__).resolve().parent.parent / "stubs"

_SNAKE_RE = re.compile(r"(?<!^)(?=[A-Z])")


def to_snake(name: str) -> str:
    """`PostController` -> `post_controller` (D-013)."""
    return _SNAKE_RE.sub("_", name).lower()


def to_pascal(name: str) -> str:
    """`created_by` -> `CreatedBy`, `user` -> `User`."""
    return "".join(part[:1].upper() + part[1:] for part in re.split(r"[_\s]+", name) if part)


def table_name_for(class_name: str) -> str:
    from fastogram.database.model import table_name_for as _table_name_for

    return _table_name_for(class_name)


def _paths() -> Any:
    from fastogram.foundation import paths

    return paths


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(_paths().base_path()))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------- stub rendering (T-51 "stub:publish")


def _stub_text(relative: str) -> str:
    """App stubs (`<project>/stubs/<relative>`) take priority over the bundled ones."""
    app_stub = _paths().base_path("stubs", relative)
    if app_stub.is_file():
        return app_stub.read_text()
    bundled = STUBS_DIR / relative
    if not bundled.is_file():
        raise RuntimeError(f'No bundled stub named "{relative}".')
    return bundled.read_text()


def render_stub(relative: str, context: dict[str, Any]) -> str:
    from jinja2 import Template

    return Template(_stub_text(relative)).render(**context)


# ---------------------------------------------------------------- writing files


def _write_file(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{_relative(path)} already exists. Use --force to overwrite.")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp"
    tmp.write_text(content)
    tmp.replace(path)


def _format_python(path: Path) -> None:
    """`ruff format` + sort imports, when Ruff is installed (T-51 "How it works")."""
    ruff = shutil.which("ruff")
    if not ruff:
        return
    subprocess.run([ruff, "format", "--quiet", str(path)], check=False, capture_output=True)
    subprocess.run([ruff, "check", "--quiet", "--fix", "--select", "I,F401", str(path)], check=False, capture_output=True)


def _write_python_file(path: Path, content: str, *, force: bool) -> None:
    _write_file(path, content, force=force)
    _format_python(path)


def _finish(cmd: Command, fn: Any) -> int:
    try:
        result = fn()
    except (FileExistsError, ValueError, RuntimeError) as exc:
        cmd.error(str(exc))
        return 1
    paths = result if isinstance(result, list) else [result]
    for path in paths:
        cmd.info(f"Created: {_relative(path)}")
    return 0


# ---------------------------------------------------------------- make:request


def generate_request(class_name: str, *, force: bool) -> Path:
    path = _paths().app_path("http", "requests", f"{to_snake(class_name)}.py")
    content = (
        "from pydantic import Field\n"
        "from fastogram.http import FormRequest\n\n\n"
        f"class {class_name}(FormRequest):\n"
        "    # Declare each field with its type and constraints (T-19).\n"
        "    title: str = Field(max_length=255)\n"
    )
    _write_python_file(path, render_stub("request.stub", {"content": content}), force=force)
    return path


class MakeRequestCommand(Command):
    signature = "make:request {name : e.g. StorePostRequest} {--force : Overwrite an existing file}"
    description = "Create a new form request class"

    async def handle(self) -> int:
        name, force = self.argument("name"), bool(self.option("force"))
        return _finish(self, lambda: generate_request(name, force=force))


# ---------------------------------------------------------------- make:middleware


def generate_middleware(class_name: str, *, force: bool) -> Path:
    path = _paths().app_path("http", "middleware", f"{to_snake(class_name)}.py")
    content = (
        "from fastogram.http import Middleware, Next, Request, Response\n\n\n"
        f"class {class_name}(Middleware):\n"
        "    async def handle(self, request: Request, next: Next) -> Response:\n"
        "        return await next(request)\n"
    )
    _write_python_file(path, render_stub("middleware.stub", {"content": content}), force=force)
    return path


class MakeMiddlewareCommand(Command):
    signature = "make:middleware {name : e.g. EnsureUserIsSubscribed} {--force : Overwrite an existing file}"
    description = "Create a new middleware class"

    async def handle(self) -> int:
        name, force = self.argument("name"), bool(self.option("force"))
        return _finish(self, lambda: generate_middleware(name, force=force))


# ---------------------------------------------------------------- make:page


def generate_page(path_arg: str, *, force: bool) -> Path:
    page_path = path_arg.strip("/").lower()
    file_path = _paths().resource_path("js", "pages", f"{page_path}.tsx")
    component_name = to_pascal(Path(page_path).name)
    content = (
        'import { Head } from "@inertiajs/react";\n\n'
        "type Props = {\n"
        f'    // the props your controller passes to inertia("{page_path}", {{...}})\n'
        "};\n\n"
        f"export default function {component_name}({{}}: Props) {{\n"
        "    return (\n"
        "        <>\n"
        f'            <Head title="{component_name}" />\n'
        f'            <div className="p-4">{page_path}</div>\n'
        "        </>\n"
        "    );\n"
        "}\n"
    )
    _write_file(file_path, render_stub("page.stub", {"content": content}), force=force)
    return file_path


class MakePageCommand(Command):
    signature = "make:page {path : e.g. posts/index} {--force : Overwrite an existing file}"
    description = "Create a new Inertia page component"

    async def handle(self) -> int:
        path_arg, force = self.argument("path"), bool(self.option("force"))
        return _finish(self, lambda: generate_page(path_arg, force=force))


# ---------------------------------------------------------------- make:factory


def generate_factory(class_name: str, *, model_name: str | None, force: bool) -> Path:
    model_name = model_name or (class_name.removesuffix("Factory") if class_name.endswith("Factory") else class_name)
    model_snake = to_snake(model_name)
    path = _paths().database_path("factories", f"{to_snake(class_name)}.py")
    content = (
        "from fastogram.database import Factory\n"
        f"from app.models.{model_snake} import {model_name}\n\n\n"
        f"class {class_name}(Factory):\n"
        f"    model = {model_name}\n\n"
        "    def definition(self) -> dict:\n"
        "        return {\n"
        '            "title": self.faker.sentence(),\n'
        '            "body": self.faker.paragraph(),\n'
        "        }\n"
    )
    _write_python_file(path, render_stub("factory.stub", {"content": content}), force=force)
    return path


class MakeFactoryCommand(Command):
    signature = "make:factory {name : e.g. PostFactory} {--model= : The model this factory builds} {--force : Overwrite an existing file}"
    description = "Create a new model factory"

    async def handle(self) -> int:
        name, model_name, force = self.argument("name"), self.option("model"), bool(self.option("force"))
        return _finish(self, lambda: generate_factory(name, model_name=model_name, force=force))


# ---------------------------------------------------------------- make:seeder


def generate_seeder(class_name: str, *, force: bool) -> Path:
    path = _paths().database_path("seeders", f"{to_snake(class_name)}.py")
    base_name = class_name.removesuffix("Seeder") if class_name.endswith("Seeder") else class_name
    model_snake = to_snake(base_name)
    factory_class = f"{base_name}Factory"
    content = (
        "from fastogram.database import Seeder\n"
        f"from database.factories.{model_snake}_factory import {factory_class}\n\n\n"
        f"class {class_name}(Seeder):\n"
        "    async def run(self) -> None:\n"
        f"        await {factory_class}.new().count(10).create()\n"
    )
    _write_python_file(path, render_stub("seeder.stub", {"content": content}), force=force)
    return path


class MakeSeederCommand(Command):
    signature = "make:seeder {name : e.g. PostSeeder} {--force : Overwrite an existing file}"
    description = "Create a new seeder class"

    async def handle(self) -> int:
        name, force = self.argument("name"), bool(self.option("force"))
        return _finish(self, lambda: generate_seeder(name, force=force))


# ---------------------------------------------------------------- make:policy


def generate_policy(class_name: str, *, model_name: str | None, force: bool) -> Path:
    model_name = model_name or (class_name.removesuffix("Policy") if class_name.endswith("Policy") else class_name)
    model_snake = to_snake(model_name)
    path = _paths().app_path("policies", f"{to_snake(class_name)}.py")
    content = (
        f"from app.models.{model_snake} import {model_name}\n"
        "from app.models.user import User\n\n\n"
        f"class {class_name}:\n"
        f"    async def update(self, user: User, {model_snake}: {model_name}) -> bool:\n"
        f"        return user.id == {model_snake}.user_id\n\n"
        f"    async def delete(self, user: User, {model_snake}: {model_name}) -> bool:\n"
        f"        return user.id == {model_snake}.user_id\n"
    )
    _write_python_file(path, render_stub("policy.stub", {"content": content}), force=force)
    return path


class MakePolicyCommand(Command):
    signature = "make:policy {name : e.g. PostPolicy} {--model= : The model this policy guards} {--force : Overwrite an existing file}"
    description = "Create a new policy class"

    async def handle(self) -> int:
        name, model_name, force = self.argument("name"), self.option("model"), bool(self.option("force"))
        return _finish(self, lambda: generate_policy(name, model_name=model_name, force=force))


# ---------------------------------------------------------------- make:job


def generate_job(class_name: str, *, force: bool) -> Path:
    path = _paths().app_path("jobs", f"{to_snake(class_name)}.py")
    content = (
        "from fastogram.queue import Job\n\n\n"
        f"class {class_name}(Job):\n"
        "    tries = 1\n"
        "    after_commit = True\n\n"
        "    def __init__(self, user_id: int) -> None:\n"
        "        self.user_id = user_id\n\n"
        "    async def handle(self) -> None:\n"
        "        ...\n"
    )
    _write_python_file(path, render_stub("job.stub", {"content": content}), force=force)
    return path


class MakeJobCommand(Command):
    signature = "make:job {name : e.g. SendWelcomeEmail} {--force : Overwrite an existing file}"
    description = "Create a new job class"

    async def handle(self) -> int:
        name, force = self.argument("name"), bool(self.option("force"))
        return _finish(self, lambda: generate_job(name, force=force))


# ---------------------------------------------------------------- make:event / make:listener


def generate_event(class_name: str, *, force: bool) -> Path:
    path = _paths().app_path("events", f"{to_snake(class_name)}.py")
    content = (
        "from fastogram.events import Event\n\n\n" f"class {class_name}(Event):\n" "    def __init__(self) -> None:\n" "        ...\n"
    )
    _write_python_file(path, render_stub("event.stub", {"content": content}), force=force)
    return path


class MakeEventCommand(Command):
    signature = "make:event {name : e.g. OrderShipped} {--force : Overwrite an existing file}"
    description = "Create a new event class"

    async def handle(self) -> int:
        name, force = self.argument("name"), bool(self.option("force"))
        return _finish(self, lambda: generate_event(name, force=force))


def generate_listener(class_name: str, *, event_name: str | None, queued: bool, force: bool) -> Path:
    path = _paths().app_path("listeners", f"{to_snake(class_name)}.py")
    if event_name:
        event_snake = to_snake(event_name)
        header = f"from app.events.{event_snake} import {event_name}\n\n\n"
        event_type = event_name
    else:
        header = "from typing import Any\n\n\n"
        event_type = "Any"
    queued_line = "    queued = True\n\n" if queued else ""
    content = f"{header}" f"class {class_name}:\n" f"{queued_line}" f"    async def handle(self, event: {event_type}) -> None:\n" "        ...\n"
    _write_python_file(path, render_stub("listener.stub", {"content": content}), force=force)
    return path


class MakeListenerCommand(Command):
    signature = (
        "make:listener {name : e.g. SendShipmentNotification} "
        "{--event= : The event class this listener handles} "
        "{--queued : Add queued = True} "
        "{--force : Overwrite an existing file}"
    )
    description = "Create a new event listener class"

    async def handle(self) -> int:
        name = self.argument("name")
        event_name, queued, force = self.option("event"), bool(self.option("queued")), bool(self.option("force"))
        return _finish(self, lambda: generate_listener(name, event_name=event_name, queued=queued, force=force))


# ---------------------------------------------------------------- make:mail


def generate_mail(class_name: str, *, force: bool) -> list[Path]:
    py_path = _paths().app_path("mail", f"{to_snake(class_name)}.py")
    view_relative = f"mail/{to_snake(class_name)}.html"
    view_path = _paths().resource_path("views", view_relative)
    words = re.findall(r"[A-Z][a-z0-9]*|[A-Z]+(?![a-z])", class_name) or [class_name]
    subject = " ".join(words)
    content = (
        "from fastogram.mail import Content, Envelope, Mailable\n\n\n"
        f"class {class_name}(Mailable):\n"
        "    def envelope(self) -> Envelope:\n"
        f'        return Envelope(subject="{subject}")\n\n'
        "    def content(self) -> Content:\n"
        f'        return Content(view="{view_relative}")\n'
    )
    _write_python_file(py_path, render_stub("mail.stub", {"content": content}), force=force)
    view_content = render_stub("mail_view.stub", {"content": f"<p>{subject}</p>\n"})
    _write_file(view_path, view_content, force=force)
    return [py_path, view_path]


class MakeMailCommand(Command):
    signature = "make:mail {name : e.g. WelcomeMail} {--force : Overwrite an existing file}"
    description = "Create a new mailable class"

    async def handle(self) -> int:
        name, force = self.argument("name"), bool(self.option("force"))
        return _finish(self, lambda: generate_mail(name, force=force))


# ---------------------------------------------------------------- make:command


def generate_console_command(class_name: str, *, force: bool) -> Path:
    path = _paths().app_path("console", "commands", f"{to_snake(class_name)}.py")
    signature_name = to_snake(class_name).replace("_", "-")
    content = (
        "from fastogram.console import Command\n\n\n"
        f"class {class_name}(Command):\n"
        f'    signature = "app:{signature_name}"\n'
        '    description = "Command description"\n\n'
        "    async def handle(self) -> int:\n"
        "        return 0\n"
    )
    _write_python_file(path, render_stub("command.stub", {"content": content}), force=force)
    return path


class MakeCommandCommand(Command):
    signature = "make:command {name : e.g. SendReport} {--force : Overwrite an existing file}"
    description = "Create a new console command"

    async def handle(self) -> int:
        name, force = self.argument("name"), bool(self.option("force"))
        return _finish(self, lambda: generate_console_command(name, force=force))


# ---------------------------------------------------------------- make:test


def generate_test(class_name: str, *, unit: bool, force: bool) -> Path:
    base_name = class_name.removesuffix("Test") if class_name.endswith("Test") else class_name
    directory = "unit" if unit else "feature"
    path = _paths().base_path("tests", directory, f"test_{to_snake(base_name)}.py")
    content = (
        "from fastogram.testing import TestClient\n\n\n"
        "async def test_example(client: TestClient) -> None:\n"
        '    response = await client.get("/")\n'
        "    response.assert_ok()\n"
    )
    _write_python_file(path, render_stub("test.stub", {"content": content}), force=force)
    return path


class MakeTestCommand(Command):
    signature = "make:test {name : e.g. PostTest} {--unit : Put it in tests/unit instead of tests/feature} {--force : Overwrite an existing file}"
    description = "Create a new test file"

    async def handle(self) -> int:
        name, unit, force = self.argument("name"), bool(self.option("unit")), bool(self.option("force"))
        return _finish(self, lambda: generate_test(name, unit=unit, force=force))


# ---------------------------------------------------------------- make:controller


def generate_controller(
    class_name: str,
    *,
    resource: bool,
    api: bool,
    invokable: bool,
    model_name: str | None,
    use_requests: bool,
    force: bool,
) -> list[Path]:
    base_name = class_name.removesuffix("Controller") if class_name.endswith("Controller") else class_name
    page_prefix = table_name_for(base_name)
    route_prefix = page_prefix
    created: list[Path] = []

    store_request_class = f"Store{base_name}Request"
    update_request_class = f"Update{base_name}Request"
    if use_requests:
        created.append(generate_request(store_request_class, force=force))
        created.append(generate_request(update_request_class, force=force))

    want_methods = resource or api
    imports = ["from fastogram.http import Controller"]
    bodies: list[str] = []

    if invokable:
        imports[0] += ", Request, Response"
        bodies.append("async def __call__(self, request: Request) -> Response:\n    ...")
    elif want_methods:
        imports[0] += ", redirect"
        imports.append("from fastogram.inertia import inertia")
        model_snake = to_snake(model_name) if model_name else None
        if model_name:
            imports.append(f"from app.models.{model_snake} import {model_name}")
        if use_requests:
            imports.append(f"from app.http.requests.{to_snake(store_request_class)} import {store_request_class}")
            imports.append(f"from app.http.requests.{to_snake(update_request_class)} import {update_request_class}")

        param_name = model_snake or "id"
        param_type = model_name or "int"
        fetch_expr = f"await {model_name}.latest().paginate(15)" if model_name else "[]"

        bodies.append(f'async def index(self):\n    return inertia("{page_prefix}/index", {{"{page_prefix}": {fetch_expr}}})')
        if not api:
            bodies.append(f'async def create(self):\n    return inertia("{page_prefix}/create")')
        store_param = f"request: {store_request_class}" if use_requests else "request"
        bodies.append(
            f"async def store(self, {store_param}):\n    ...\n"
            f'    return redirect().route("{route_prefix}.index").with_flash("success", "Created.")'
        )
        bodies.append(
            f'async def show(self, {param_name}: {param_type}):\n'
            f'    return inertia("{page_prefix}/show", {{"{param_name}": {param_name}}})'
        )
        if not api:
            bodies.append(
                f'async def edit(self, {param_name}: {param_type}):\n'
                f'    return inertia("{page_prefix}/edit", {{"{param_name}": {param_name}}})'
            )
        update_param = f"request: {update_request_class}" if use_requests else "request"
        bodies.append(
            f"async def update(self, {update_param}, {param_name}: {param_type}):\n    ...\n"
            f'    return redirect().route("{route_prefix}.index").with_flash("success", "Updated.")'
        )
        destroy_delete = f"    await {param_name}.delete()\n" if model_name else ""
        bodies.append(
            f"async def destroy(self, {param_name}: {param_type}):\n"
            f"{destroy_delete}"
            f'    return redirect().route("{route_prefix}.index").with_flash("success", "Deleted.")'
        )
    else:
        bodies.append("pass")

    indented = ["\n".join((f"    {line}" if line else "") for line in block.split("\n")) for block in bodies]
    content = "\n".join(imports) + "\n\n\n" + f"class {class_name}(Controller):\n" + "\n\n".join(indented) + "\n"

    path = _paths().app_path("http", "controllers", f"{to_snake(class_name)}.py")
    _write_python_file(path, render_stub("controller.stub", {"content": content}), force=force)
    created.append(path)
    return created


class MakeControllerCommand(Command):
    signature = (
        "make:controller {name : e.g. PostController} "
        "{--resource : Generate the seven resource methods} "
        "{--model= : Type the methods for route-model binding} "
        "{--requests : Also generate Store/Update form requests} "
        "{--api : Like --resource without create/edit} "
        "{--invokable : A single-action controller} "
        "{--force : Overwrite an existing file}"
    )
    description = "Create a new controller class"

    async def handle(self) -> int:
        name = self.argument("name")
        return _finish(
            self,
            lambda: generate_controller(
                name,
                resource=bool(self.option("resource")),
                api=bool(self.option("api")),
                invokable=bool(self.option("invokable")),
                model_name=self.option("model"),
                use_requests=bool(self.option("requests")),
                force=bool(self.option("force")),
            ),
        )


# ---------------------------------------------------------------- make:model


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str
    nullable: bool
    unique: bool
    index: bool


_FIELD_TYPES = {"string", "text", "integer", "big_integer", "boolean", "decimal", "date", "datetime", "json", "uuid", "foreign"}


def parse_fields(spec: str) -> list[FieldSpec]:
    """`"title:string body:text user:foreign"` -> `FieldSpec`s (T-31/T-51 `--fields` syntax)."""
    fields: list[FieldSpec] = []
    for token in spec.split():
        parts = token.split(":")
        if len(parts) < 2:
            raise ValueError(f'Invalid field "{token}": expected "name:type".')
        name, type_part, *modifiers = parts
        nullable = type_part.endswith("?")
        type_name = type_part.rstrip("?")
        if type_name not in _FIELD_TYPES:
            raise ValueError(f'Unknown field type "{type_name}" in "{token}".')
        fields.append(FieldSpec(name, type_name, nullable, "unique" in modifiers, "index" in modifiers))
    return fields


@dataclass
class _ColumnReqs:
    sa_types: set[str] = field(default_factory=set)
    datetime_names: set[str] = field(default_factory=set)
    needs_uuid: bool = False
    needs_any: bool = False
    needs_decimal: bool = False


def _column_line(spec: FieldSpec) -> tuple[str, _ColumnReqs]:
    reqs = _ColumnReqs()
    opt = " | None" if spec.nullable else ""
    kwargs = [*(["unique=True"] if spec.unique else []), *(["index=True"] if spec.index else [])]

    if spec.type == "string":
        reqs.sa_types.add("String")
        return f"{spec.name}: Mapped[str{opt}] = mapped_column({', '.join(['String(255)', *kwargs])})", reqs
    if spec.type == "text":
        reqs.sa_types.add("Text")
        return f"{spec.name}: Mapped[str{opt}] = mapped_column({', '.join(['Text', *kwargs])})", reqs
    if spec.type == "decimal":
        reqs.sa_types.add("Numeric")
        reqs.needs_decimal = True
        return f"{spec.name}: Mapped[Decimal{opt}] = mapped_column({', '.join(['Numeric(10, 2)', *kwargs])})", reqs
    if spec.type == "boolean":
        reqs.sa_types.add("Boolean")
        bool_kwargs = [*kwargs, *([] if spec.nullable else ["default=False"])]
        return f"{spec.name}: Mapped[bool{opt}] = mapped_column({', '.join(['Boolean', *bool_kwargs])})", reqs
    if spec.type == "json":
        reqs.sa_types.add("JSON")
        reqs.needs_any = True
        return f"{spec.name}: Mapped[Any{opt}] = mapped_column({', '.join(['JSON', *kwargs])})", reqs
    if spec.type == "uuid":
        reqs.sa_types.add("Uuid")
        reqs.needs_uuid = True
        return f"{spec.name}: Mapped[uuid.UUID{opt}] = mapped_column({', '.join(['Uuid', *kwargs])})", reqs

    py_type, sa_ctor = {"integer": ("int", "Integer"), "big_integer": ("int", "BigInteger"), "date": ("date", "Date"), "datetime": ("datetime", "DateTime(timezone=True)")}[
        spec.type
    ]
    if spec.type == "date":
        reqs.datetime_names.add("date")
    if spec.type == "datetime":
        reqs.datetime_names.add("datetime")
    if kwargs:
        reqs.sa_types.add(sa_ctor.split("(")[0])
        return f"{spec.name}: Mapped[{py_type}{opt}] = mapped_column({', '.join([sa_ctor, *kwargs])})", reqs
    return f"{spec.name}: Mapped[{py_type}{opt}]", reqs


def _foreign_lines(spec: FieldSpec) -> tuple[str, str]:
    pascal = to_pascal(spec.name)
    table = table_name_for(pascal)
    opt = " | None" if spec.nullable else ""
    column = f'{spec.name}_id: Mapped[int{opt}] = mapped_column(ForeignKey("{table}.id"))'
    relation = f'{spec.name}: Mapped["{pascal}"] = belongs_to("{pascal}")'
    return column, relation


def _model_content(class_name: str, fields: list[FieldSpec]) -> str:
    sa_types: set[str] = set()
    datetime_names: set[str] = set()
    needs_uuid = needs_any = needs_decimal = False
    column_lines: list[str] = []
    relation_lines: list[str] = []
    fillable: list[str] = []
    related_models: set[str] = set()

    for spec in fields:
        if spec.type == "foreign":
            column, relation = _foreign_lines(spec)
            column_lines.append(column)
            relation_lines.append(relation)
            sa_types.add("ForeignKey")
            related_models.add(to_pascal(spec.name))
            continue
        fillable.append(spec.name)
        line, reqs = _column_line(spec)
        column_lines.append(line)
        sa_types |= reqs.sa_types
        datetime_names |= reqs.datetime_names
        needs_uuid = needs_uuid or reqs.needs_uuid
        needs_any = needs_any or reqs.needs_any
        needs_decimal = needs_decimal or reqs.needs_decimal

    imports: list[str] = []
    if needs_uuid:
        imports.append("import uuid")
    if datetime_names:
        imports.append(f"from datetime import {', '.join(sorted(datetime_names))}")
    if needs_decimal:
        imports.append("from decimal import Decimal")
    if needs_any:
        imports.append("from typing import Any")
    if sa_types:
        imports.append(f"from sqlalchemy import {', '.join(sorted(sa_types))}")
    db_names = {"Mapped", "Model", "mapped_column"}
    if relation_lines:
        db_names.add("belongs_to")
    imports.append(f"from fastogram.database import {', '.join(sorted(db_names))}")
    if related_models:
        # `Mapped["User"]` is a forward-ref string SQLAlchemy resolves at mapper-configuration
        # time; this `TYPE_CHECKING` import is only so static checkers (ruff's F821) see it too.
        imports.append("from typing import TYPE_CHECKING")
        guarded = "\n".join(f"    from app.models.{to_snake(name)} import {name}" for name in sorted(related_models))
        imports.append(f"if TYPE_CHECKING:\n{guarded}")

    # Always declared, even empty: A11 (T-58) requires every model to define `__fillable__` or
    # `__guarded__`, and a model generated with no plain fields yet (or fields that are all
    # `foreign`) would otherwise have neither.
    fillable_repr = ", ".join(f'"{n}"' for n in fillable)
    fillable_block = f"    __fillable__ = [{fillable_repr}]\n\n"

    if column_lines or relation_lines:
        body = "\n".join(f"    {line}" for line in column_lines)
        if relation_lines:
            body += "\n\n" + "\n".join(f"    {line}" for line in relation_lines)
    else:
        body = "    pass"

    return "\n".join(imports) + "\n\n\n" + f"class {class_name}(Model):\n" + fillable_block + body + "\n"


async def generate_model(
    class_name: str,
    *,
    migration: bool,
    controller: bool,
    resource: bool,
    factory: bool,
    seeder: bool,
    policy: bool,
    requests_flag: bool,
    fields_spec: str,
    force: bool,
) -> list[Path]:
    fields = parse_fields(fields_spec) if fields_spec else []
    content = _model_content(class_name, fields)
    path = _paths().app_path("models", f"{to_snake(class_name)}.py")
    _write_python_file(path, render_stub("model.stub", {"content": content}), force=force)
    created: list[Path] = [path]

    if migration:
        from fastogram.console import migrations as migrations_module

        page_prefix = table_name_for(class_name)
        created.append(await migrations_module.make_migration(f"create {page_prefix} table", base_path=_paths().base_path()))
    if factory:
        created.append(generate_factory(f"{class_name}Factory", model_name=class_name, force=force))
    if seeder:
        created.append(generate_seeder(f"{class_name}Seeder", force=force))
    if policy:
        created.append(generate_policy(f"{class_name}Policy", model_name=class_name, force=force))
    if controller or resource:
        created.extend(
            generate_controller(
                f"{class_name}Controller",
                resource=resource,
                api=False,
                invokable=False,
                model_name=class_name,
                use_requests=requests_flag,
                force=force,
            )
        )
    return created


class MakeModelCommand(Command):
    signature = (
        "make:model {name : e.g. Post} "
        "{--m|migration : Also create a migration} "
        "{--c|controller : Also create a controller} "
        "{--r|resource : Make that controller a resource controller} "
        "{--f|factory : Also create a factory} "
        "{--s|seeder : Also create a seeder} "
        '{--a|all : Everything: migration, factory, seeder, policy, resource controller and form requests} '
        '{--fields= : name:type[:modifier] pairs, e.g. "title:string body:text user:foreign"} '
        "{--force : Overwrite existing files}"
    )
    description = "Create a new model class"

    async def handle(self) -> int:
        class_name = self.argument("name")
        all_flag = bool(self.option("all"))
        force = bool(self.option("force"))
        try:
            created = await generate_model(
                class_name,
                migration=all_flag or bool(self.option("migration")),
                controller=all_flag or bool(self.option("controller")),
                resource=all_flag or bool(self.option("resource")),
                factory=all_flag or bool(self.option("factory")),
                seeder=all_flag or bool(self.option("seeder")),
                policy=all_flag,
                requests_flag=all_flag,
                fields_spec=self.option("fields") or "",
                force=force,
            )
        except (FileExistsError, ValueError, RuntimeError) as exc:
            self.error(str(exc))
            return 1
        for created_path in created:
            self.info(f"Created: {_relative(created_path)}")
        return 0


# ---------------------------------------------------------------- stub:publish


class StubPublishCommand(Command):
    signature = "stub:publish {--force : Overwrite stubs already published}"
    description = "Publish all stubs for customization"

    async def handle(self) -> int:
        target_dir = _paths().base_path("stubs")
        target_dir.mkdir(parents=True, exist_ok=True)
        force = bool(self.option("force"))
        for stub_file in sorted(STUBS_DIR.glob("*.stub")):
            target = target_dir / stub_file.name
            if target.exists() and not force:
                self.comment(f"Skipped (already exists): stubs/{stub_file.name}")
                continue
            target.write_text(stub_file.read_text())
            self.info(f"Published: stubs/{stub_file.name}")
        return 0


def register_all() -> None:
    for cls in (
        MakeControllerCommand,
        MakeModelCommand,
        MakeRequestCommand,
        MakeMiddlewareCommand,
        MakePageCommand,
        MakeFactoryCommand,
        MakeSeederCommand,
        MakePolicyCommand,
        MakeJobCommand,
        MakeEventCommand,
        MakeListenerCommand,
        MakeMailCommand,
        MakeCommandCommand,
        MakeTestCommand,
        StubPublishCommand,
    ):
        register(cls, source="framework")
