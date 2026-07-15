import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / ".viewer_builder" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from viewer_builder.build import discover_tree  # noqa: E402


class DiscoverTreeTests(unittest.TestCase):
    def test_only_publishable_directories_are_visible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            (repo_root / "Internal" / "ReadmeOnly").mkdir(parents=True)
            (repo_root / "Internal" / "ReadmeOnly" / "README.md").write_text(
                "Overview",
                encoding="utf-8",
            )
            (repo_root / "External" / "Nested" / "Documents").mkdir(parents=True)
            (repo_root / "External" / "Nested" / "Documents" / "Policy.md").write_text(
                "Policy",
                encoding="utf-8",
            )
            (repo_root / "External" / "OnlyText").mkdir(parents=True)
            (repo_root / "External" / "OnlyText" / "Offer.txt").write_text(
                "Offer",
                encoding="utf-8",
            )
            (repo_root / "External" / "MetaOnly").mkdir(parents=True)
            (repo_root / "External" / "MetaOnly" / "Meta.md").write_text(
                "Metadata",
                encoding="utf-8",
            )

            documents, readmes, metas, directories = discover_tree(repo_root)

        self.assertEqual(documents, ["External/Nested/Documents/Policy.md"])
        self.assertEqual(readmes, {"Internal/ReadmeOnly": "Internal/ReadmeOnly/README.md"})
        self.assertEqual(metas, {"External/MetaOnly/Meta.md": "External/MetaOnly/Meta.md"})
        self.assertEqual(
            directories,
            {
                "Internal",
                "Internal/ReadmeOnly",
                "External",
                "External/Nested",
                "External/Nested/Documents",
            },
        )

    def test_rejects_symbolic_links_in_source_trees(self) -> None:
        link_names = ("Leak.md", "README.md", "Meta.md", "Assets")

        for link_name in link_names:
            with self.subTest(link_name=link_name), tempfile.TemporaryDirectory() as temporary_directory:
                workspace = Path(temporary_directory)
                repo_root = workspace / "repo"
                internal_root = repo_root / "Internal"
                (repo_root / "External").mkdir(parents=True)
                internal_root.mkdir()

                if link_name == "Assets":
                    target = workspace / "outside-directory"
                    target.mkdir()
                    (target / "Secret.md").write_text("secret", encoding="utf-8")
                    (internal_root / link_name).symlink_to(target, target_is_directory=True)
                else:
                    target = workspace / "outside-file"
                    target.write_text("secret", encoding="utf-8")
                    (internal_root / link_name).symlink_to(target)

                with self.assertRaisesRegex(ValueError, "Symbolic links are not supported"):
                    discover_tree(repo_root)

    def test_rejects_broken_symbolic_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            (repo_root / "Internal").mkdir()
            (repo_root / "External").mkdir()
            (repo_root / "Internal" / "Broken.md").symlink_to(repo_root / "missing.md")

            with self.assertRaisesRegex(ValueError, "Internal/Broken.md"):
                discover_tree(repo_root)

    def test_rejects_symbolic_link_as_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repo_root = workspace / "repo"
            repo_root.mkdir()
            (repo_root / "External").mkdir()
            real_internal_root = workspace / "real-internal"
            real_internal_root.mkdir()
            (real_internal_root / "Secret.md").write_text("secret", encoding="utf-8")
            (repo_root / "Internal").symlink_to(real_internal_root, target_is_directory=True)

            with self.assertRaisesRegex(ValueError, "Source tree must not be a symbolic link: Internal"):
                discover_tree(repo_root)


if __name__ == "__main__":
    unittest.main()
