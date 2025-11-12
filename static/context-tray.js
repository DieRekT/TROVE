/**
 * Context Tray - Vanilla JS implementation
 * Provides pin/unpin UI and context management for the chat interface
 * 
 * Features:
 * - Auto-collects articles you interact with (hover/preview/open)
 * - De-dupes across repeated queries
 * - Tracks articles (ephemeral) vs Pins (persistent)
 * - Export to CSV/JSON
 * - Clear tracked (keeps pinned)
 */

// Configuration
const TRACKED_MAX = 50;
const CLEAR_TRACKED_ON_NEW_QUERY = false; // Set to true to auto-clear on new search

class ContextTray {
  constructor(container) {
    this.container = container;
    this.isOpen = false;
    this.articles = [];
    this.loading = false;
    this.init();
  }

  init() {
    this.render();
    this.attachEventListeners();
    // Auto-fetch stats on init to show count
    this.fetchStats();
    // Listen for article-tracked events to auto-refresh
    window.addEventListener('article-tracked', () => {
      this.refresh();
    });
    // Listen for tracked-cleared events
    window.addEventListener('tracked-cleared', () => {
      this.refresh();
    });
  }

  async fetchContext() {
    this.loading = true;
    this.updateLoadingState();
    try {
      const res = await fetch('/api/context');
      const data = await res.json();
      if (data.ok) {
        this.articles = data.items || [];
        // Also update stats when fetching context
        await this.fetchStats();
        this.render();
      }
    } catch (error) {
      console.error('Failed to fetch context:', error);
    } finally {
      this.loading = false;
      this.updateLoadingState();
    }
  }
  
  async onNewSearchStarted() {
    if (CLEAR_TRACKED_ON_NEW_QUERY) {
      try {
        await fetch('/api/context/tracked', { method: 'DELETE' });
        await this.fetchContext();
        await this.fetchStats();
        console.log('Cleared tracked articles on new search');
      } catch (error) {
        console.error('Failed to clear tracked on new search:', error);
      }
    }
  }
  
  async refresh() {
    await this.fetchContext();
    await this.fetchStats();
  }

