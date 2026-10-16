from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from onec_artifact_toolkit.manifest import build_manifest, compare_manifests, read_text_document


class ManifestTests(unittest.TestCase):
    def test_manifest_detects_encoding_and_newlines(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Module.bsl").write_bytes("Процедура Тест()\r\nКонецПроцедуры\r\n".encode("cp1251"))

            manifest = build_manifest(root)

            self.assertEqual(1, len(manifest["files"]))
            self.assertEqual("cp1251", manifest["files"][0]["encoding"])
            self.assertEqual("crlf", manifest["files"][0]["newline"])

    def test_compare_reports_added_deleted_and_modified(self) -> None:
        with TemporaryDirectory() as first, TemporaryDirectory() as second:
            before = Path(first)
            after = Path(second)
            (before / "same.txt").write_text("same", encoding="utf-8")
            (after / "same.txt").write_text("same", encoding="utf-8")
            (before / "old.txt").write_text("old", encoding="utf-8")
            (after / "new.txt").write_text("new", encoding="utf-8")
            (before / "changed.txt").write_text("before", encoding="utf-8")
            (after / "changed.txt").write_text("after", encoding="utf-8")

            result = compare_manifests(build_manifest(before), build_manifest(after))

            self.assertEqual(["new.txt"], result["added"])
            self.assertEqual(["old.txt"], result["deleted"])
            self.assertEqual(["changed.txt"], result["modified"])

    def test_binary_file_is_not_decoded(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "binary.bin"
            path.write_bytes(b"abc\x00def")
            self.assertIsNone(read_text_document(path))


if __name__ == "__main__":
    unittest.main()
