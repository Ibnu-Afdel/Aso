"""Laravel `signature` string parsing (D-029, T-50).

`"report:send {user_id} {--queue : Dispatch as a background job}"` -> a command name plus
`ArgumentSpec`/`OptionSpec` lists. This is the *only* way `Command` subclasses declare input;
the parsed result drives both `self.argument()`/`self.option()` lookups at runtime and the
dynamic Click parameters the CLI builds for `--help` (T-50 "How it works").

Grammar (Laravel's artisan signature syntax):
    {arg}            required argument
    {arg?}           optional argument
    {arg=default}    optional argument with a default
    {arg*}           array argument (zero or more values)
    {arg?*}          optional array argument
    {--flag}         boolean option (`--flag`)
    {--opt=}         value option, no default (`--opt=value`)
    {--opt=default}  value option with a default
    {--opt=*}        array option (repeatable, `--opt=a --opt=b`)
    {--Q|queue}      a shortcut (`-Q`) for `--queue`
    {arg : text}     inline description (shown in `--help`)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_TOKEN_RE = re.compile(r"\{([^}]*)\}")


@dataclass(frozen=True)
class ArgumentSpec:
    name: str
    optional: bool = False
    is_list: bool = False
    default: str | None = None
    description: str = ""


@dataclass(frozen=True)
class OptionSpec:
    name: str
    shortcut: str | None = None
    kind: str = "flag"  # "flag" | "value" | "list"
    default: object = None
    description: str = ""


@dataclass(frozen=True)
class ParsedSignature:
    name: str
    arguments: list[ArgumentSpec] = field(default_factory=list)
    options: list[OptionSpec] = field(default_factory=list)

    def argument(self, name: str) -> ArgumentSpec | None:
        return next((a for a in self.arguments if a.name == name), None)

    def option(self, name: str) -> OptionSpec | None:
        return next((o for o in self.options if o.name == name), None)


def parse_signature(signature: str) -> ParsedSignature:
    signature = signature.strip()
    brace = signature.find("{")
    if brace == -1:
        return ParsedSignature(name=signature.strip())
    name = signature[:brace].strip()
    arguments: list[ArgumentSpec] = []
    options: list[OptionSpec] = []
    for raw in _TOKEN_RE.findall(signature[brace:]):
        spec_part, description = _split_description(raw)
        if spec_part.startswith("--"):
            options.append(_parse_option(spec_part[2:], description))
        else:
            arguments.append(_parse_argument(spec_part, description))
    return ParsedSignature(name=name, arguments=arguments, options=options)


def _split_description(token: str) -> tuple[str, str]:
    if " : " in token:
        spec_part, _, description = token.partition(" : ")
        return spec_part.strip(), description.strip()
    return token.strip(), ""


def _parse_option(body: str, description: str) -> OptionSpec:
    shortcut: str | None = None
    if "|" in body:
        shortcut, _, body = body.partition("|")
        shortcut = shortcut.strip() or None
    if "=" in body:
        opt_name, _, default_part = body.partition("=")
        opt_name = opt_name.strip()
        if default_part == "*":
            return OptionSpec(opt_name, shortcut, "list", [], description)
        if default_part == "":
            return OptionSpec(opt_name, shortcut, "value", None, description)
        return OptionSpec(opt_name, shortcut, "value", default_part, description)
    return OptionSpec(body.strip(), shortcut, "flag", False, description)


def _parse_argument(body: str, description: str) -> ArgumentSpec:
    is_list = False
    if body.endswith("*"):
        is_list = True
        body = body[:-1]
    optional = False
    default: str | None = None
    if body.endswith("?"):
        optional = True
        body = body[:-1]
    elif "=" in body:
        body, _, default = body.partition("=")
        optional = True
    return ArgumentSpec(body.strip(), optional, is_list, default, description)