  async fetchStats() {
    try {
      const res = await fetch('/api/context/stats');
      const data = await res.json();
      if (data.ok) {
        this.stats = {
          pinned: data.pinned || 0,
          tracked: data.tracked || 0,
          total: data.total || 0
        };
        this.render();
      }
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  }

  async handlePin(troveId, pinned) {
    try {
      const endpoint = pinned 
        ? `/api/context/pin/${troveId}` 
        : `/api/context/unpin/${troveId}`;
      await fetch(endpoint, { method: 'POST' });
      await this.fetchContext();
      await this.fetchStats();
    } catch (error) {
      console.error('Failed to pin/unpin:', error);
    }
  }

  async handleMove(troveId, direction) {
    try {
      await fetch(`/api/context/move/${troveId}?direction=${direction}`, { method: 'POST' });
      await this.fetchContext();
      await this.fetchStats();
    } catch (error) {
      console.error('Failed to move article:', error);
    }
  }

  async handleClear() {
    if (!confirm('Clear all articles from context? (This will also clear pinned articles.)')) return;
    try {
      await fetch('/api/context', { method: 'DELETE' });
      await this.fetchContext();
      await this.fetchStats();
    } catch (error) {
      console.error('Failed to clear context:', error);
    }
  }

  async handleClearTracked() {
    if (!confirm('Clear tracked articles? (Pinned articles will be kept.)')) return;
    try {
      await fetch('/api/context/tracked', { method: 'DELETE' });
      await this.fetchContext();
      await this.fetchStats();
    } catch (error) {
      console.error('Failed to clear tracked:', error);
    }
  }

  async handleExport(format = 'json') {
    try {
      const url = `/api/context/export?format=${format}`;
      if (format === 'csv') {
        const res = await fetch(url);
        const blob = await res.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = 'tracked-articles.csv';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(downloadUrl);
      } else {
        const res = await fetch(url);
        const data = await res.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = 'tracked-articles.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(downloadUrl);
      }
    } catch (error) {
      console.error('Failed to export:', error);
      alert('Failed to export articles');
    }
  }

  toggle() {
    this.isOpen = !this.isOpen;
    if (this.isOpen) {
      this.fetchContext();
    }
    this.render();
  }

  updateLoadingState() {
    const content = this.container.querySelector('.context-tray-content');
    if (content) {
      content.classList.toggle('loading', this.loading);
    }
  }

  attachEventListeners() {
    const pill = this.container.querySelector('.context-pill');
    const closeBtn = this.container.querySelector('.context-tray-close');
    const clearBtn = this.container.querySelector('.btn-clear-context');
    const clearTrackedBtn = this.container.querySelector('.btn-clear-tracked');
    const exportJsonBtn = this.container.querySelector('.btn-export-json');
    const exportCsvBtn = this.container.querySelector('.btn-export-csv');

    if (pill) {
      pill.addEventListener('click', () => this.toggle());
    }
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        this.isOpen = false;
        this.render();
      });
    }
    if (clearBtn) {
      clearBtn.addEventListener('click', () => this.handleClear());
    }
    if (clearTrackedBtn) {
      clearTrackedBtn.addEventListener('click', () => this.handleClearTracked());
    }
    if (exportJsonBtn) {
      exportJsonBtn.addEventListener('click', () => this.handleExport('json'));
    }
    if (exportCsvBtn) {
      exportCsvBtn.addEventListener('click', () => this.handleExport('csv'));
    }

    // Handle pin toggle clicks
    this.container.addEventListener('click', (e) => {
      if (e.target.closest('.pin-toggle')) {
        const btn = e.target.closest('.pin-toggle');
        const troveId = btn.dataset.troveId;
        const currentlyPinned = btn.dataset.pinned === 'true';
        this.handlePin(troveId, !currentlyPinned);
      }
      // Handle move buttons
      if (e.target.closest('.move-up')) {
        const btn = e.target.closest('.move-up');
        const troveId = btn.dataset.troveId;
        this.handleMove(troveId, 'up');
      }
      if (e.target.closest('.move-down')) {
        const btn = e.target.closest('.move-down');
        const troveId = btn.dataset.troveId;
        this.handleMove(troveId, 'down');
      }
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
      if (this.isOpen && !this.container.contains(e.target)) {
        this.isOpen = false;
        this.render();
      }
    });
  }

  render() {
    const stats = this.stats || { pinned: 0, tracked: 0, total: 0 };
    const pinnedCount = stats.pinned || this.articles.filter(a => a.pinned).length;
    const trackedCount = stats.tracked || (this.articles.length - pinnedCount);
    const totalCount = stats.total || this.articles.length;

    this.container.innerHTML = `
      <button class="context-pill" aria-label="Tracked articles (${totalCount} total, ${pinnedCount} pinned)">
        📚 Tracked (${totalCount})
        ${pinnedCount > 0 ? `<span class="pinned-badge">${pinnedCount} pinned</span>` : ''}
      </button>

      ${this.isOpen ? `
        <div class="context-tray">
          <div class="context-tray-header">
            <h3>Tracked Articles</h3>
            <button class="context-tray-close" aria-label="Close tray">×</button>
          </div>

          <div class="context-tray-stats">
            <span class="stat-item">📌 Pinned: <strong>${pinnedCount}</strong></span>
            <span class="stat-item">📋 Tracked: <strong>${trackedCount}</strong></span>
            <span class="stat-item">📊 Total: <strong>${totalCount}</strong></span>
          </div>

          <div class="context-tray-actions">
            <button class="btn-clear-tracked" ${trackedCount === 0 ? 'disabled' : ''} title="Clear tracked articles (keeps pinned)">
              🗑️ Clear Tracked
            </button>
            <button class="btn-clear-context" ${totalCount === 0 ? 'disabled' : ''} title="Clear all articles (including pinned)">
              🗑️ Clear All
            </button>
            <button class="btn-export-json" ${totalCount === 0 ? 'disabled' : ''} title="Export as JSON">
              📥 Export JSON
            </button>
            <button class="btn-export-csv" ${totalCount === 0 ? 'disabled' : ''} title="Export as CSV">
              📥 Export CSV
            </button>
          </div>

          <div class="context-tray-content">
            ${this.loading ? `
              <div class="context-loading">Loading...</div>
            ` : this.articles.length === 0 ? `
              <div class="context-empty">
                <p>No articles tracked yet.</p>
                <p class="hint">Click on articles in search results to track them automatically.</p>
              </div>
            ` : `
              <ul class="context-list">
                ${this.articles
                  .sort((a, b) => {
                    // Pinned articles first, then by last_seen DESC
                    if (a.pinned && !b.pinned) return -1;
                    if (!a.pinned && b.pinned) return 1;
                    if (a.pinned && b.pinned) {
                      // For pinned articles, maintain order (newer first = higher last_seen)
                      return (b.last_seen || 0) - (a.last_seen || 0);
                    }
                    return (b.last_seen || 0) - (a.last_seen || 0);
                  })
                  .map((article, index, arr) => {
                    const pinnedArticles = arr.filter(a => a.pinned);
                    const pinnedIndex = pinnedArticles.findIndex(a => a.trove_id === article.trove_id);
                    const isFirstPinned = article.pinned && pinnedIndex === 0;
                    const isLastPinned = article.pinned && pinnedIndex === pinnedArticles.length - 1;
                    return `
                    <li class="context-item ${article.pinned ? 'pinned' : 'tracked'}">
                      <div class="context-item-header">
                        <div class="context-item-actions">
                          <button 
                            class="pin-toggle" 
                            data-trove-id="${article.trove_id}"
                            data-pinned="${article.pinned}"
                            aria-label="${article.pinned ? 'Unpin article' : 'Pin article'}"
                            title="${article.pinned ? 'Unpin (remove from pins)' : 'Pin (promote to pins)'}"
                          >
                            ${article.pinned ? '📌' : '📍'}
                          </button>
                          ${article.pinned ? `
                            <div class="move-buttons">
                              <button 
                                class="move-up" 
                                data-trove-id="${article.trove_id}"
                                aria-label="Move up"
                                title="Move up in pinned order"
                                ${isFirstPinned ? 'disabled' : ''}
                              >
                                ▲
                              </button>
                              <button 
                                class="move-down" 
                                data-trove-id="${article.trove_id}"
                                aria-label="Move down"
                                title="Move down in pinned order"
                                ${isLastPinned ? 'disabled' : ''}
                              >
                                ▼
                              </button>
                            </div>
                          ` : ''}
                          <a href="/reader?id=${article.trove_id}${article.url ? `&url=${encodeURIComponent(article.url)}` : ''}" 
                             class="btn-read" 
                             title="Open in Reader">
                            📖
                          </a>
                        </div>
                        <div class="context-item-title">
                          <a href="${article.url || '#'}" target="_blank" rel="noopener noreferrer">
                            ${this.escapeHtml(article.title || 'Untitled')}
                          </a>
                          ${article.pinned ? '<span class="pinned-label">📌 Pinned</span>' : '<span class="tracked-label">📋 Tracked</span>'}
                        </div>
                      </div>
                      ${(article.date || article.source) ? `
                        <div class="context-item-meta">
                          ${article.date ? `<span>📅 ${this.escapeHtml(article.date)}</span>` : ''}
                          ${article.source ? `<span>📰 ${this.escapeHtml(article.source)}</span>` : ''}
                        </div>
                      ` : ''}
                      ${article.snippet ? `
                        <div class="context-item-snippet">${this.escapeHtml(article.snippet.substring(0, 200))}${article.snippet.length > 200 ? '...' : ''}</div>
                      ` : ''}
                    </li>
                  `}).join('')}
              </ul>
            `}
          </div>
        </div>
      ` : ''}
    `;

    this.attachEventListeners();
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

/**
 * Citations Footer - Vanilla JS implementation
 */
function renderCitationsFooter(items, container) {
  if (!items || items.length === 0) {
    if (container) container.innerHTML = '';
    return;
  }

  const html = `
    <div class="citations-footer">
      <div class="citations-header">
        <strong>Sources:</strong>
      </div>
      <ol class="citations-list">
        ${items.map((item, index) => `
          <li class="citation-item">
            ${item.url ? `
              <a href="${item.url}" target="_blank" rel="noopener noreferrer" class="citation-link">
                ${escapeHtml(item.title)}
              </a>
            ` : `
              <span>${escapeHtml(item.title)}</span>
            `}
            ${(item.date || item.source) ? `
              <span class="citation-meta">
                ${item.date && item.source 
                  ? `${escapeHtml(item.date)} • ${escapeHtml(item.source)}`
                  : escapeHtml(item.date || item.source)}
              </span>
            ` : ''}
          </li>
        `).join('')}
      </ol>
    </div>
  `;

  if (container) {
    container.innerHTML = html;
  }
  return html;
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Slash Commands Parser
 */
function parseSlashCommand(input) {
  const trimmed = input.trim();
  
  if (!trimmed.startsWith('/')) {
    return { type: 'none' };
  }

  const parts = trimmed.slice(1).split(/\s+/);
  const command = parts[0].toLowerCase();
  const args = parts.slice(1).join(' ');

  switch (command) {
    case 'context':
      return { type: 'context', args };
    case 'cite':
      return { type: 'cite', args };
    case 'clear':
      return { type: 'clear', args };
    default:
      return { type: 'none' };
  }
}

// Global function to call when new search starts
function onNewSearchStarted() {
  if (CLEAR_TRACKED_ON_NEW_QUERY) {
    fetch('/api/context/tracked', { method: 'DELETE' })
      .then(() => {
        // Refresh any context trays on the page
        if (window.contextTrayInstance) {
          window.contextTrayInstance.refresh();
        }
        // Dispatch event for other components
        window.dispatchEvent(new CustomEvent('tracked-cleared'));
      })
      .catch(error => {
        console.error('Failed to clear tracked on new search:', error);
      });
  }
}

// Export for use in chat.html and other pages
if (typeof window !== 'undefined') {
  window.ContextTray = ContextTray;
  window.renderCitationsFooter = renderCitationsFooter;
  window.parseSlashCommand = parseSlashCommand;
  window.onNewSearchStarted = onNewSearchStarted;
  window.CLEAR_TRACKED_ON_NEW_QUERY = CLEAR_TRACKED_ON_NEW_QUERY;
  window.TRACKED_MAX = TRACKED_MAX;
}

