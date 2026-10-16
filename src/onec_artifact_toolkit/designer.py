from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence
import os
import subprocess


ARTIFACT_SUFFIXES = {".epf", ".erf"}


@dataclass(frozen=True)
class Infobase:
    mode: str
    location: str
    user_environment: str | None = None
    password_environment: str | None = None

    @classmethod
    def file(cls, path: Path) -> "Infobase":
        return cls("file", str(path.resolve()))

    @classmethod
    def server(cls, address: str) -> "Infobase":
        normalized = address.strip()
        if not normalized or "\\" not in normalized:
            raise ValueError("Server infobase must use the server\\database form")
        return cls("server", normalized)

    def with_environment_credentials(
        self,
        user_environment: str | None,
        password_environment: str | None,
    ) -> "Infobase":
        return Infobase(self.mode, self.location, user_environment, password_environment)

    def arguments(self, environment: Mapping[str, str] | None = None) -> list[str]:
        values = os.environ if environment is None else environment
        result = ["/F" if self.mode == "file" else "/S", self.location]
        result.extend(_credential_arguments("/N", self.user_environment, values))
        result.extend(_credential_arguments("/P", self.password_environment, values))
        return result


@dataclass(frozen=True)
class DesignerCommand:
    executable: Path
    arguments: tuple[str, ...]
    log_path: Path
    required_inputs: tuple[Path, ...]

    def display_arguments(self) -> list[str]:
        return redact_arguments([str(self.executable), *self.arguments])


@dataclass(frozen=True)
class DesignerResult:
    return_code: int
    log_path: Path

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0


def _credential_arguments(
    switch: str,
    variable_name: str | None,
    environment: Mapping[str, str],
) -> list[str]:
    if variable_name is None:
        return []
    value = environment.get(variable_name)
    if value is None:
        raise ValueError(f"Environment variable is not set: {variable_name}")
    return [switch, value]


def validate_artifact_path(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.suffix.casefold() not in ARTIFACT_SUFFIXES:
        raise ValueError("External artifact must have the .epf or .erf extension")
    return resolved


def validate_root_xml(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.suffix.casefold() != ".xml":
        raise ValueError("Root source file must have the .xml extension")
    return resolved


def build_dump_command(
    executable: Path,
    infobase: Infobase,
    artifact: Path,
    root_xml: Path,
    log_path: Path,
    environment: Mapping[str, str] | None = None,
) -> DesignerCommand:
    artifact_path = validate_artifact_path(artifact)
    xml_path = validate_root_xml(root_xml)
    arguments = _base_arguments(infobase, environment)
    arguments.extend(
        [
            "/DumpExternalDataProcessorOrReportToFiles",
            str(xml_path),
            str(artifact_path),
            "/Out",
            str(log_path.resolve()),
        ]
    )
    return DesignerCommand(executable.resolve(), tuple(arguments), log_path.resolve(), (artifact_path,))


def build_load_command(
    executable: Path,
    infobase: Infobase,
    artifact: Path,
    root_xml: Path,
    log_path: Path,
    environment: Mapping[str, str] | None = None,
) -> DesignerCommand:
    artifact_path = validate_artifact_path(artifact)
    xml_path = validate_root_xml(root_xml)
    arguments = _base_arguments(infobase, environment)
    arguments.extend(
        [
            "/LoadExternalDataProcessorOrReportFromFiles",
            str(artifact_path),
            str(xml_path),
            "/Out",
            str(log_path.resolve()),
        ]
    )
    return DesignerCommand(executable.resolve(), tuple(arguments), log_path.resolve(), (xml_path,))


def _base_arguments(
    infobase: Infobase,
    environment: Mapping[str, str] | None,
) -> list[str]:
    return [
        "DESIGNER",
        *infobase.arguments(environment),
        "/DisableStartupDialogs",
        "/DisableStartupMessages",
    ]


def redact_arguments(arguments: Sequence[str]) -> list[str]:
    result = list(arguments)
    for index, argument in enumerate(result[:-1]):
        if argument.casefold() in {"/n", "/p"}:
            result[index + 1] = "***"
    return result


def execute_designer(command: DesignerCommand, timeout: int = 300) -> DesignerResult:
    if timeout <= 0:
        raise ValueError("Timeout must be greater than zero")
    if not command.executable.is_file():
        raise ValueError(f"Designer executable does not exist: {command.executable}")
    missing_inputs = [path for path in command.required_inputs if not path.is_file()]
    if missing_inputs:
        raise ValueError(f"Input file does not exist: {missing_inputs[0]}")
    command.log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            [str(command.executable), *command.arguments],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError(f"Designer did not finish within {timeout} seconds") from error
    return DesignerResult(completed.returncode, command.log_path)
