import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / ".viewer_builder" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from viewer_builder.build import (  # noqa: E402
    Document,
    MetaPage,
    OutputClaim,
    collect_output_claims,
    discover_tree,
    replace_markdown_extension,
    site_rel_from_repo_path,
    source_root_from_repo_path,
    validate_output_claims,
    verify_output_manifest,
)


def make_document(repo_path: str, body: bytes = b"") -> Document:
    return Document(
        repo_path=repo_path,
        site_rel_path=site_rel_from_repo_path(repo_path),
        source_root=source_root_from_repo_path(repo_path),
        current_bytes=body,
    )


class ValidateOutputClaimsTests(unittest.TestCase):
    def test_rejects_exact_duplicate_output_path(self) -> None:
        claims = [
            OutputClaim("Guide.clear.html", "clear page for Internal/Guide.md"),
            OutputClaim("Guide.clear.html", "canonical page for Internal/Guide.clear.md"),
        ]

        with self.assertRaises(ValueError) as raised:
            validate_output_claims(claims)

        message = str(raised.exception)
        self.assertIn("Guide.clear.html", message)
        self.assertIn("Internal/Guide.md", message)
        self.assertIn("Internal/Guide.clear.md", message)

    def test_rejects_file_directory_prefix_conflict_in_either_order(self) -> None:
        file_claim = OutputClaim("Guide.html", "canonical page for Internal/Guide.md")
        nested_claim = OutputClaim(
            "Guide.html/index.html",
            "directory page for Internal/Guide.html",
        )

        for claims in ([file_claim, nested_claim], [nested_claim, file_claim]):
            with self.subTest(first=claims[0].relative_path):
                with self.assertRaises(ValueError) as raised:
                    validate_output_claims(claims)

            message = str(raised.exception)
            self.assertIn("Guide.html", message)
            self.assertIn("Internal/Guide.md", message)
            self.assertIn("Internal/Guide.html", message)

    def test_rejects_case_and_unicode_equivalent_paths(self) -> None:
        equivalent_pairs = (
            ("Guide.clear.html", "guide.CLEAR.html"),
            ("Caf\u00e9.html", "Cafe\u0301.html"),
        )

        for first_path, second_path in equivalent_pairs:
            with self.subTest(first_path=first_path, second_path=second_path):
                with self.assertRaisesRegex(ValueError, "Output path collision"):
                    validate_output_claims(
                        [
                            OutputClaim(first_path, "first producer"),
                            OutputClaim(second_path, "second producer"),
                        ]
                    )

        with self.assertRaisesRegex(ValueError, "Output directory collision"):
            validate_output_claims(
                [
                    OutputClaim("Assets", "first directory", is_directory=True),
                    OutputClaim("assets", "second directory", is_directory=True),
                ]
            )

    def test_collector_exposes_generated_document_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            claims = collect_output_claims(
                Path(temporary_directory),
                [
                    make_document("Internal/Guide.md"),
                    make_document("Internal/Guide.clear.md"),
                ],
                (),
                {"Internal", "External"},
                (),
            )

        with self.assertRaisesRegex(ValueError, "Guide.clear.html"):
            validate_output_claims(claims)

    def test_collector_exposes_internal_external_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            claims = collect_output_claims(
                Path(temporary_directory),
                [
                    make_document("Internal/External/Guide.md"),
                    make_document("External/Guide.md"),
                ],
                (),
                {"Internal", "Internal/External", "External"},
                (),
            )

        with self.assertRaisesRegex(ValueError, "External/Guide.md"):
            validate_output_claims(claims)

    def test_collector_deduplicates_snapshot_hashes(self) -> None:
        sha256 = "a" * 64
        with tempfile.TemporaryDirectory() as temporary_directory:
            claims = collect_output_claims(
                Path(temporary_directory),
                (),
                [sha256, sha256],
                {"Internal", "External"},
                (),
            )

        snapshot_claims = [
            claim for claim in claims if claim.relative_path.startswith(f"snapshots/{sha256}")
        ]
        self.assertEqual(len(snapshot_claims), 2)
        validate_output_claims(claims)

    def test_collector_rejects_symlinked_builder_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            assets_root = repo_root / ".viewer_builder" / "assets"
            assets_root.mkdir(parents=True)
            outside_file = repo_root / "outside.css"
            outside_file.write_text("secret", encoding="utf-8")
            (assets_root / "site.css").symlink_to(outside_file)

            with self.assertRaisesRegex(ValueError, "site.css"):
                collect_output_claims(
                    repo_root,
                    (),
                    (),
                    {"Internal", "External"},
                    (),
                )

    def test_current_repository_has_no_output_collisions(self) -> None:
        document_paths, _readmes, meta_sources, directories = discover_tree(REPO_ROOT)
        documents: list[Document] = []
        current_hashes: set[str] = set()
        for repo_path in document_paths:
            body = (REPO_ROOT / repo_path).read_bytes()
            documents.append(make_document(repo_path, body))
            current_hashes.add(hashlib.sha256(body).hexdigest())

        meta_pages = [
            MetaPage(
                repo_path=repo_path,
                site_rel_path=replace_markdown_extension(
                    site_rel_from_repo_path(repo_path),
                    ".html",
                ),
                source_root=source_root_from_repo_path(repo_path),
            )
            for repo_path in meta_sources
        ]
        claims = collect_output_claims(
            REPO_ROOT,
            documents,
            current_hashes,
            directories | {"Internal", "External"},
            meta_pages,
        )

        manifest = validate_output_claims(claims)

        self.assertEqual(len(manifest), sum(not claim.is_directory for claim in claims))

    def test_verifies_generated_files_match_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            expected_file = output_dir / "expected.html"
            expected_file.write_text("expected", encoding="utf-8")
            manifest = validate_output_claims(
                [OutputClaim("expected.html", "expected page")]
            )

            verify_output_manifest(output_dir, manifest)

            missing_manifest = validate_output_claims(
                [
                    OutputClaim("expected.html", "expected page"),
                    OutputClaim("missing.html", "missing page"),
                ]
            )
            with self.assertRaisesRegex(RuntimeError, "missing: missing.html"):
                verify_output_manifest(output_dir, missing_manifest)

            (output_dir / "unexpected.html").write_text("unexpected", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "unexpected: unexpected.html"):
                verify_output_manifest(output_dir, manifest)


if __name__ == "__main__":
    unittest.main()
