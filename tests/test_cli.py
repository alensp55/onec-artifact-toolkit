from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch
import unittest

from onec_artifact_toolkit.cli import command_dump, create_parser


class CliTests(unittest.TestCase):
    def test_dump_dry_run_redacts_password(self) -> None:
        arguments = create_parser().parse_args(
            [
                "dump",
                "--designer",
                "designer.exe",
                "--server-base",
                "localhost\\demo",
                "--user-env",
                "APP_USER",
                "--password-env",
                "APP_SECRET",
                "--dry-run",
                "sample.epf",
                "source/sample.xml",
            ]
        )
        output = StringIO()

        with patch.dict("os.environ", {"APP_USER": "operator", "APP_SECRET": "private-value"}):
            with redirect_stdout(output):
                exit_code = command_dump(arguments)

        self.assertEqual(0, exit_code)
        self.assertIn('"***"', output.getvalue())
        self.assertNotIn("private-value", output.getvalue())


if __name__ == "__main__":
    unittest.main()
