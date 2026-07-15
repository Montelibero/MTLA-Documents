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


if __name__ == "__main__":
    unittest.main()
