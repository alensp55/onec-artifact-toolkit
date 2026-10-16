from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from onec_artifact_toolkit.designer import (
    Infobase,
    build_dump_command,
    build_load_command,
    redact_arguments,
)


class DesignerTests(unittest.TestCase):
    def test_dump_uses_documented_argument_order(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            command = build_dump_command(
                root / "designer.exe",
                Infobase.file(root / "base"),
                root / "sample.epf",
                root / "source" / "sample.xml",
                root / "dump.log",
            )

            operation = command.arguments.index("/DumpExternalDataProcessorOrReportToFiles")
            self.assertEqual(str((root / "source" / "sample.xml").resolve()), command.arguments[operation + 1])
            self.assertEqual(str((root / "sample.epf").resolve()), command.arguments[operation + 2])

    def test_load_uses_artifact_then_root_xml(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            command = build_load_command(
                root / "designer.exe",
                Infobase.file(root / "base"),
                root / "sample.erf",
                root / "source" / "sample.xml",
                root / "build.log",
            )

            operation = command.arguments.index("/LoadExternalDataProcessorOrReportFromFiles")
            self.assertEqual(str((root / "sample.erf").resolve()), command.arguments[operation + 1])
            self.assertEqual(str((root / "source" / "sample.xml").resolve()), command.arguments[operation + 2])

    def test_credentials_are_read_from_environment_and_redacted(self) -> None:
        infobase = Infobase.server("localhost\\demo").with_environment_credentials("APP_USER", "APP_SECRET")

        arguments = infobase.arguments({"APP_USER": "operator", "APP_SECRET": "sensitive-value"})
        display = redact_arguments(arguments)

        self.assertEqual(["/S", "localhost\\demo", "/N", "***", "/P", "***"], display)
        self.assertNotIn("sensitive-value", display)

    def test_missing_environment_value_is_rejected(self) -> None:
        infobase = Infobase.file(Path("base")).with_environment_credentials(None, "APP_SECRET")

        with self.assertRaisesRegex(ValueError, "APP_SECRET"):
            infobase.arguments({})

    def test_invalid_artifact_extension_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "epf or .erf"):
            build_dump_command(
                Path("designer.exe"),
                Infobase.file(Path("base")),
                Path("sample.bin"),
                Path("sample.xml"),
                Path("dump.log"),
            )


if __name__ == "__main__":
    unittest.main()
