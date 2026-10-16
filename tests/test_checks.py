from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from onec_artifact_toolkit.checks import check_source_tree, release_scan


class CheckTests(unittest.TestCase):
    def test_source_checks_find_tabs_length_and_trailing_spaces(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Module.bsl").write_text("\tСтрока = 1;  \n" + "А" * 121, encoding="utf-8")

            rules = {finding.rule for finding in check_source_tree(root)}

            self.assertEqual({"tab-character", "trailing-whitespace", "line-length"}, rules)

    def test_release_scan_uses_denylist_without_echoing_source_data(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            denied_value = "internal" + ".example"
            (root / "README.md").write_text(denied_value, encoding="utf-8")

            findings = release_scan(root, [denied_value])

            self.assertEqual(1, len(findings))
            self.assertEqual("denylist", findings[0].rule)

    def test_release_scan_finds_private_data_patterns(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            token = "ghp_" + "A" * 30
            content = "contact" + "@" + "example.org\n" + token
            (root / "values.txt").write_text(content, encoding="utf-8")

            findings = release_scan(root, [])

            messages = {finding.message for finding in findings}
            self.assertEqual({"email address", "GitHub token"}, messages)

    def test_release_scan_distinguishes_secret_literals_from_placeholders(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            value = "sensitive" + "-value"
            (root / "settings.txt").write_text(f'password = "{value}"\nsecret = "demo-value"', encoding="utf-8")

            findings = release_scan(root, [])

            self.assertEqual(["secret assignment"], [finding.message for finding in findings])


if __name__ == "__main__":
    unittest.main()
