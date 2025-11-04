import React, { useState, useEffect } from 'react';

interface Article {
  trove_id: string;
  title: string;
  date: string;
  source: string;
  url: string;
  snippet: string;
  pinned?: boolean;
}

interface ContextTrayProps {
  sessionId?: string;
}

export const ContextTray: React.FC<ContextTrayProps> = ({ sessionId }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchContext = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/context');
      const data = await res.json();
      if (data.ok) {
        setArticles(data.items || []);
      }
    } catch (error) {
      console.error('Failed to fetch context:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchContext();
    }
  }, [isOpen]);

  const handlePin = async (troveId: string, pinned: boolean) => {
    try {
      const endpoint = pinned ? `/api/context/pin/${troveId}` : `/api/context/unpin/${troveId}`;
      await fetch(endpoint, { method: 'POST' });
      await fetchContext();
    } catch (error) {
      console.error('Failed to pin/unpin:', error);
    }
  };

  const handleClear = async () => {
    if (!confirm('Clear all articles from context?')) return;
    try {
      await fetch('/api/context', { method: 'DELETE' });
      await fetchContext();
    } catch (error) {
      console.error('Failed to clear context:', error);
    }
  };

  const pinnedCount = articles.filter(a => a.pinned).length;
  const totalCount = articles.length;

  return (
    <div className="context-tray-wrapper">
      <button
        className="context-pill"
        onClick={() => setIsOpen(!isOpen)}
        aria-label={`Research context (${totalCount} articles)`}
      >
        📚 Research ({totalCount})
        {pinnedCount > 0 && <span className="pinned-badge">{pinnedCount}</span>}
      </button>

      {isOpen && (
        <div className="context-tray">
          <div className="context-tray-header">
            <h3>Research Context</h3>
            <button
              className="context-tray-close"
              onClick={() => setIsOpen(false)}
              aria-label="Close tray"
            >
              ×
            </button>
          </div>

          <div className="context-tray-actions">
            <button
              className="btn-clear-context"
              onClick={handleClear}
              disabled={totalCount === 0}
            >
              🗑️ Clear All
            </button>
          </div>

          <div className="context-tray-content">
            {loading ? (
              <div className="context-loading">Loading...</div>
            ) : articles.length === 0 ? (
              <div className="context-empty">
                No articles in context yet. Open articles to track them.
              </div>
            ) : (
              <ul className="context-list">
                {articles
                  .sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0))
                  .map(article => (
                    <li
                      key={article.trove_id}
                      className={`context-item ${article.pinned ? 'pinned' : ''}`}
                    >
                      <div className="context-item-header">
                        <button
                          className="pin-toggle"
                          onClick={() => handlePin(article.trove_id, !article.pinned)}
                          aria-label={article.pinned ? 'Unpin article' : 'Pin article'}
                          title={article.pinned ? 'Unpin' : 'Pin'}
                        >
                          {article.pinned ? '📌' : '📍'}
                        </button>
                        <div className="context-item-title">
                          <a
                            href={article.url || '#'}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {article.title}
                          </a>
                        </div>
                      </div>
                      {(article.date || article.source) && (
                        <div className="context-item-meta">
                          {article.date && <span>{article.date}</span>}
                          {article.source && <span>{article.source}</span>}
                        </div>
                      )}
                      {article.snippet && (
                        <div className="context-item-snippet">{article.snippet}</div>
                      )}
                    </li>
                  ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

