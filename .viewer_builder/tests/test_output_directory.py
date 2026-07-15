import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / ".viewer_builder" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from viewer_builder.build import reset_output_directory, validate_output_directory  # noqa: E402


class ResetOutputDirectoryTests(unittest.TestCase):
    def test_validation_preserves_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            output_dir = repo_root / ".viewer_builder" / ".output" / "site"
            output_dir.mkdir(parents=True)
            existing_file = output_dir / "current.html"
            existing_file.write_text("current", encoding="utf-8")

            result = validate_output_directory(repo_root, output_dir)

            self.assertEqual(result, output_dir.resolve())
            self.assertEqual(existing_file.read_text(encoding="utf-8"), "current")

    def test_resets_child_of_managed_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            output_dir = repo_root / ".viewer_builder" / ".output" / "preview"
            output_dir.mkdir(parents=True)
            stale_file = output_dir / "stale.html"
            stale_file.write_text("old", encoding="utf-8")

            result = reset_output_directory(repo_root, output_dir)

            self.assertEqual(result, output_dir.resolve())
            self.assertTrue(output_dir.is_dir())
            self.assertFalse(stale_file.exists())

    def test_rejects_repository_root_without_deleting_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            sentinel = repo_root / "keep.txt"
            sentinel.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "must be a child"):
                reset_output_directory(repo_root, repo_root)

            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_rejects_managed_output_root_without_deleting_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            output_root = repo_root / ".viewer_builder" / ".output"
            output_root.mkdir(parents=True)
            sentinel = output_root / "keep.txt"
            sentinel.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "must be a child"):
                reset_output_directory(repo_root, output_root)

            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_rejects_directory_outside_managed_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            repo_root = temporary_root / "repo"
            outside_dir = temporary_root / "outside"
            repo_root.mkdir()
            outside_dir.mkdir()
            sentinel = outside_dir / "keep.txt"
            sentinel.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "must be a child"):
                reset_output_directory(repo_root, outside_dir)

            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_rejects_file_as_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            output_file = repo_root / ".viewer_builder" / ".output" / "site"
            output_file.parent.mkdir(parents=True)
            output_file.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "not a directory"):
                reset_output_directory(repo_root, output_file)

            self.assertEqual(output_file.read_text(encoding="utf-8"), "keep")

    def test_rejects_symlink_from_managed_root_to_outside(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            repo_root = temporary_root / "repo"
            output_root = repo_root / ".viewer_builder" / ".output"
            outside_dir = temporary_root / "outside"
            output_root.mkdir(parents=True)
            outside_dir.mkdir()
            sentinel = outside_dir / "keep.txt"
            sentinel.write_text("keep", encoding="utf-8")
            output_link = output_root / "site"
            output_link.symlink_to(outside_dir, target_is_directory=True)

            with self.assertRaisesRegex(ValueError, "must be a child"):
                reset_output_directory(repo_root, output_link)

            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_rejects_symlinked_managed_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            repo_root = temporary_root / "repo"
            viewer_builder = repo_root / ".viewer_builder"
            outside_root = temporary_root / "outside"
            viewer_builder.mkdir(parents=True)
            outside_root.mkdir()
            (viewer_builder / ".output").symlink_to(outside_root, target_is_directory=True)
            sentinel = outside_root / "keep.txt"
            sentinel.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "must not be a symlink"):
                reset_output_directory(repo_root, outside_root / "site")

            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
