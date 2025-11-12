(() => {
  const VIEW_BUTTONS = document.querySelectorAll("[data-view-btn]");
  const PANELS = document.querySelectorAll("[data-panel]");
  const articleInput = document.getElementById("briefArticleInput");
  const articleCombobox = document.getElementById("briefArticleCombobox");
  const articleListbox = document.getElementById("briefArticleListbox");
  const comboboxOptions = articleListbox?.querySelector(".combobox-options");
  const comboboxLoading = articleListbox?.querySelector(".combobox-loading");
  const comboboxEmpty = articleListbox?.querySelector(".combobox-empty");
  const loadButton = document.getElementById("loadBriefButton");
  const refreshSummaryButton = document.getElementById("refreshBriefButton");
  const refreshImagesButton = document.getElementById("refreshImagesButton");
  const copyMarkdownButton = document.getElementById("copyMarkdownButton");
  const extractCardsButton = document.getElementById("extractCardsButton");
  const statusEl = document.querySelector("[data-brief-status]");
  const bodyEl = document.querySelector("[data-brief-body]");
  const titleEl = document.querySelector("[data-brief-title]");
  const subtitleEl = document.querySelector("[data-brief-subtitle]");
  const overviewEl = document.querySelector("[data-brief-overview]");
  const metricsEl = document.querySelector("[data-brief-metrics]");
  const sectionsEl = document.querySelector("[data-brief-sections]");
  const imagesGridEl = document.querySelector("[data-brief-images]");
  const imagesHintEl = document.querySelector("[data-brief-images-hint]");
  const markdownEl = document.querySelector("[data-brief-markdown]");
  const suggestionsList = document.getElementById("briefArticleSuggestions");
  const summaryTitleEl = document.querySelector("[data-brief-summary-title]");
  const flagsEl = document.querySelector("[data-brief-flags]");
  const highlightsSectionEl = document.querySelector("[data-brief-highlights-section]");
  const highlightsListEl = document.querySelector("[data-brief-highlights]");
  const quotesSectionEl = document.querySelector("[data-brief-quotes-section]");
  const quotesListEl = document.querySelector("[data-brief-quotes]");
  const stepsSectionEl = document.querySelector("[data-brief-steps-section]");
  const stepsListEl = document.querySelector("[data-brief-steps]");
  const articleSelect = document.getElementById("briefArticleSelect");
  const manualToggleButton = document.getElementById("briefManualToggle");
  const pickerContainer = document.querySelector("[data-brief-picker-container]");
  const manualContainer = document.querySelector("[data-brief-manual-container]");
  const articleListContainer = document.querySelector("[data-brief-article-list]");

  const LAST_ARTICLE_KEY = "kingfisher:last_brief_article";

  const state = {
    view: "cards",
    articleId: "",
    brief: null,
    loading: false,
    useManual: false,
    recentArticles: [],
    recentLoaded: false,
  };

  const DEFAULT_OVERVIEW_TEXT = "Overview will appear here once the brief loads.";

  function setView(view) {
    state.view = view;
    VIEW_BUTTONS.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.view === view);
    });
    PANELS.forEach((panel) => {
      const panelView = panel.dataset.panel;
      panel.style.display = panelView === view ? "" : "none";
      if (panelView === "brief") {
        panel.classList.toggle("active", panelView === view);
      }
    });

    if (view === "brief") {
      if (!state.brief) {
        statusEl.hidden = false;
        statusEl.textContent = state.articleId
          ? "Load the brief to see the summary and cards."
          : "Select a recent article or enter a Trove article ID to generate a brief.";
        bodyEl.classList.remove("active");
      }
      if (!state.recentLoaded) {
        loadRecentArticles();
      } else {
        renderRecentArticles(state.recentArticles);
      }
      setManualMode(state.useManual);
      // Ensure combobox is ready and shows if there are articles
      if (articleCombobox && state.recentArticles.length > 0) {
        updateComboboxOptions();
        // Show combobox dropdown if input has focus
        if (document.activeElement === articleCombobox) {
          openCombobox();
        }
      }
    }
  }

  function setManualMode(enabled) {
    state.useManual = Boolean(enabled);
    if (manualContainer) {
      manualContainer.hidden = !state.useManual;
    }
    if (pickerContainer) {
      pickerContainer.hidden = state.useManual;
    }
    if (manualToggleButton) {
      manualToggleButton.textContent = state.useManual ? "⬅ Back to dropdown" : "✏️ Enter ID manually";
    }
    if (state.useManual && articleInput) {
      articleInput.focus();
    }
  }

  function renderArticleStatusBadge(emoji, label, status) {
    const resolvedStatus = status === "cached" ? "cached" : "missing";
    const badge = document.createElement("span");
    badge.className = "brief-status-badge";
    badge.dataset.status = resolvedStatus;
    badge.textContent = `${emoji} ${label}`;
    badge.title = resolvedStatus === "cached" ? `${label} cached` : `${label} missing`;
    return badge;
  }

  function filterArticles(query, articles) {
    if (!query || !query.trim()) return articles;
    const q = query.toLowerCase().trim();
    return articles.filter((item) => {
      const title = (item.title || "").toLowerCase();
      const date = (item.date || "").toLowerCase();
      const source = (item.source || "").toLowerCase();
      const snippet = (item.snippet || "").toLowerCase();
      const id = (item.id || "").toLowerCase();
      return title.includes(q) || date.includes(q) || source.includes(q) || snippet.includes(q) || id.includes(q);
    });
  }

  function renderComboboxOptions(filteredItems, selectedId = null) {
    if (!comboboxOptions) return;
    
    comboboxOptions.innerHTML = "";
    
    if (filteredItems.length === 0) {
      if (comboboxEmpty) comboboxEmpty.hidden = false;
      return;
    }
    
    if (comboboxEmpty) comboboxEmpty.hidden = true;
    
    filteredItems.forEach((item) => {
      if (!item || !item.id) return;
      
      const option = document.createElement("div");
      option.className = "combobox-option";
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", item.id === selectedId ? "true" : "false");
      option.dataset.articleId = item.id;
      
      const titleEl = document.createElement("div");
      titleEl.className = "combobox-option-title";
      titleEl.textContent = `${item.pinned ? "📌 " : ""}${item.title || "Untitled"}`;
      option.appendChild(titleEl);
      
      const metaParts = [];
      if (item.date) metaParts.push(item.date);
      if (item.source) metaParts.push(item.source);
      if (metaParts.length) {
        const metaEl = document.createElement("div");
        metaEl.className = "combobox-option-meta";
        metaEl.textContent = metaParts.join(" • ");
        option.appendChild(metaEl);
      }
      
      if (item.snippet) {
        const snippetEl = document.createElement("div");
        snippetEl.className = "combobox-option-snippet";
        snippetEl.textContent = item.snippet;
        option.appendChild(snippetEl);
      }
      
      if (item.status) {
        const badgesEl = document.createElement("div");
        badgesEl.className = "combobox-option-badges";
        if (item.status.cards === "cached") {
          const badge = document.createElement("span");
          badge.className = "combobox-option-badge";
          badge.setAttribute("data-status", "cached");
          badge.textContent = "🃏 Cards";
          badgesEl.appendChild(badge);
        }
        if (item.status.summary === "cached") {
          const badge = document.createElement("span");
          badge.className = "combobox-option-badge";
          badge.setAttribute("data-status", "cached");
          badge.textContent = "🧠 Summary";
          badgesEl.appendChild(badge);
        }
        if (item.status.images === "cached") {
          const badge = document.createElement("span");
          badge.className = "combobox-option-badge";
          badge.setAttribute("data-status", "cached");
          badge.textContent = "🖼 Images";
          badgesEl.appendChild(badge);
        }
        if (badgesEl.children.length > 0) {
          option.appendChild(badgesEl);
        }
      }
      
      option.addEventListener("click", () => selectArticleFromCombobox(item.id));
      option.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          selectArticleFromCombobox(item.id);
        }
      });
      
      comboboxOptions.appendChild(option);
    });
  }

  function selectArticleFromCombobox(articleId) {
    if (!articleId) return;
    const item = state.recentArticles.find((a) => a.id === articleId || a.trove_id === articleId);
    if (item) {
      const id = item.id || item.trove_id || articleId;
      state.articleId = id;  // Set state immediately
      if (articleCombobox) {
        articleCombobox.value = item.title || id;
      }
      if (articleSelect) {
        articleSelect.value = id;
      }
      if (articleInput) {
        articleInput.value = id;
      }
      rememberArticleId(id);
      setManualMode(false);
      closeCombobox();
      fetchBrief({ refresh: false });
    }
  }

  function openCombobox() {
    if (!articleListbox) return;
    articleListbox.hidden = false;
    if (articleCombobox) {
      articleCombobox.setAttribute("aria-expanded", "true");
    }
    updateComboboxOptions();
  }

  function closeCombobox() {
    if (!articleListbox) return;
    articleListbox.hidden = true;
    if (articleCombobox) {
      articleCombobox.setAttribute("aria-expanded", "false");
    }
  }

  function updateComboboxOptions() {
    if (!articleCombobox || !state.recentArticles.length) return;
    
    const query = articleCombobox.value.trim();
    const filtered = filterArticles(query, state.recentArticles);
    renderComboboxOptions(filtered, state.articleId);
  }

  function renderRecentArticles(items, options = {}) {
    const data = Array.isArray(items) ? items : [];
    const message = options.message || "";
    
    // Transform API response to match frontend expectations
    // API returns: trove_id, has_summary, has_cards, has_images
    // Frontend expects: id, status.summary, status.cards, status.images
    const transformedData = data.map(item => ({
      ...item,
      id: item.id || item.trove_id,  // Ensure id exists
      status: {
        summary: item.has_summary ? "cached" : "missing",
        cards: item.has_cards ? "cached" : "missing",
        images: item.has_images ? "cached" : "missing",
      },
      pinned: item.pinned || false,
    }));
    
    state.recentArticles = transformedData;

    // Update combobox
    if (articleCombobox) {
      const currentQuery = articleCombobox.value.trim();
      const filtered = filterArticles(currentQuery, transformedData);
      renderComboboxOptions(filtered, state.articleId);
    }

    // Keep select updated for backward compatibility
    if (articleSelect) {
      const previousValue = articleSelect.value;
      const targetValue = state.articleId || previousValue || "";
      articleSelect.innerHTML = "";
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "— Select an article —";
      articleSelect.appendChild(placeholder);

      transformedData.forEach((item) => {
        if (!item || !item.id) return;
        const option = document.createElement("option");
        option.value = item.id;
        const title = item.title || "Untitled";
        const datePart = item.date ? ` (${item.date})` : "";
        const sourcePart = item.source ? ` – ${item.source}` : "";
        const prefix = item.pinned ? "📌 " : "";
        option.textContent = `${prefix}${title}${datePart}${sourcePart}`;
        articleSelect.appendChild(option);
      });

      if (targetValue && transformedData.some((item) => item.id === targetValue)) {
        articleSelect.value = targetValue;
        if (articleCombobox) {
          const selectedItem = transformedData.find((item) => item.id === targetValue);
          if (selectedItem) {
            articleCombobox.value = selectedItem.title || targetValue;
          }
        }
      } else {
        articleSelect.value = "";
      }
    }

    if (!articleListContainer) return;

    articleListContainer.innerHTML = "";

    if (message) {
      const msgEl = document.createElement("p");
      msgEl.className = "hint";
      msgEl.textContent = message;
      articleListContainer.appendChild(msgEl);
      return;
    }

    if (!transformedData.length) {
      const emptyEl = document.createElement("p");
      emptyEl.className = "hint";
      emptyEl.textContent = "No recent articles yet. Track a Trove article to see it here.";
      articleListContainer.appendChild(emptyEl);
      return;
    }

    transformedData.forEach((item) => {
      if (!item || !item.id) return;
      const card = document.createElement("article");
      card.className = "brief-article-item";
      card.tabIndex = 0;

      const titleEl = document.createElement("h4");
      titleEl.textContent = `${item.pinned ? "📌 " : ""}${item.title || "Untitled"}`;
      card.appendChild(titleEl);

      const metaParts = [];
      if (item.date) metaParts.push(item.date);
      if (item.source) metaParts.push(item.source);
      if (item.pinned) metaParts.push("Pinned");
      if (metaParts.length) {
        const metaEl = document.createElement("div");
        metaEl.className = "brief-article-meta";
        metaEl.textContent = metaParts.join(" • ");
        card.appendChild(metaEl);
      }

      if (item.snippet) {
        const snippetEl = document.createElement("div");
        snippetEl.className = "brief-article-snippet";
        snippetEl.textContent = item.snippet;
        card.appendChild(snippetEl);
      }

      const badgesEl = document.createElement("div");
      badgesEl.className = "brief-article-badges";
      badgesEl.appendChild(renderArticleStatusBadge("🃏", "Cards", item.status?.cards));
      badgesEl.appendChild(renderArticleStatusBadge("🧠", "Summary", item.status?.summary));
      badgesEl.appendChild(renderArticleStatusBadge("🖼", "Images", item.status?.images));
      card.appendChild(badgesEl);

      const selectArticle = () => {
        if (!item.id) return;
        if (articleSelect) {
          articleSelect.value = item.id;
        }
        if (articleInput) {
          articleInput.value = item.id;
        }
        rememberArticleId(item.id);
        setManualMode(false);
        fetchBrief({ refresh: false });
      };

      card.addEventListener("click", selectArticle);
      card.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          selectArticle();
        }
      });

      articleListContainer.appendChild(card);
    });
  }

  async function loadRecentArticles(force = false) {
    if (!force && state.recentLoaded) {
      renderRecentArticles(state.recentArticles);
      return;
    }

    try {
      const response = await fetch("/api/brief/articles");
      if (!response.ok) {
        throw new Error(`Request failed (${response.status})`);
      }
      const payload = await response.json();
      const articles = Array.isArray(payload) ? payload : [];
      state.recentLoaded = true;
      renderRecentArticles(articles);
      
      // If combobox is focused and we have articles, show dropdown
      if (articleCombobox && articles.length > 0 && document.activeElement === articleCombobox) {
        openCombobox();
      }
    } catch (error) {
      console.warn("Failed to load recent articles:", error);
      state.recentArticles = [];
      state.recentLoaded = true;
      renderRecentArticles([], { message: "Unable to load recent articles right now." });
    }
  }

  function setSummaryList(sectionEl, listEl, items, options = {}) {
    if (!sectionEl || !listEl) return;
    listEl.innerHTML = "";
    const normalized = (items || [])
      .map((item) => {
        if (typeof item === "string") return item.trim();
        if (item === null || item === undefined) return "";
        return String(item).trim();
      })
      .filter(Boolean);
    if (!normalized.length) {
      sectionEl.hidden = true;
      return;
    }
    sectionEl.hidden = false;
    normalized.forEach((entry) => {
      const li = document.createElement("li");
      if (typeof options.render === "function") {
        const rendered = options.render(entry);
        if (rendered instanceof Node) {
          li.appendChild(rendered);
        } else if (typeof rendered === "string") {
          li.textContent = rendered;
        } else {
          li.textContent = entry;
        }
      } else {
        li.textContent = entry;
      }
      listEl.appendChild(li);
    });
  }

  function clearSummarySections() {
    if (summaryTitleEl) {
      summaryTitleEl.hidden = true;
      summaryTitleEl.textContent = "";
    }
    if (flagsEl) {
      flagsEl.innerHTML = "";
      flagsEl.hidden = true;
    }
    if (overviewEl) {
      overviewEl.textContent = DEFAULT_OVERVIEW_TEXT;
    }
    setSummaryList(highlightsSectionEl, highlightsListEl, []);
    setSummaryList(quotesSectionEl, quotesListEl, []);
    setSummaryList(stepsSectionEl, stepsListEl, []);
  }

  function setLoading(isLoading, message) {
    state.loading = isLoading;
    if (isLoading) {
      statusEl.textContent = message || "Loading brief…";
      statusEl.hidden = false;
      bodyEl.classList.remove("active");
      clearSummarySections();
    } else {
      statusEl.hidden = true;
    }
    loadButton.disabled = isLoading;
    refreshSummaryButton.disabled = isLoading || !state.articleId;
    refreshImagesButton.disabled = isLoading || !state.articleId;
    if (extractCardsButton) extractCardsButton.disabled = isLoading || !state.brief;
    copyMarkdownButton.disabled = isLoading || !markdownEl.value.trim();
  }

  function formatDateTime(timestamp) {
    if (!timestamp) return "";
    try {
      const date = new Date(Number(timestamp) * 1000);
      if (Number.isNaN(date.getTime())) return "";
      return date.toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      });
    } catch {
      return "";
    }
  }

  function updateMetrics(brief) {
    metricsEl.innerHTML = "";
    const fragments = [];

    const sourceCounts = brief.image_sources || {};
    const cardCounts = brief.card_type_counts || {};
    const totalCards = brief.summary?.card_count ?? 0;
    const cached = brief.summary?.cached;

    fragments.push(`Cards: ${totalCards}`);
    fragments.push(cached ? "Summary: cached" : "Summary: fresh");
    const generatedImages = brief.images.filter((img) => img.generated).length;
    const realImages = brief.images.length - generatedImages;

    if (realImages > 0) fragments.push(`Images: ${realImages} from Trove`);
    if (generatedImages > 0) fragments.push(`Images: ${generatedImages} generated`);

    Object.entries(cardCounts).forEach(([type, count]) => {
      const pill = document.createElement("span");
      pill.className = "metric-pill";
      pill.textContent = `${type}: ${count}`;
      metricsEl.appendChild(pill);
    });

    Object.entries(sourceCounts).forEach(([source, count]) => {
      const pill = document.createElement("span");
      pill.className = "metric-pill";
      pill.textContent = `${source}: ${count}`;
      metricsEl.appendChild(pill);
    });

    fragments.forEach((text) => {
      const pill = document.createElement("span");
      pill.className = "metric-pill";
      pill.textContent = text;
      metricsEl.appendChild(pill);
    });
  }

  function renderSections(brief) {
    sectionsEl.innerHTML = "";
    const sections = brief.sections || [];
    if (!sections.length) {
      sectionsEl.innerHTML =
        '<p class="hint">No cards found for this article yet. Extract Kingfisher cards and try again.</p>';
      return;
    }

    sections.forEach((section) => {
      if (!section.cards || !section.cards.length) return;

      const sectionEl = document.createElement("div");
      sectionEl.className = "brief-section";

      const heading = document.createElement("h4");
      heading.textContent = section.heading || section.card_type || "Section";
      sectionEl.appendChild(heading);

      const list = document.createElement("ul");
      section.cards.forEach((card) => {
        const item = document.createElement("li");
        const metaBits = [];
        if (card.metadata) {
          ["date", "source", "page", "location", "person"].forEach((key) => {
            if (card.metadata[key]) metaBits.push(`${key}: ${card.metadata[key]}`);
          });
        }
        const title = card.title ? `**${card.title}** — ` : "";
        item.innerHTML = `${title}${card.content || ""}`;
        if (metaBits.length) {
          const meta = document.createElement("div");
          meta.className = "hint";
          meta.textContent = metaBits.join(" • ");
          item.appendChild(meta);
        }
        list.appendChild(item);
      });

      sectionEl.appendChild(list);
      sectionsEl.appendChild(sectionEl);
    });
  }

  function renderImages(brief) {
    imagesGridEl.innerHTML = "";
    const images = brief.images || [];
    if (!images.length) {
      imagesHintEl.hidden = false;
      return;
    }
    imagesHintEl.hidden = true;

    images.forEach((image, index) => {
      const card = document.createElement("article");
      card.className = "brief-image-card";

      const imgEl = document.createElement("img");
      imgEl.alt = image.metadata?.article_title || `Brief image ${index + 1}`;
      imgEl.src = image.local_path || image.url || image.source || "";
      card.appendChild(imgEl);

      const metaWrapper = document.createElement("div");
      metaWrapper.className = "image-meta";
      const label = document.createElement("strong");
      label.textContent = (image.kind || "alternate").replace(/_/g, " ");
      metaWrapper.appendChild(label);
      const source = document.createElement("span");
      source.textContent = image.generated
        ? "Generated illustration"
        : image.source || "Trove";
      metaWrapper.appendChild(source);
      card.appendChild(metaWrapper);

      imagesGridEl.appendChild(card);
    });
  }

  function renderSummaryDetails(brief) {
    clearSummarySections();
    if (!brief || !brief.summary) {
      return;
    }

    const summaryPayload = brief.summary;
    const summaryBody = summaryPayload.summary;
    const structured =
      summaryBody && typeof summaryBody === "object" && !Array.isArray(summaryBody) ? summaryBody : null;

    if (summaryTitleEl) {
      if (structured?.title) {
        summaryTitleEl.hidden = false;
        summaryTitleEl.textContent = structured.title;
      } else {
        summaryTitleEl.hidden = true;
        summaryTitleEl.textContent = "";
      }
    }

    const overviewCandidates = [
      structured?.overview,
      summaryPayload.summary_text,
      typeof summaryBody === "string" ? summaryBody : "",
    ];
    const overview = overviewCandidates.find((entry) => typeof entry === "string" && entry.trim());
    if (overviewEl) {
      overviewEl.textContent = overview ? overview.trim() : "No summary available.";
    }

    if (flagsEl) {
      const addBadge = (text, tone = "muted") => {
        if (!text) return;
        const badge = document.createElement("span");
        badge.className = "summary-badge";
        badge.dataset.tone = tone;
        badge.textContent = text;
        flagsEl.appendChild(badge);
      };

      const cardCount = Number(summaryPayload.card_count || 0);
      if (cardCount === 0) {
        addBadge("No cards yet", "warning");
      } else if (brief.generated_cards) {
        addBadge("Cards generated just now", "info");
      } else {
        addBadge("Using stored cards", "muted");
      }

      if (summaryPayload.cached) {
        addBadge("Summary cached", "muted");
      } else if (cardCount > 0) {
        addBadge("Summary refreshed", "success");
      }

      if (summaryPayload.generated_at) {
        addBadge(`Updated ${formatDateTime(summaryPayload.generated_at)}`, "muted");
      }

      flagsEl.hidden = flagsEl.childElementCount === 0;
    }

    const toArray = (value) => {
      if (!value) return [];
      if (Array.isArray(value)) return value;
      if (typeof value === "string") return value.trim() ? [value.trim()] : [];
      return [];
    };

    setSummaryList(highlightsSectionEl, highlightsListEl, toArray(structured?.highlights));
    setSummaryList(
      quotesSectionEl,
      quotesListEl,
      toArray(structured?.notable_quotes),
      {
        render(text) {
          const span = document.createElement("span");
          span.textContent = text;
          return span;
        },
      },
    );
    setSummaryList(stepsSectionEl, stepsListEl, toArray(structured?.next_steps));
  }

  function renderBrief(brief) {
    state.brief = brief;
    state.articleId = brief.article.article_id || state.articleId;
    if (state.articleId) {
      articleInput.value = state.articleId;
      localStorage.setItem(LAST_ARTICLE_KEY, state.articleId);
      rememberArticleId(state.articleId);
    }

    titleEl.textContent = brief.article.title || "Article brief";
    const subtitleParts = [];
    if (brief.article.date) subtitleParts.push(brief.article.date);
    if (brief.article.source) subtitleParts.push(brief.article.source);
    subtitleEl.textContent = subtitleParts.join(" • ");

    renderSummaryDetails(brief);
    updateMetrics(brief);
    renderSections(brief);
    renderImages(brief);

    if (brief.markdown) {
      markdownEl.value = brief.markdown;
      copyMarkdownButton.disabled = false;
    } else {
      markdownEl.value = "";
      copyMarkdownButton.disabled = true;
    }

    refreshSummaryButton.disabled = false;
    refreshImagesButton.disabled = false;
    if (extractCardsButton) extractCardsButton.disabled = false;
    bodyEl.classList.add("active");
    loadRecentArticles(true);
  }

  async function fetchBrief(options = {}) {
    // Prefer state.articleId, fallback to input fields
    const articleId = (state.articleId || articleInput?.value || articleSelect?.value || articleCombobox?.value || "").trim();
    if (!articleId) {
      statusEl.hidden = false;
      statusEl.textContent = "Please enter a Trove article ID.";
      if (articleInput) articleInput.focus();
      return;
    }

    state.articleId = articleId;
    // Sync all input fields
    if (articleInput) articleInput.value = articleId;
    if (articleSelect) articleSelect.value = articleId;
    setLoading(true, "Building brief…");
    const params = new URLSearchParams();
    if (options.refresh) params.set("refresh", "1");
    if (options.refreshSummary) params.set("refresh_summary", "1");
    if (options.refreshImages) params.set("refresh_images", "1");
    if (options.includeMarkdown === false) params.set("include_markdown", "0");

    try {
      const resp = await fetch(`/api/brief/${encodeURIComponent(articleId)}?${params.toString()}`);
      if (!resp.ok) {
        throw new Error(`Request failed (${resp.status})`);
      }
      const data = await resp.json();
      if (!data?.ok) {
        throw new Error(data?.error || "Failed to build brief.");
      }
      renderBrief(data);
      setLoading(false);
    } catch (err) {
      setLoading(false);
      bodyEl.classList.remove("active");
      statusEl.hidden = false;
      statusEl.textContent = `Unable to build brief: ${err.message}`;
    }
  }

  async function extractCardsFromBrief() {
    if (!state.brief || !state.brief.article) {
      if (typeof showToast === "function") {
        showToast("No brief loaded. Load a brief first.", "error");
      } else {
        alert("No brief loaded. Load a brief first.");
      }
      return;
    }

    const article = state.brief.article;
    const text = article.full_text || article.text || article.snippet || "";
    
    if (!text || !text.trim()) {
      if (typeof showToast === "function") {
        showToast("No article text available for extraction.", "error");
      } else {
        alert("No article text available for extraction.");
      }
      return;
    }

    if (extractCardsButton) {
      extractCardsButton.disabled = true;
      extractCardsButton.textContent = "Extracting...";
    }

    try {
      const response = await fetch("/api/kingfisher/extract-cards", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: text,
          metadata: {
            title: article.title,
            date: article.date,
            source: article.source,
          },
          use_llm: true,
        }),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
        throw new Error(error.detail || `Request failed (${response.status})`);
      }

      const data = await response.json();
      
      if (!data.ok) {
        throw new Error(data.error || "Extraction failed");
      }

      const cardCount = data.count || 0;
      const method = data.method || "unknown";
      
      if (cardCount > 0) {
        const message = `Extracted ${cardCount} cards using ${method} method`;
        if (typeof showToast === "function") {
          showToast(message, "success");
        } else {
          alert(message);
        }
        // Refresh the brief to show new cards
        fetchBrief({ refresh: true });
      } else {
        const message = "No cards extracted. Try with a longer article text.";
        if (typeof showToast === "function") {
          showToast(message, "warning");
        } else {
          alert(message);
        }
      }
    } catch (error) {
      console.error("Card extraction error:", error);
      const message = `Extraction failed: ${error.message}`;
      if (typeof showToast === "function") {
        showToast(message, "error");
      } else {
        alert(message);
      }
    } finally {
      if (extractCardsButton) {
        extractCardsButton.disabled = false;
        extractCardsButton.textContent = "🃏 Extract Cards";
      }
    }
  }

  function copyMarkdown() {
    if (!markdownEl.value) return;
    navigator.clipboard
      .writeText(markdownEl.value)
      .then(() => {
        copyMarkdownButton.textContent = "Copied!";
        setTimeout(() => (copyMarkdownButton.textContent = "Copy Markdown"), 1800);
      })
      .catch(() => {
        copyMarkdownButton.textContent = "Copy failed";
        setTimeout(() => (copyMarkdownButton.textContent = "Copy Markdown"), 1800);
      });
  }

  function hydrateSuggestions() {
    if (!suggestionsList) return;
    const stored = JSON.parse(localStorage.getItem("kingfisher:brief_history") || "[]");
    suggestionsList.innerHTML = "";
    stored.forEach((entry) => {
      const option = document.createElement("option");
      option.value = entry;
      suggestionsList.appendChild(option);
    });
  }

  function rememberArticleId(articleId) {
    try {
      const existing = JSON.parse(localStorage.getItem("kingfisher:brief_history") || "[]");
      const next = [articleId, ...existing.filter((entry) => entry !== articleId)].slice(0, 8);
      localStorage.setItem("kingfisher:brief_history", JSON.stringify(next));
      hydrateSuggestions();
    } catch {
      /* ignore */
    }
  }

  function init() {
    VIEW_BUTTONS.forEach((btn) => {
      btn.addEventListener("click", () => setView(btn.dataset.view));
    });

    manualToggleButton?.addEventListener("click", () => {
      setManualMode(!state.useManual);
    });

    loadButton?.addEventListener("click", () => {
      fetchBrief({ refresh: false });
    });

    refreshSummaryButton?.addEventListener("click", () => {
      fetchBrief({ refreshSummary: true });
    });

    refreshImagesButton?.addEventListener("click", () => {
      fetchBrief({ refreshImages: true });
    });

    extractCardsButton?.addEventListener("click", extractCardsFromBrief);

    copyMarkdownButton?.addEventListener("click", copyMarkdown);

    articleInput?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        loadButton.click();
      }
    });

    // Combobox event handlers
    if (articleCombobox) {
      articleCombobox.addEventListener("focus", () => {
        if (state.recentArticles.length > 0) {
          openCombobox();
        }
      });

      articleCombobox.addEventListener("input", () => {
        updateComboboxOptions();
        if (articleListbox) {
          articleListbox.hidden = false;
        }
      });

      articleCombobox.addEventListener("blur", (e) => {
        // Delay closing to allow option clicks
        setTimeout(() => {
          if (!articleListbox?.contains(document.activeElement)) {
            closeCombobox();
          }
        }, 200);
      });

      articleCombobox.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          closeCombobox();
          articleCombobox.blur();
        } else if (e.key === "ArrowDown") {
          e.preventDefault();
          const firstOption = comboboxOptions?.querySelector(".combobox-option");
          if (firstOption) {
            firstOption.focus();
            firstOption.setAttribute("aria-selected", "true");
          }
        } else if (e.key === "Enter" && articleCombobox.value.trim()) {
          // Try to find matching article
          const query = articleCombobox.value.trim();
          const match = state.recentArticles.find(
            (item) =>
              item.id === query ||
              (item.title || "").toLowerCase() === query.toLowerCase()
          );
          if (match) {
            e.preventDefault();
            selectArticleFromCombobox(match.id);
          } else {
            // Fallback: treat as manual ID entry
            if (articleInput) {
              articleInput.value = query;
              state.articleId = query;
              fetchBrief({ refresh: false });
            }
          }
        }
      });
    }

    // Close combobox when clicking outside
    document.addEventListener("click", (e) => {
      if (
        articleListbox &&
        !articleCombobox?.contains(e.target) &&
        !articleListbox.contains(e.target)
      ) {
        closeCombobox();
      }
    });

    articleSelect?.addEventListener("change", (event) => {
      const selectedId = event.target.value;
      if (articleInput) {
        articleInput.value = selectedId || "";
      }
      if (articleCombobox) {
        const item = state.recentArticles.find((a) => a.id === selectedId);
        if (item) {
          articleCombobox.value = item.title || selectedId;
        } else {
          articleCombobox.value = selectedId || "";
        }
      }
      if (!selectedId) {
        return;
      }
      rememberArticleId(selectedId);
      setManualMode(false);
      fetchBrief({ refresh: false });
    });

    hydrateSuggestions();
    const lastArticle = localStorage.getItem(LAST_ARTICLE_KEY);
    if (lastArticle) {
      if (articleInput) {
        articleInput.value = lastArticle;
      }
      if (articleCombobox) {
        // Will be set when articles load
        state.articleId = lastArticle;
      }
    }

    // Load recent articles for combobox
    if (state.view === "brief" || !state.view) {
      loadRecentArticles();
    }

    clearSummarySections();
    setManualMode(false);
    setView("cards");
  }

  document.addEventListener("DOMContentLoaded", init);
})();

