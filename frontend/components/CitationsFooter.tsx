import React from 'react';

interface Citation {
  id?: string;
  trove_id?: string;
  title: string;
  url?: string;
  date?: string;
  source?: string;
}

interface CitationsFooterProps {
  items: Citation[];
}

export const CitationsFooter: React.FC<CitationsFooterProps> = ({ items }) => {
  if (!items || items.length === 0) return null;

  return (
    <div className="citations-footer">
      <div className="citations-header">
        <strong>Sources:</strong>
      </div>
      <ol className="citations-list">
        {items.map((item, index) => (
          <li key={item.trove_id || item.id || index} className="citation-item">
            {item.url ? (
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="citation-link"
              >
                {item.title}
              </a>
            ) : (
              <span>{item.title}</span>
            )}
            {(item.date || item.source) && (
              <span className="citation-meta">
                {item.date && item.source
                  ? `${item.date} • ${item.source}`
                  : item.date || item.source}
              </span>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
};

