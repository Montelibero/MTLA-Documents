(function () {
  const root = document.querySelector("[data-search-root]");
  if (!root) {
    return;
  }

  const form = root.querySelector(".search-form");
  const input = root.querySelector("[data-search-input]");
  const submitButton = root.querySelector("[data-search-submit]");
  const resultsContainer = root.querySelector("[data-search-results]");
  const indexUrl = root.dataset.indexUrl;
  const minisearchUrl = root.dataset.minisearchUrl;

  if (!form || !input || !submitButton || !resultsContainer || !indexUrl || !minisearchUrl) {
    return;
  }

  let searchRuntime = null;
  let loadPromise = null;
  let renderedResults = [];
  let activeIndex = -1;
  let latestQuery = "";

  function expandTerms(value) {
    return value
      .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
      .replace(/[._/-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function loadScript(url) {
    if (window.MiniSearch) {
      return Promise.resolve();
    }
    return new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[data-search-lib="${url}"]`);
      if (existing) {
        existing.addEventListener("load", () => resolve(), { once: true });
        existing.addEventListener("error", () => reject(new Error(`Failed to load ${url}`)), { once: true });
        return;
      }

      const script = document.createElement("script");
      script.src = url;
      script.async = true;
      script.dataset.searchLib = url;
      script.addEventListener("load", () => resolve(), { once: true });
      script.addEventListener("error", () => reject(new Error(`Failed to load ${url}`)), { once: true });
      document.head.appendChild(script);
    });
  }

  function buildSearchRecords(documents) {
    const records = [];
    for (const documentRecord of documents) {
      records.push({
        id: `${documentRecord.canonical_key}::document`,
        docKey: documentRecord.canonical_key,
        kind: "document",
        filename: documentRecord.filename,
        filename_terms: expandTerms(documentRecord.filename),
        path: documentRecord.canonical_key,
        path_terms: expandTerms(documentRecord.canonical_key),
        h1: documentRecord.h1 || "",
        heading_l2: "",
        heading_l3: "",
        headingText: "",
        level: 0,
        url: documentRecord.url,
        isExternal: Boolean(documentRecord.is_external),
      });

      for (const heading of documentRecord.headings || []) {
        const headingRecord = {
          id: `${documentRecord.canonical_key}::${heading.anchor}`,
          docKey: documentRecord.canonical_key,
          kind: "heading",
          filename: documentRecord.filename,
          filename_terms: expandTerms(documentRecord.filename),
          path: documentRecord.canonical_key,
          path_terms: expandTerms(documentRecord.canonical_key),
          h1: documentRecord.h1 || "",
          heading_l2: "",
          heading_l3: "",
          headingText: heading.text,
          level: heading.level,
          url: `${documentRecord.url}#${heading.anchor}`,
          isExternal: Boolean(documentRecord.is_external),
        };

        if (heading.level === 1) {
          headingRecord.h1 = heading.text;
        } else if (heading.level === 2) {
          headingRecord.heading_l2 = heading.text;
        } else {
          headingRecord.heading_l3 = heading.text;
        }

        records.push(headingRecord);
      }
    }

    return records;
  }

  async function ensureSearchRuntime() {
    if (searchRuntime) {
      return searchRuntime;
    }
    if (!loadPromise) {
      loadPromise = Promise.all([
        loadScript(minisearchUrl),
        fetch(indexUrl, { credentials: "same-origin" }).then((response) => {
          if (!response.ok) {
            throw new Error(`Failed to load search index: ${response.status}`);
          }
          return response.json();
        }),
      ]).then(([, payload]) => {
        const miniSearch = new window.MiniSearch({
          fields: ["filename_terms", "path_terms", "h1", "heading_l2", "heading_l3"],
          storeFields: ["docKey", "kind", "filename", "path", "h1", "headingText", "level", "url", "isExternal"],
        });
        miniSearch.addAll(buildSearchRecords(payload.documents || []));
        searchRuntime = { miniSearch };
        return searchRuntime;
      });
    }
    return loadPromise;
  }

  function buildScopeQuery(term) {
    const basePath = (document.body.dataset.siteBasePath || "/").replace(/^\/|\/$/g, "");
    const parts = [`site:${window.location.hostname}`];
    if (basePath) {
      parts.push(`"${basePath}"`);
    }
    parts.push(term);
    return parts.join(" ");
  }

  function chooseBetterResult(candidate, existing) {
    if (!existing) {
      return candidate;
    }
    if (candidate.score !== existing.score) {
      return candidate.score > existing.score ? candidate : existing;
    }
    if (candidate.isExternal !== existing.isExternal) {
      return candidate.isExternal ? existing : candidate;
    }
    if (candidate.kind !== existing.kind) {
      return candidate.kind === "heading" ? candidate : existing;
    }
    if (candidate.level !== existing.level) {
      return candidate.level < existing.level ? candidate : existing;
    }
    return candidate;
  }

  function searchDocuments(query) {
    const results = searchRuntime.miniSearch.search(query, {
      prefix: query.length >= 2,
      combineWith: "OR",
      boost: {
        filename_terms: 10,
        path_terms: 3,
        h1: 6,
        heading_l2: 4,
        heading_l3: 2,
      },
    });

    const grouped = new Map();
    for (const result of results) {
      const candidate = {
        docKey: result.docKey,
        url: result.url,
        filename: result.filename,
        path: result.path,
        h1: result.h1 || "",
        headingText: result.headingText || "",
        kind: result.kind,
        level: result.level || 0,
        isExternal: Boolean(result.isExternal),
        score: result.score,
      };
      grouped.set(candidate.docKey, chooseBetterResult(candidate, grouped.get(candidate.docKey)));
    }

    return Array.from(grouped.values());
  }

  function clearResults() {
    renderedResults = [];
    activeIndex = -1;
    resultsContainer.hidden = true;
    resultsContainer.innerHTML = "";
  }

  function renderSection(title, items, startIndex) {
    if (!items.length) {
      return startIndex;
    }

    if (title) {
      const label = document.createElement("div");
      label.className = "search-results__section-title";
      label.textContent = title;
      resultsContainer.appendChild(label);
    }

    for (const item of items) {
      const link = document.createElement("a");
      link.className = "search-result";
      link.href = item.url;
      link.dataset.resultIndex = String(startIndex);

      const filename = document.createElement("span");
      filename.className = "search-result__filename";
      filename.textContent = item.filename;
      link.appendChild(filename);

      if (item.headingText) {
        const heading = document.createElement("span");
        heading.className = "search-result__heading";
        heading.textContent = item.headingText;
        link.appendChild(heading);
      }

      if (item.h1) {
        const context = document.createElement("span");
        context.className = "search-result__context";
        context.textContent = item.h1;
        link.appendChild(context);
      }

      const path = document.createElement("span");
      path.className = "search-result__path";
      path.textContent = item.path;
      link.appendChild(path);

      link.addEventListener("mouseenter", () => setActiveResult(startIndex));
      resultsContainer.appendChild(link);
      startIndex += 1;
    }

    return startIndex;
  }

  function setActiveResult(index) {
    activeIndex = index;
    const nodes = resultsContainer.querySelectorAll(".search-result");
    nodes.forEach((node) => {
      node.classList.toggle("is-active", Number(node.dataset.resultIndex) === activeIndex);
    });
  }

  function renderResults(items) {
    renderedResults = items;
    resultsContainer.innerHTML = "";

    if (!items.length) {
      const emptyState = document.createElement("div");
      emptyState.className = "search-results__empty";
      emptyState.textContent = "No local matches. Use Search for DuckDuckGo.";
      resultsContainer.appendChild(emptyState);
      resultsContainer.hidden = false;
      activeIndex = -1;
      return;
    }

    const internal = items.filter((item) => !item.isExternal);
    const external = items.filter((item) => item.isExternal);

    let index = 0;
    index = renderSection("", internal, index);
    if (internal.length && external.length) {
      const divider = document.createElement("div");
      divider.className = "search-results__divider";
      resultsContainer.appendChild(divider);
    }
    renderSection("External Files", external, index);

    resultsContainer.hidden = false;
    setActiveResult(0);
  }

  function navigateToResult(index) {
    const result = renderedResults[index];
    if (!result) {
      return;
    }
    window.location.assign(result.url);
  }

  async function updateResults() {
    const query = input.value.trim();
    latestQuery = query;

    if (query.length < 2) {
      clearResults();
      return;
    }

    try {
      await ensureSearchRuntime();
    } catch (error) {
      console.error(error);
      clearResults();
      return;
    }

    if (latestQuery !== query) {
      return;
    }

    renderResults(searchDocuments(query));
  }

  input.addEventListener("focus", () => {
    ensureSearchRuntime().catch((error) => console.error(error));
  });

  input.addEventListener("input", () => {
    updateResults().catch((error) => console.error(error));
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" && renderedResults.length) {
      event.preventDefault();
      setActiveResult((activeIndex + 1) % renderedResults.length);
      return;
    }

    if (event.key === "ArrowUp" && renderedResults.length) {
      event.preventDefault();
      setActiveResult((activeIndex - 1 + renderedResults.length) % renderedResults.length);
      return;
    }

    if (event.key === "Escape") {
      clearResults();
      return;
    }

    if (event.key === "Enter" && input.value.trim().length >= 2) {
      event.preventDefault();
      if (renderedResults.length) {
        navigateToResult(activeIndex >= 0 ? activeIndex : 0);
      }
    }
  });

  document.addEventListener("click", (event) => {
    if (!root.contains(event.target)) {
      clearResults();
    }
  });

  form.addEventListener("submit", (event) => {
    if (event.submitter !== submitButton) {
      return;
    }
    const query = input.value.trim();
    if (!query) {
      return;
    }
    input.value = buildScopeQuery(query);
  });
})();
