from __future__ import annotations

import argparse
import hashlib
import logging
import os
import posixpath
import re
import shutil
import subprocess
import sys
import json
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable
from urllib.parse import quote, unquote, urlsplit

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt
from markdown_it.token import Token
from PIL import Image


LOGGER = logging.getLogger("viewer_builder")
COMMIT_MARKER = "__COMMIT__"
LANGUAGE_RE = re.compile(r"^(?P<stem>.+)\.(?P<lang>[A-Za-z0-9_-]+)\.md$")


@dataclass
class Config:
    site_title: str
    repo_commit_base_url: str
    site_base_path: str
    output_dir: Path


@dataclass
class HistoryEntry:
    commit_sha: str
    commit_url: str
    committed_at_label: str
    committed_at_iso: str
    repo_path_at_commit: str
    sha256: str
    body: bytes

    @property
    def public_html_url(self) -> str:
        return f"/{self.sha256}.html"

    @property
    def public_md_url(self) -> str:
        return f"/{self.sha256}.md"


@dataclass
class MetaPage:
    repo_path: str
    site_rel_path: str
    source_root: str

    @property
    def filename(self) -> str:
        return PurePosixPath(self.repo_path).name

    @property
    def public_url(self) -> str:
        return to_public_url(self.site_rel_path)


@dataclass
class Document:
    repo_path: str
    site_rel_path: str
    source_root: str
    current_bytes: bytes
    history: list[HistoryEntry] = field(default_factory=list)
    meta_page: MetaPage | None = None
    language_links: list[tuple[str, str]] = field(default_factory=list)
    current_sha256: str = ""
    current_commit_sha: str = ""
    current_commit_url: str = ""
    current_committed_at_label: str = ""
    current_committed_at_iso: str = ""

    @property
    def filename(self) -> str:
        return PurePosixPath(self.repo_path).name

    @property
    def parent_repo_dir(self) -> str:
        return str(PurePosixPath(self.repo_path).parent)

    @property
    def section_title(self) -> str:
        return "External Files" if self.site_rel_path.startswith("External/") else "Association Files"

    @property
    def canonical_html_rel_path(self) -> str:
        return replace_markdown_extension(self.site_rel_path, ".html")

    @property
    def canonical_html_url(self) -> str:
        return to_public_url(self.canonical_html_rel_path)

    @property
    def canonical_md_url(self) -> str:
        return to_public_url(self.site_rel_path)

    @property
    def history_rel_path(self) -> str:
        return replace_markdown_extension(self.site_rel_path, ".history.html")

    @property
    def history_url(self) -> str:
        return to_public_url(self.history_rel_path)

    @property
    def canonical_dir_rel_path(self) -> str:
        parent = PurePosixPath(self.site_rel_path).parent.as_posix()
        return "" if parent == "." else parent

    @property
    def permanent_snapshot_url(self) -> str:
        return f"/{self.current_sha256}.html"


@dataclass
class DirectoryEntry:
    label: str
    url: str
    kind: str
    modified_at_label: str = ""


@dataclass
class DirectoryPage:
    repo_dir: str
    site_dir_rel_path: str
    source_root: str
    readme_repo_path: str | None
    title: str
    directory_entries: list[DirectoryEntry] = field(default_factory=list)
    document_entries: list[DirectoryEntry] = field(default_factory=list)

    @property
    def section_title(self) -> str:
        return "External Files" if self.site_dir_rel_path.startswith("External") else "Association Files"

    @property
    def public_url(self) -> str:
        return to_directory_public_url(self.site_dir_rel_path)


@dataclass
class SnapshotPage:
    sha256: str
    body: bytes
    canonical_filename: str
    canonical_url: str
    section_title: str
    breadcrumb_site_rel: str
    commit_sha: str
    commit_url: str
    committed_at_label: str
    committed_at_iso: str
    source_repo_path_at_commit: str
    status_badges: list[dict[str, str]] = field(default_factory=list)

    @property
    def public_html_url(self) -> str:
        return f"/{self.sha256}.html"

    @property
    def public_md_url(self) -> str:
        return f"/{self.sha256}.md"


@dataclass
class HeadingEntry:
    level: int
    text: str
    anchor: str
    children: list["HeadingEntry"] = field(default_factory=list)


