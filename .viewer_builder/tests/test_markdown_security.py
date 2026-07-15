import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / ".viewer_builder" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from viewer_builder.build import Config, MarkdownRenderer  # noqa: E402


def make_renderer() -> MarkdownRenderer:
    config = Config(
        site_title="Test documents",
        repo_commit_base_url="https://example.test/commit",
        site_origin="https://docs.example.test",
        site_base_path="/docs",
        output_dir=Path("output"),
    )
    return MarkdownRenderer(
        config,
        {"Internal/Other.md": "/Other.html"},
    )


class MarkdownSecurityTests(unittest.TestCase):
    def test_escapes_raw_html(self) -> None:
        markdown_text = """<script>alert('xss')</script>

<img src=x onerror="alert('xss')">

<svg onload="alert('xss')"></svg>
"""

        rendered, _contents, _heading_count = make_renderer().render(
            markdown_text,
            "Internal/Test.md",
        )

        self.assertNotIn("<script", rendered)
        self.assertNotIn("<img", rendered)
        self.assertNotIn("<svg", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("&lt;img", rendered)
        self.assertIn("&lt;svg", rendered)

    def test_does_not_create_links_for_unsafe_schemes(self) -> None:
        renderer = make_renderer()
        unsafe_links = (
            "[JavaScript](javascript:alert(1))",
            "[Data](data:text/html,<script>alert(1)</script>)",
            "![SVG](data:image/svg+xml,<svg onload=alert(1)>)",
        )

        for markdown_text in unsafe_links:
            with self.subTest(markdown_text=markdown_text):
                rendered, _contents, _heading_count = renderer.render(
                    markdown_text,
                    "Internal/Test.md",
                )
                self.assertNotIn('href="javascript:', rendered.casefold())
                self.assertNotIn('href="data:', rendered.casefold())
                self.assertNotIn('src="data:image/svg', rendered.casefold())

    def test_preserves_markdown_formatting_and_safe_links(self) -> None:
        rendered, _contents, _heading_count = make_renderer().render(
            "# Heading\n\n**Bold** [internal](Other.md) [external](https://example.test)",
            "Internal/Test.md",
        )

        self.assertIn('<h1 id="heading">Heading</h1>', rendered)
        self.assertIn("<strong>Bold</strong>", rendered)
        self.assertIn('href="/docs/Other.html"', rendered)
        self.assertIn('href="https://example.test"', rendered)


if __name__ == "__main__":
    unittest.main()
