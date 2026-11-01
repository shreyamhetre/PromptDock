"""Export prompts to YAML files and push edited files back as new versions.

One file per prompt (``<name>.yaml``) holds the **latest version** and, for reference, the
tag mapping at export time. Full history stays in the database.

``push`` never overwrites anything: it creates a new version only when a file's template
or model_config differs from the latest version, and moves no tags unless asked
(``tag=...``). It can never move ``prod``.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from promptdock.client import Client
from promptdock.core.service import compute_content_hash
from promptdock.errors import InvalidInputError, NotFoundError, PromptDockError
from promptdock.models import PromptVersionCreate

PUSH_NEVER_MOVES = "prod"
_HEADER = (
    "# Exported by PromptDock. Edit template / model_config, then run `promptdock push`.\n"
    "# `version` is the version this file was exported from; `tags` is for reference only.\n"
)


@dataclass
class PromptFile:
    name: str
    template: Any
    model_config: dict[str, Any] = field(default_factory=dict)
    description: str | None = None
    version: int | None = None
    tags: dict[str, int | None] = field(default_factory=dict)


@dataclass
class PushResult:
    name: str
    status: Literal["created", "new_version", "unchanged", "error"]
    version: int | None = None
    tag_moved: str | None = None
    warning: str | None = None
    error: str | None = None


# --- YAML ------------------------------------------------------------------------------


class _Dumper(yaml.SafeDumper):
    pass


def _str_representer(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _str_representer)


def dump_prompt_file(prompt: PromptFile) -> str:
    data: dict[str, Any] = {
        "name": prompt.name,
        "description": prompt.description,
        "version": prompt.version,
        "template": prompt.template,
        "model_config": prompt.model_config,
        "tags": prompt.tags,
    }
    body = yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=100)
    return _HEADER + body


def load_prompt_file(path: Path) -> PromptFile:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise InvalidInputError(f"{path.name}: not valid YAML: {exc}") from None
    if not isinstance(data, dict) or "template" not in data:
        raise InvalidInputError(f"{path.name}: expected a mapping with a 'template' key")
    tags = data.get("tags") or {}
    return PromptFile(
        name=str(data.get("name") or path.stem),
        template=data["template"],
        model_config=dict(data.get("model_config") or {}),
        description=data.get("description"),
        version=data.get("version"),
        tags=dict(tags) if isinstance(tags, dict) else {},
    )


def _prompt_files(directory: Path) -> list[Path]:
    return sorted([*directory.glob("*.yaml"), *directory.glob("*.yml")])


# --- export / push ---------------------------------------------------------------------


def export_prompts(
    client: Client, directory: str | Path, names: list[str] | None = None
) -> list[Path]:
    """Write ``<name>.yaml`` for each prompt (all prompts by default). Prompts without any
    version are skipped. Returns the files written."""
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in names or [p.name for p in client.list_prompts()]:
        info = client.get_prompt_info(name)
        try:
            latest = client.get_version(name)
        except NotFoundError:
            continue
        tags = {t.name: t.version for t in client.list_tags(name)}
        source = latest.template
        template: Any = source if isinstance(source, str) else [m.model_dump() for m in source]
        path = out / f"{name}.yaml"
        path.write_text(
            dump_prompt_file(
                PromptFile(
                    name=name,
                    template=template,
                    model_config=latest.llm_config,
                    description=info.description,
                    version=latest.version,
                    tags=tags,
                )
            ),
            encoding="utf-8",
            newline="\n",
        )
        written.append(path)
    return written


def push_prompts(
    client: Client,
    directory: str | Path,
    *,
    tag: str | None = None,
    message: str | None = None,
    dry_run: bool = False,
) -> list[PushResult]:
    """Create a new version for every file whose content differs from the latest version.

    New prompts are created. With ``tag``, that tag is moved to each new version (never
    ``prod``). One file failing does not stop the others.
    """
    if tag == PUSH_NEVER_MOVES:
        raise InvalidInputError(
            "push can never move 'prod'; promote to prod explicitly with `promptdock promote`"
        )
    folder = Path(directory)
    if not folder.is_dir():
        raise InvalidInputError(f"{folder} is not a directory")
    return [_push_one(client, path, tag, message, dry_run) for path in _prompt_files(folder)]


def _push_one(
    client: Client, path: Path, tag: str | None, message: str | None, dry_run: bool
) -> PushResult:
    name = path.stem
    try:
        prompt_file = load_prompt_file(path)
        name = prompt_file.name
        data = PromptVersionCreate.model_validate(
            {
                "template": prompt_file.template,
                "model_config": prompt_file.model_config,
                "commit_message": message or f"push {path.name}",
            }
        )

        try:
            latest = client.get_version(name)
        except NotFoundError:
            latest = None
        if latest is None:
            try:
                client.get_prompt_info(name)
            except NotFoundError:
                if not dry_run:
                    client.create_prompt(name, prompt_file.description)
            status: Literal["created", "new_version"] = "created"
        else:
            if latest.content_hash == compute_content_hash(data.template, data.llm_config):
                return PushResult(name, "unchanged", version=latest.version)
            status = "new_version"

        warning = None
        based_on = prompt_file.version
        if latest is not None and based_on is not None and latest.version > based_on:
            warning = (
                f"the database has v{latest.version}, newer than v{based_on} "
                "this file was exported from; created a new version anyway"
            )

        if dry_run:
            next_version = (latest.version + 1) if latest else 1
            return PushResult(name, status, next_version, tag, warning)

        created = client.create_version(
            name,
            prompt_file.template,
            model_config=prompt_file.model_config,
            commit_message=data.commit_message,
        )
        if tag is not None:
            try:
                moved = client.promote(name, tag, created.version, reason=f"push {path.name}")
                warning = "; ".join(filter(None, [warning, *moved.warnings])) or None
            except PromptDockError as exc:
                error = f"created v{created.version} but did not move '{tag}': {exc}"
                return PushResult(name, status, created.version, None, warning, error)
        return PushResult(name, status, created.version, tag, warning)
    except ValidationError as exc:
        return PushResult(name, "error", error=f"{path.name}: {exc.errors()[0]['msg']}")
    except PromptDockError as exc:
        return PushResult(name, "error", error=str(exc))