def replace_markdown_extension(path_value: str, new_suffix: str) -> str:
    if not path_value.endswith(".md"):
        raise ValueError(f"Not a markdown path: {path_value}")
    return path_value[:-3] + new_suffix


def to_public_url(site_rel_path: str) -> str:
    stripped = site_rel_path.strip("/")
    if not stripped:
        return "/"
    return "/" + quote(stripped, safe="/")


def to_directory_public_url(site_dir_rel_path: str) -> str:
    stripped = site_dir_rel_path.strip("/")
    if not stripped:
        return "/"
    return "/" + quote(stripped, safe="/") + "/"


def repo_path_for_fs_path(repo_root: Path, fs_path: Path) -> str:
    return fs_path.relative_to(repo_root).as_posix()


def site_rel_from_repo_path(repo_path: str) -> str:
    pure = PurePosixPath(repo_path)
    parts = pure.parts
    if not parts:
        raise ValueError("Empty repo path")
    if parts[0] == "Internal":
        return PurePosixPath(*parts[1:]).as_posix() if len(parts) > 1 else ""
    if parts[0] == "External":
        tail = PurePosixPath(*parts[1:]).as_posix() if len(parts) > 1 else ""
        return "External" if not tail else f"External/{tail}"
    raise ValueError(f"Unsupported source root in path: {repo_path}")


def source_root_from_repo_path(repo_path: str) -> str:
    return PurePosixPath(repo_path).parts[0]


def load_config(repo_root: Path, output_override: str | None) -> Config:
    config_path = repo_root / ".viewer_builder" / "config.yml"
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    output_dir = Path(output_override) if output_override else Path(raw.get("output_dir", ".viewer_builder/.output/site"))
    return Config(
        site_title=str(raw["site_title"]),
        repo_commit_base_url=str(raw["repo_commit_base_url"]).rstrip("/"),
        site_base_path=str(raw.get("site_base_path", "") or "").rstrip("/"),
        output_dir=(repo_root / output_dir).resolve(),
    )


def site_url(config: Config, public_url: str) -> str:
    if public_url == "/":
        return f"{config.site_base_path}/" if config.site_base_path else "/"
    return f"{config.site_base_path}{public_url}" if config.site_base_path else public_url


def output_path_for_relative(output_root: Path, relative_path: str) -> Path:
    if not relative_path:
        return output_root / "index.html"
    return output_root / PurePosixPath(relative_path)


def output_path_for_directory(output_root: Path, site_dir_rel_path: str) -> Path:
    if not site_dir_rel_path:
        return output_root / "index.html"
    return output_root / PurePosixPath(site_dir_rel_path) / "index.html"


def iso_to_utc_label(value: str) -> str:
    normalized = value.replace("Z", "+00:00")
    timestamp = datetime.fromisoformat(normalized).astimezone(timezone.utc)
    return timestamp.strftime("%Y-%m-%d %H:%M")


def iso_to_utc_timestamp(value: str) -> str:
    normalized = value.replace("Z", "+00:00")
    timestamp = datetime.fromisoformat(normalized).astimezone(timezone.utc)
    return timestamp.isoformat(timespec="seconds").replace("+00:00", "Z")


def run_git(repo_root: Path, *args: str, text: bool = True) -> str | bytes:
    command = ["git", *args]
    result = subprocess.run(
        command,
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=text,
    )
    return result.stdout


def discover_tree(repo_root: Path) -> tuple[list[str], dict[str, str], dict[str, str], set[str]]:
    documents: list[str] = []
    readmes: dict[str, str] = {}
    metas: dict[str, str] = {}
    directories: set[str] = set()

    for root_name in ("Internal", "External"):
        root_path = repo_root / root_name
        for current_dir, dirnames, filenames in os.walk(root_path):
            dirnames.sort()
            filenames.sort()
            current_dir_path = Path(current_dir)
            repo_dir = repo_path_for_fs_path(repo_root, current_dir_path)
            directories.add(repo_dir)
            for filename in filenames:
                if not filename.endswith(".md"):
                    continue
                repo_path = repo_path_for_fs_path(repo_root, current_dir_path / filename)
                if filename == "README.md":
                    readmes[repo_dir] = repo_path
                elif filename == "Meta.md" or filename.endswith(".meta.md"):
                    metas[repo_path] = repo_path
                else:
                    documents.append(repo_path)
    documents.sort()
    return documents, readmes, metas, directories


