# Viewer Builder

Static site generator for the Montelibero document viewer.

## Local build

Requires Python 3.10 or newer.

Native Python build:

```bash
python3 -m venv .viewer_builder/.venv
.viewer_builder/.venv/bin/pip install -r .viewer_builder/requirements.txt
.viewer_builder/.venv/bin/python .viewer_builder/scripts/build.py
```

If your local Python already has the required packages installed, the short form also works:

```bash
python3 .viewer_builder/scripts/build.py
```

The generated site goes to `.viewer_builder/.output/site/`.

To protect repository files, `--output-dir` accepts only a child directory of
`.viewer_builder/.output/`. For example:

```bash
python3 .viewer_builder/scripts/build.py --output-dir .viewer_builder/.output/preview
```

The builder may fully remove the selected directory before generating the site.

Symbolic links are not supported anywhere under `Internal/` or `External/`,
and Markdown sources must be regular files. The build rejects links instead of
following their targets or publishing content that differs from the Git blob.

Before replacing an existing build, the builder validates the complete output
manifest. Duplicate or case-equivalent targets and file-versus-directory
conflicts stop the build and leave the previous generated site untouched.

After generation, local links, asset references, and HTML anchors are checked
against the output manifest. External URLs are not requested, and outgoing
links in immutable historical snapshot pages do not block a current build.

Raw HTML in Markdown is escaped and displayed as text. Use Markdown syntax for
formatting; repository content cannot inject executable tags or attributes into
generated pages.

## Local preview

Build first, then start the local preview server:

```bash
python3 .viewer_builder/scripts/serve.py
```

By default the config uses the GitHub Pages project base path `/MTLA-Documents`, so the preview URL is:

```text
http://127.0.0.1:8000/MTLA-Documents/
```
