/**
 * Context Tray - Vanilla JS implementation
 * Provides pin/unpin UI and context management for the chat interface
 */

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
    // Auto-fetch on init if needed
    // this.fetchContext();
  }

  async fetchContext() {
    this.loading = true;
    this.updateLoadingState();
    try {
      const res = await fetch('/api/context');
      const data = await res.json();
      if (data.ok) {
        this.articles = data.items || [];
        this.render();
      }
    } catch (error) {
      console.error('Failed to fetch context:', error);
    } finally {
      this.loading = false;
      this.updateLoadingState();
    }
  }

  async handlePin(troveId, pinned) {
    try {
      const endpoint = pinned 
        ? `/api/context/pin/${troveId}` 
        : `/api/context/unpin/${troveId}`;
      await fetch(endpoint, { method: 'POST' });
      await this.fetchContext();
    } catch (error) {
      console.error('Failed to pin/unpin:', error);
    }
  }

  async handleClear() {
    if (!confirm('Clear all articles from context?')) return;
    try {
      await fetch('/api/context', { method: 'DELETE' });
      await this.fetchContext();
    } catch (error) {
      console.error('Failed to clear context:', error);
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

    // Handle pin toggle clicks
    this.container.addEventListener('click', (e) => {
      if (e.target.closest('.pin-toggle')) {
        const btn = e.target.closest('.pin-toggle');
        const troveId = btn.dataset.troveId;
        const currentlyPinned = btn.dataset.pinned === 'true';
        this.handlePin(troveId, !currentlyPinned);
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
    const pinnedCount = this.articles.filter(a => a.pinned).length;
    const totalCount = this.articles.length;

    this.container.innerHTML = `
      <button class="context-pill" aria-label="Research context (${totalCount} articles)">
        📚 Research (${totalCount})
        ${pinnedCount > 0 ? `<span class="pinned-badge">${pinnedCount}</span>` : ''}
      </button>

      ${this.isOpen ? `
        <div class="context-tray">
          <div class="context-tray-header">
            <h3>Research Context</h3>
            <button class="context-tray-close" aria-label="Close tray">×</button>
          </div>

          <div class="context-tray-actions">
            <button class="btn-clear-context" ${totalCount === 0 ? 'disabled' : ''}>
              🗑️ Clear All
            </button>
          </div>

          <div class="context-tray-content">
            ${this.loading ? `
              <div class="context-loading">Loading...</div>
            ` : this.articles.length === 0 ? `
              <div class="context-empty">
                No articles in context yet. Open articles to track them.
              </div>
            ` : `
              <ul class="context-list">
                ${this.articles
                  .sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0))
                  .map(article => `
                    <li class="context-item ${article.pinned ? 'pinned' : ''}">
                      <div class="context-item-header">
                        <button 
                          class="pin-toggle" 
                          data-trove-id="${article.trove_id}"
                          data-pinned="${article.pinned}"
                          aria-label="${article.pinned ? 'Unpin article' : 'Pin article'}"
                          title="${article.pinned ? 'Unpin' : 'Pin'}"
                        >
                          ${article.pinned ? '📌' : '📍'}
                        </button>
                        <div class="context-item-title">
                          <a href="${article.url || '#'}" target="_blank" rel="noopener noreferrer">
                            ${this.escapeHtml(article.title)}
                          </a>
                        </div>
                      </div>
                      ${(article.date || article.source) ? `
                        <div class="context-item-meta">
                          ${article.date ? `<span>${this.escapeHtml(article.date)}</span>` : ''}
                          ${article.source ? `<span>${this.escapeHtml(article.source)}</span>` : ''}
                        </div>
                      ` : ''}
                      ${article.snippet ? `
                        <div class="context-item-snippet">${this.escapeHtml(article.snippet)}</div>
                      ` : ''}
                    </li>
                  `).join('')}
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

// Export for use in chat.html
if (typeof window !== 'undefined') {
  window.ContextTray = ContextTray;
  window.renderCitationsFooter = renderCitationsFooter;
  window.parseSlashCommand = parseSlashCommand;
}