def split_language_variant(filename: str) -> tuple[str, str] | None:
    match = LANGUAGE_RE.match(filename)
    if not match:
        return None
    return match.group("stem"), match.group("lang")


def select_meta_for_document(document_repo_path: str, meta_pages: dict[str, MetaPage]) -> MetaPage | None:
    document_path = PurePosixPath(document_repo_path)
    sibling_specific = f"{document_path.stem}.meta.md"
    specific_repo_path = str(document_path.parent / sibling_specific)
    if specific_repo_path in meta_pages:
        return meta_pages[specific_repo_path]
    shared_repo_path = str(document_path.parent / "Meta.md")
    return meta_pages.get(shared_repo_path)


def parse_history_entries(repo_root: Path, config: Config, document_repo_path: str) -> list[HistoryEntry]:
    raw_log = run_git(
        repo_root,
        "log",
        "--follow",
        "--name-status",
        f"--format={COMMIT_MARKER}%n%H%n%aI",
        "--",
        document_repo_path,
    )
    lines = raw_log.splitlines()
    entries: list[HistoryEntry] = []
    index = 0

    while index < len(lines):
        if lines[index] != COMMIT_MARKER:
            index += 1
            continue

        commit_sha = lines[index + 1]
        committed_at = lines[index + 2]
        index += 3
        while index < len(lines) and not lines[index]:
            index += 1

        status_lines: list[str] = []
        while index < len(lines) and lines[index] != COMMIT_MARKER:
            if lines[index]:
                status_lines.append(lines[index])
            index += 1

        if not status_lines:
            continue

        candidates: list[str]
        parts = status_lines[0].split("\t")
        status = parts[0]
        if status.startswith("R") and len(parts) >= 3:
            repo_path_at_commit = parts[2]
            candidates = [parts[2], parts[1]]
        elif len(parts) >= 2:
            repo_path_at_commit = parts[1]
            candidates = [parts[1]]
        else:
            continue

        body = None
        chosen_repo_path = repo_path_at_commit
        for candidate in candidates:
            try:
                body = run_git(repo_root, "show", f"{commit_sha}:{candidate}", text=False)
                chosen_repo_path = candidate
                break
            except subprocess.CalledProcessError:
                continue
        if body is None:
            raise RuntimeError(f"Unable to read historical file contents for {document_repo_path} in {commit_sha}")

        sha256 = hashlib.sha256(body).hexdigest()
        entries.append(
            HistoryEntry(
                commit_sha=commit_sha,
                commit_url=f"{config.repo_commit_base_url}/{commit_sha}",
                committed_at_label=iso_to_utc_label(committed_at),
                committed_at_iso=iso_to_utc_timestamp(committed_at),
                repo_path_at_commit=chosen_repo_path,
                sha256=sha256,
                body=body,
            )
        )

    return entries


def slugify_github(text: str, used: dict[str, int]) -> str:
    lowered = text.strip().lower()
    pieces: list[str] = []
    for character in lowered:
        category = unicodedata.category(character)
        if character in {" ", "-"}:
            pieces.append("-")
        elif character == "_":
            pieces.append("_")
        elif category.startswith(("L", "N", "M")):
            pieces.append(character)
    slug = re.sub(r"-{2,}", "-", "".join(pieces)).strip("-")
    if not slug:
        slug = "section"
    counter = used[slug]
    used[slug] += 1
    if counter:
        return f"{slug}-{counter}"
    return slug


