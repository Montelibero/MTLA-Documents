import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / ".viewer_builder" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from viewer_builder.build import (  # noqa: E402
    Config,
    OutputClaim,
    resolve_local_output_reference,
    validate_generated_links,
    validate_output_claims,
)


def make_config(output_dir: Path) -> Config:
    return Config(
        site_title="Test documents",
        repo_commit_base_url="https://example.test/commit",
        site_origin="https://docs.example.test",
        site_base_path="/docs",
        output_dir=output_dir,
    )


def write_output(output_dir: Path, relative_path: str, content: str) -> None:
    target = output_dir / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


class ResolveLocalOutputReferenceTests(unittest.TestCase):
    def test_resolves_relative_root_and_same_origin_references(self) -> None:
        config = make_config(Path("output"))

        self.assertEqual(
            resolve_local_output_reference(config, "Guides/Page.html", "../Policy.html#terms"),
            ("Policy.html", "terms"),
        )
        self.assertEqual(
            resolve_local_output_reference(
                config,
                "Guides/Page.html",
                "https://docs.example.test/docs/Guide.html",
            ),
            ("Guide.html", ""),
        )
        self.assertIsNone(
            resolve_local_output_reference(
                config,
                "Guides/Page.html",
                "https://external.example/Guide.html",
            )
        )


class ValidateGeneratedLinksTests(unittest.TestCase):
    def test_accepts_valid_current_links_and_ignores_snapshot_outgoing_links(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            config = make_config(output_dir)
            claims = [
                OutputClaim("index.html", "directory page for Internal"),
                OutputClaim("Guide.html", "canonical document page for Internal/Guide.md"),
                OutputClaim("Guide.clear.html", "clear document page for Internal/Guide.md"),
                OutputClaim("assets/site.css", "builder asset site.css"),
                OutputClaim("snapshots/abc.html", "HTML snapshot abc"),
            ]
            manifest = validate_output_claims(claims)
            write_output(
                output_dir,
                "index.html",
                '<a href="/docs/Guide.html#section">Guide</a>'
                '<link href="/docs/assets/site.css">'
                '<a href="https://external.example/missing">External</a>',
            )
            write_output(
                output_dir,
                "Guide.html",
                '<h1 id="section">Guide</h1><a href="#section">Section</a>',
            )
            write_output(output_dir, "Guide.clear.html", '<a href="missing.html">Ignored</a>')
            write_output(
                output_dir,
                "snapshots/abc.html",
                '<a href="historical-missing.html">Ignored history</a>',
            )

            validate_generated_links(config, manifest)

    def test_reports_missing_target_and_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            config = make_config(output_dir)
            manifest = validate_output_claims(
                [
                    OutputClaim("index.html", "directory page for Internal"),
                    OutputClaim("Guide.html", "canonical document page for Internal/Guide.md"),
                ]
            )
            write_output(
                output_dir,
                "index.html",
                '<a href="missing.html">Missing</a><a href="Guide.html#missing">Anchor</a>',
            )
            write_output(output_dir, "Guide.html", '<h1 id="present">Guide</h1>')

            with self.assertRaises(ValueError) as raised:
                validate_generated_links(config, manifest)

            message = str(raised.exception)
            self.assertIn("missing missing.html", message)
            self.assertIn("missing #missing in Guide.html", message)


if __name__ == "__main__":
    unittest.main()
