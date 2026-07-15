import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / ".viewer_builder" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from viewer_builder.build import MetaPage, discover_tree, select_meta_for_document  # noqa: E402


def make_meta_pages(*repo_paths: str) -> dict[str, MetaPage]:
    return {
        repo_path: MetaPage(repo_path=repo_path, site_rel_path="", source_root="Internal")
        for repo_path in repo_paths
    }


class SelectMetaForDocumentTests(unittest.TestCase):
    def test_prefers_language_specific_meta(self) -> None:
        meta_pages = make_meta_pages(
            "Internal/Policy/Rules.ru.meta.md",
            "Internal/Policy/Rules.meta.md",
            "Internal/Policy/Meta.md",
        )

        selected = select_meta_for_document("Internal/Policy/Rules.ru.md", meta_pages)

        self.assertIsNotNone(selected)
        self.assertEqual(selected.repo_path, "Internal/Policy/Rules.ru.meta.md")

    def test_language_variants_share_language_neutral_meta(self) -> None:
        meta_pages = make_meta_pages(
            "Internal/Policy/Rules.meta.md",
            "Internal/Policy/Meta.md",
        )

        for language in ("ru", "en"):
            with self.subTest(language=language):
                selected = select_meta_for_document(f"Internal/Policy/Rules.{language}.md", meta_pages)

                self.assertIsNotNone(selected)
                self.assertEqual(selected.repo_path, "Internal/Policy/Rules.meta.md")

    def test_uses_directory_meta_as_last_fallback(self) -> None:
        meta_pages = make_meta_pages("Internal/Policy/Meta.md")

        selected = select_meta_for_document("Internal/Policy/Rules.ru.md", meta_pages)

        self.assertIsNotNone(selected)
        self.assertEqual(selected.repo_path, "Internal/Policy/Meta.md")

    def test_uses_specific_meta_for_document_without_language_suffix(self) -> None:
        meta_pages = make_meta_pages(
            "Internal/Policy/Rules.meta.md",
            "Internal/Policy/Meta.md",
        )

        selected = select_meta_for_document("Internal/Policy/Rules.md", meta_pages)

        self.assertIsNotNone(selected)
        self.assertEqual(selected.repo_path, "Internal/Policy/Rules.meta.md")

    def test_returns_none_when_no_meta_exists(self) -> None:
        self.assertIsNone(select_meta_for_document("Internal/Policy/Rules.ru.md", {}))

    def test_does_not_fuzzy_match_a_misspelled_meta_name(self) -> None:
        meta_pages = make_meta_pages("Internal/Policy/Rulse.meta.md")

        self.assertIsNone(select_meta_for_document("Internal/Policy/Rules.ru.md", meta_pages))


class RepositoryMetaCoverageTests(unittest.TestCase):
    def test_every_meta_page_is_selected_by_at_least_one_document(self) -> None:
        document_paths, _readmes, meta_sources, _directories = discover_tree(REPO_ROOT)
        meta_pages = make_meta_pages(*meta_sources)
        selected_paths = {
            selected.repo_path
            for document_path in document_paths
            if (selected := select_meta_for_document(document_path, meta_pages)) is not None
        }

        self.assertEqual(set(meta_sources), selected_paths)


if __name__ == "__main__":
    unittest.main()