class MarkdownRenderer:
    def __init__(self, config: Config, public_lookup: dict[str, str]):
        self.config = config
        self.public_lookup = public_lookup
        self.markdown = MarkdownIt("commonmark", {"html": True, "linkify": True})
        self.markdown.enable("table")
        self.markdown.enable("strikethrough")
        self.markdown.enable("linkify")
        if self.markdown.linkify is not None:
            self.markdown.linkify.set({"fuzzy_link": False, "fuzzy_email": False})

    def render(self, markdown_text: str, current_repo_path: str) -> tuple[str, list[HeadingEntry], int]:
        tokens = self.markdown.parse(markdown_text)
        headings = self._apply_heading_ids(tokens)
        self._rewrite_links(tokens, current_repo_path)
        html = self.markdown.renderer.render(tokens, self.markdown.options, {})
        contents_headings = normalize_contents_headings(headings)
        return html, build_heading_tree(contents_headings), len(contents_headings)

    def _apply_heading_ids(self, tokens: list[Token]) -> list[HeadingEntry]:
        used: dict[str, int] = defaultdict(int)
        headings: list[HeadingEntry] = []
        for index, token in enumerate(tokens):
            if token.type != "heading_open":
                continue
            inline_token = tokens[index + 1] if index + 1 < len(tokens) else None
            if inline_token is None or inline_token.type != "inline":
                continue
            slug = slugify_github(inline_token.content, used)
            token.attrSet("id", slug)
            headings.append(
                HeadingEntry(
                    level=int(token.tag[1]),
                    text=inline_token.content.strip(),
                    anchor=slug,
                )
            )
        return headings

    def _rewrite_links(self, tokens: Iterable[Token], current_repo_path: str) -> None:
        for token in tokens:
            if token.type == "link_open":
                href = token.attrGet("href")
                if href:
                    token.attrSet("href", self._rewrite_href(current_repo_path, href))
            if token.children:
                self._rewrite_links(token.children, current_repo_path)

    def _rewrite_href(self, current_repo_path: str, href: str) -> str:
        if href.startswith("#"):
            return href

        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc:
            return href
        if href.startswith(("mailto:", "tel:", "data:")):
            return href

        raw_path = unquote(parsed.path)
        fragment = f"#{parsed.fragment}" if parsed.fragment else ""

        if not raw_path:
            return href

        target_repo_path = None
        if raw_path.startswith("/"):
            root_candidate = raw_path.lstrip("/")
            if root_candidate == "":
                return site_url(self.config, "/") + fragment
            if root_candidate.startswith(("Internal/", "External/")):
                target_repo_path = posixpath.normpath(root_candidate)
        else:
            current_dir = str(PurePosixPath(current_repo_path).parent)
            target_repo_path = posixpath.normpath(posixpath.join(current_dir, raw_path))

        if not target_repo_path:
            return href

        public_url = self.public_lookup.get(target_repo_path)
        if public_url is None:
            return href
        return site_url(self.config, public_url) + fragment


def build_heading_tree(headings: list[HeadingEntry]) -> list[HeadingEntry]:
    root = HeadingEntry(level=0, text="", anchor="")
    stack: list[HeadingEntry] = [root]

    for heading in headings:
        while len(stack) > 1 and heading.level <= stack[-1].level:
            stack.pop()
        heading.children = []
        stack[-1].children.append(heading)
        stack.append(heading)

    return root.children


def normalize_contents_headings(headings: list[HeadingEntry]) -> list[HeadingEntry]:
    top_level_headings = [heading for heading in headings if heading.level == 1]
    if len(top_level_headings) == 1:
        return [heading for heading in headings if heading.level != 1]
    return headings


def repo_url_from_commit_base_url(commit_base_url: str) -> str:
    if commit_base_url.endswith("/commit"):
        return commit_base_url[:-7]
    return commit_base_url


def canonical_data_key(site_rel_path: str) -> str:
    if not site_rel_path.endswith(".md"):
        raise ValueError(f"Not a markdown path: {site_rel_path}")
    return "/" + quote(site_rel_path[:-3].strip("/"), safe="/")


def build_history_hashes(document: Document) -> list[str]:
    start_index = 1 if document.history and document.history[0].sha256 == document.current_sha256 else 0
    return [entry.sha256 for entry in document.history[start_index:]]


