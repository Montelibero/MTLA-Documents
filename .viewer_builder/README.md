# Viewer Builder

Static site generator for the Montelibero document viewer.

## Local build

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

## Local preview

Build first, then start the local preview server:

```bash
python3 .viewer_builder/scripts/serve.py
```

By default the config uses the GitHub Pages project base path `/MTLA-Documents`, so the preview URL is:

```text
http://127.0.0.1:8000/MTLA-Documents/
```