def write_data_json(config: Config, documents: list[Document], snapshots: dict[str, SnapshotPage]) -> None:
    current: dict[str, dict] = {}
    for document in sorted(documents, key=lambda item: canonical_data_key(item.site_rel_path).lower()):
        document_data: dict[str, object] = {
            "current_hash": document.current_sha256,
            "history_hashes": build_history_hashes(document),
        }
        if document.source_root == "External":
            document_data["is_external"] = True
        current[canonical_data_key(document.site_rel_path)] = document_data

    hashes = {
        sha256: {
            "commit": snapshot.commit_sha,
            "commit_url": snapshot.commit_url,
            "fixed_in_git_at": snapshot.committed_at_iso,
        }
        for sha256, snapshot in sorted(snapshots.items())
    }

    historical_snapshot_count = sum(len(build_history_hashes(document)) for document in documents)
    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "source_url": repo_url_from_commit_base_url(config.repo_commit_base_url),
            "stats": {
                "current_documents": len(documents),
                "historical_snapshots": historical_snapshot_count,
                "unique_hashes": len(snapshots),
            },
        },
        "current": current,
        "hashes": hashes,
    }
    (config.output_dir / "data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_breadcrumbs_for_path(site_rel_path: str, is_directory: bool, final_label: str) -> list[dict[str, str]]:
    crumbs = [{"label": "Home", "url": "/"}]
    normalized = site_rel_path.strip("/")
    if not normalized:
        if is_directory:
            crumbs[-1]["current"] = "true"
        return crumbs

    parts = normalized.split("/")
    limit = len(parts) if is_directory else len(parts) - 1
    for index in range(limit):
        label = parts[index]
        partial = "/".join(parts[: index + 1])
        crumbs.append({"label": label, "url": to_directory_public_url(partial)})

    if not is_directory:
        crumbs.append({"label": final_label, "url": ""})
    else:
        crumbs[-1]["current"] = "true"
    return crumbs


def build_breadcrumbs_for_meta(site_dir_rel_path: str, filename: str) -> list[dict[str, str]]:
    breadcrumbs = build_breadcrumbs_for_path(site_dir_rel_path, is_directory=True, final_label=filename)
    breadcrumbs.append({"label": filename, "url": ""})
    return breadcrumbs


def make_status_badge(label: str, tone: str) -> dict[str, str]:
    return {"label": label, "tone": tone}


def copy_assets(repo_root: Path, config: Config) -> None:
    source_dir = repo_root / ".viewer_builder" / "assets"
    target_dir = config.output_dir / "assets"
    shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)


def copy_root_extras(repo_root: Path, config: Config) -> None:
    llms_source = repo_root / ".viewer_builder" / "llms.txt"
    if llms_source.exists():
        shutil.copy2(llms_source, config.output_dir / "llms.txt")


def generate_favicons(repo_root: Path, config: Config) -> None:
    source_logo = repo_root / ".viewer_builder" / "assets" / "branding" / "fspe_logo.png"
    if not source_logo.exists():
        return

    favicon_specs = {
        "favicon-16x16.png": (16, 16),
        "favicon-32x32.png": (32, 32),
        "apple-touch-icon.png": (180, 180),
        "android-chrome-192x192.png": (192, 192),
        "android-chrome-512x512.png": (512, 512),
    }

    base_image = Image.open(source_logo).convert("RGBA")
    for filename, size in favicon_specs.items():
        resized = base_image.resize(size, Image.Resampling.LANCZOS)
        resized.save(config.output_dir / filename)

    icon_sizes = [(16, 16), (32, 32), (48, 48)]
    ico_frames = [base_image.resize(size, Image.Resampling.LANCZOS) for size in icon_sizes]
    ico_frames[0].save(
        config.output_dir / "favicon.ico",
        format="ICO",
        append_images=ico_frames[1:],
        sizes=icon_sizes,
    )

    manifest = {
        "name": config.site_title,
        "short_name": "MTLA Files",
        "icons": [
            {
                "src": site_url(config, "/android-chrome-192x192.png"),
                "sizes": "192x192",
                "type": "image/png",
            },
            {
                "src": site_url(config, "/android-chrome-512x512.png"),
                "sizes": "512x512",
                "type": "image/png",
            },
        ],
        "theme_color": "#121313",
        "background_color": "#121313",
        "display": "standalone",
    }
    (config.output_dir / "site.webmanifest").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def ensure_parent(path_value: Path) -> None:
    path_value.parent.mkdir(parents=True, exist_ok=True)


def render_template(environment: Environment, template_name: str, target_path: Path, context: dict) -> None:
    ensure_parent(target_path)
    html = environment.get_template(template_name).render(**context)
    target_path.write_text(html, encoding="utf-8")


def build_environment(repo_root: Path, config: Config) -> Environment:
    environment = Environment(
        loader=FileSystemLoader(str(repo_root / ".viewer_builder" / "templates")),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.globals["site_url"] = lambda public_url: site_url(config, public_url)
    environment.globals["site_title"] = config.site_title
    return environment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Montelibero document viewer.")
    parser.add_argument("--output-dir", help="Override the configured output directory.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    repo_root = Path(__file__).resolve().parents[3]
    config = load_config(repo_root, args.output_dir)

    if config.output_dir.exists():
        shutil.rmtree(config.output_dir)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    documents_repo_paths, readmes, meta_sources, directories = discover_tree(repo_root)
    meta_pages: dict[str, MetaPage] = {}
    for meta_repo_path in sorted(meta_sources):
        site_rel_path = replace_markdown_extension(site_rel_from_repo_path(meta_repo_path), ".html")
        meta_pages[meta_repo_path] = MetaPage(
            repo_path=meta_repo_path,
            site_rel_path=site_rel_path,
            source_root=source_root_from_repo_path(meta_repo_path),
        )

    documents: list[Document] = []
    for document_repo_path in documents_repo_paths:
        fs_path = repo_root / document_repo_path
        current_bytes = fs_path.read_bytes()
        document = Document(
            repo_path=document_repo_path,
            site_rel_path=site_rel_from_repo_path(document_repo_path),
            source_root=source_root_from_repo_path(document_repo_path),
            current_bytes=current_bytes,
        )
        document.history = parse_history_entries(repo_root, config, document_repo_path)
        if not document.history:
            raise RuntimeError(f"No git history found for {document_repo_path}")
        document.current_commit_sha = document.history[0].commit_sha
        document.current_commit_url = document.history[0].commit_url
        document.current_committed_at_label = document.history[0].committed_at_label
        document.current_committed_at_iso = document.history[0].committed_at_iso
        document.current_sha256 = hashlib.sha256(current_bytes).hexdigest()
        if document.current_sha256 != document.history[0].sha256:
            LOGGER.warning(
                "Working tree content for %s differs from latest committed history entry; canonical page uses current file bytes.",
                document.repo_path,
            )
        documents.append(document)

    documents_by_repo_path = {document.repo_path: document for document in documents}
    for document in documents:
        document.meta_page = select_meta_for_document(document.repo_path, meta_pages)

    language_groups: dict[tuple[str, str], list[Document]] = defaultdict(list)
    for document in documents:
        split = split_language_variant(document.filename)
        if split is None:
            continue
        stem, _language = split
        language_groups[(document.parent_repo_dir, stem)].append(document)
    for group_documents in language_groups.values():
        if len(group_documents) < 2:
            continue
        for document in group_documents:
            _, language = split_language_variant(document.filename) or ("", "")
            siblings = []
            for sibling in group_documents:
                if sibling.repo_path == document.repo_path:
                    continue
                sibling_split = split_language_variant(sibling.filename)
                if sibling_split is None:
                    continue
                siblings.append((sibling_split[1], sibling.canonical_html_url))
            document.language_links = sorted(siblings)

    public_lookup: dict[str, str] = {}
    all_repo_dirs = set(directories)
    all_repo_dirs.add("Internal")
    all_repo_dirs.add("External")

    for repo_dir in sorted(all_repo_dirs):
        public_lookup[repo_dir] = to_directory_public_url(site_rel_from_repo_path(repo_dir))
    for document in documents:
        public_lookup[document.repo_path] = document.canonical_html_url
    for repo_dir, readme_repo_path in readmes.items():
        public_lookup[readme_repo_path] = to_directory_public_url(site_rel_from_repo_path(repo_dir))
    for meta_repo_path, meta_page in meta_pages.items():
        public_lookup[meta_repo_path] = meta_page.public_url

    markdown_renderer = MarkdownRenderer(config, public_lookup)
    environment = build_environment(repo_root, config)

    snapshots: dict[str, SnapshotPage] = {}

    def register_snapshot(
        document: Document,
        sha256: str,
        body: bytes,
        commit_sha: str,
        commit_url: str,
        committed_at_label: str,
        committed_at_iso: str,
        repo_path_at_commit: str,
    ) -> None:
        existing = snapshots.get(sha256)
        if existing is not None:
            if sha256 == document.current_sha256:
                labels = {badge["label"] for badge in existing.status_badges}
                if "Current version" not in labels:
                    existing.status_badges.append(make_status_badge("Current version", "success"))
            if existing.commit_sha != commit_sha or existing.canonical_url != document.canonical_html_url:
                LOGGER.warning(
                    "SHA collision for %s: keeping %s @ %s, ignoring %s @ %s",
                    sha256,
                    existing.canonical_url,
                    existing.commit_sha,
                    document.canonical_html_url,
                    commit_sha,
                )
            return
        snapshots[sha256] = SnapshotPage(
            sha256=sha256,
            body=body,
            canonical_filename=document.filename,
            canonical_url=document.canonical_html_url,
            section_title=document.section_title,
            breadcrumb_site_rel=document.site_rel_path,
            commit_sha=commit_sha,
            commit_url=commit_url,
            committed_at_label=committed_at_label,
            committed_at_iso=committed_at_iso,
            source_repo_path_at_commit=repo_path_at_commit,
            status_badges=[
                make_status_badge("Current version", "success")
                if sha256 == document.current_sha256
                else make_status_badge("Historical version", "warning")
            ],
        )

    for document in documents:
        for entry in document.history:
            register_snapshot(
                document=document,
                sha256=entry.sha256,
                body=entry.body,
                commit_sha=entry.commit_sha,
                commit_url=entry.commit_url,
                committed_at_label=entry.committed_at_label,
                committed_at_iso=entry.committed_at_iso,
                repo_path_at_commit=entry.repo_path_at_commit,
            )
        register_snapshot(
            document=document,
            sha256=document.current_sha256,
            body=document.current_bytes,
            commit_sha=document.current_commit_sha,
            commit_url=document.current_commit_url,
            committed_at_label=document.current_committed_at_label,
            committed_at_iso=document.current_committed_at_iso,
            repo_path_at_commit=document.repo_path,
        )

    copy_assets(repo_root, config)
    copy_root_extras(repo_root, config)
    generate_favicons(repo_root, config)

    for document in documents:
        body_html, contents, heading_count = markdown_renderer.render(document.current_bytes.decode("utf-8", errors="replace"), document.repo_path)
        breadcrumbs = build_breadcrumbs_for_path(document.site_rel_path, is_directory=False, final_label=document.filename)
        context = {
            "page_title": f"{document.filename} - {config.site_title}",
            "section_title": document.section_title,
            "breadcrumbs": breadcrumbs,
            "body_class": "page-document",
            "document": document,
            "status_badges": [make_status_badge("Current version", "success")],
            "contents": contents if heading_count > 2 else [],
            "body_html": body_html,
            "print_header": {
                "project_title": config.site_title,
                "path": "/" + document.site_rel_path,
            },
        }
        render_template(
            environment,
            "document.html",
            output_path_for_relative(config.output_dir, document.canonical_html_rel_path),
            context,
        )
        target_raw_path = output_path_for_relative(config.output_dir, document.site_rel_path)
        ensure_parent(target_raw_path)
        target_raw_path.write_bytes(document.current_bytes)

        render_template(
            environment,
            "history.html",
            output_path_for_relative(config.output_dir, document.history_rel_path),
            {
                "page_title": f"{document.filename} History - {config.site_title}",
                "section_title": document.section_title,
                "breadcrumbs": breadcrumbs,
                "body_class": "page-history",
                "document": document,
            },
        )

    for snapshot in snapshots.values():
        body_html, contents, heading_count = markdown_renderer.render(snapshot.body.decode("utf-8", errors="replace"), snapshot.source_repo_path_at_commit)
        breadcrumbs = build_breadcrumbs_for_path(snapshot.breadcrumb_site_rel, is_directory=False, final_label=snapshot.canonical_filename)
        render_template(
            environment,
            "document.html",
            output_path_for_relative(config.output_dir, f"{snapshot.sha256}.html"),
            {
                "page_title": f"{snapshot.canonical_filename} Snapshot - {config.site_title}",
                "section_title": snapshot.section_title,
                "breadcrumbs": breadcrumbs,
                "body_class": "page-document page-snapshot",
                "snapshot": snapshot,
                "status_badges": snapshot.status_badges,
                "contents": contents if heading_count > 2 else [],
                "body_html": body_html,
                "print_header": {
                    "project_title": config.site_title,
                    "path": site_url(config, snapshot.canonical_url),
                },
            },
        )
        target_raw_path = output_path_for_relative(config.output_dir, f"{snapshot.sha256}.md")
        ensure_parent(target_raw_path)
        target_raw_path.write_bytes(snapshot.body)

    directory_pages: list[DirectoryPage] = []
    for repo_dir in sorted(all_repo_dirs):
        source_root = source_root_from_repo_path(repo_dir)
        site_dir_rel_path = site_rel_from_repo_path(repo_dir)
        if site_dir_rel_path == ".":
            site_dir_rel_path = ""
        title = "Home" if repo_dir == "Internal" else PurePosixPath(repo_dir).name
        page = DirectoryPage(
            repo_dir=repo_dir,
            site_dir_rel_path=site_dir_rel_path,
            source_root=source_root,
            readme_repo_path=readmes.get(repo_dir),
            title=title,
        )
        page.directory_entries = []
        page.document_entries = []
        directory_pages.append(page)

    directory_page_map = {page.repo_dir: page for page in directory_pages}
    for repo_dir, page in directory_page_map.items():
        repo_dir_path = PurePosixPath(repo_dir)
        child_dirs: list[str] = []
        for candidate in all_repo_dirs:
            candidate_path = PurePosixPath(candidate)
            if candidate == repo_dir:
                continue
            if candidate_path.parent == repo_dir_path:
                child_dirs.append(candidate)
        if repo_dir == "Internal" and "External" not in child_dirs:
            child_dirs.append("External")
        for child_dir in sorted(child_dirs, key=lambda value: value.lower()):
            child_site_rel = site_rel_from_repo_path(child_dir)
            page.directory_entries.append(
                DirectoryEntry(
                    label=PurePosixPath(child_dir).name,
                    url=to_directory_public_url(child_site_rel),
                    kind="directory",
                )
            )

        repo_dir_documents = [document for document in documents if document.parent_repo_dir == repo_dir]
        for document in sorted(repo_dir_documents, key=lambda item: item.filename.lower()):
            page.document_entries.append(
                DirectoryEntry(
                    label=document.filename,
                    url=document.canonical_html_url,
                    kind="document",
                    modified_at_label=document.current_committed_at_label,
                )
            )

    for page in directory_pages:
        readme_html = ""
        if page.readme_repo_path:
            readme_bytes = (repo_root / page.readme_repo_path).read_bytes()
            readme_html, _, _ = markdown_renderer.render(readme_bytes.decode("utf-8", errors="replace"), page.readme_repo_path)
        breadcrumbs = build_breadcrumbs_for_path(page.site_dir_rel_path, is_directory=True, final_label=page.title)
        render_template(
            environment,
            "index.html",
            output_path_for_directory(config.output_dir, page.site_dir_rel_path),
            {
                "page_title": f"{page.title} - {config.site_title}",
                "section_title": page.section_title,
                "breadcrumbs": breadcrumbs,
                "body_class": "page-index",
                "page": page,
                "readme_html": readme_html,
            },
        )

    for meta_page in meta_pages.values():
        body_html, _, _ = markdown_renderer.render(
            (repo_root / meta_page.repo_path).read_text(encoding="utf-8"),
            meta_page.repo_path,
        )
        site_dir_rel = site_rel_from_repo_path(str(PurePosixPath(meta_page.repo_path).parent))
        breadcrumbs = build_breadcrumbs_for_meta(site_dir_rel, meta_page.filename)
        render_template(
            environment,
            "meta.html",
            output_path_for_relative(config.output_dir, meta_page.site_rel_path),
            {
            "page_title": f"{meta_page.filename} - {config.site_title}",
                "section_title": "External Files" if meta_page.source_root == "External" else "Association Files",
                "breadcrumbs": breadcrumbs,
                "body_class": "page-meta",
                "meta_page": meta_page,
                "body_html": body_html,
            },
        )

    write_data_json(config, documents, snapshots)

    LOGGER.info("Generated %s documents", len(documents))
    LOGGER.info("Generated %s historical snapshots", len(snapshots))
    LOGGER.info("Build output: %s", config.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
