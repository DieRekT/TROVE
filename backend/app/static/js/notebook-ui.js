/**
 * Research Notebook UI - Entity extraction and timeline visualization
 */

document.addEventListener("DOMContentLoaded", () => {
  loadEntities();
  setupCompareButton();
});

/**
 * Set up compare button handler
 */
function setupCompareButton() {
  const compareBtn = document.getElementById("compareBtn");
  if (compareBtn && !compareBtn.dataset.setup) {
    compareBtn.dataset.setup = "true";
    compareBtn.addEventListener("click", () => {
      const selected = Array.from(document.querySelectorAll(".entity-btn.selected"))
        .map(btn => btn.dataset.term);
      
      if (selected.length < 2) {
        alert("Please select at least 2 entities to compare. Click entities to select them.");
        return;
      }
      
      compareEntities(selected);
    });
  }
}

let chart = null;

/**
 * Load entities from the API and display them in the sidebar
 */
function loadEntities() {
  const entityList = document.getElementById("entityList");
  if (!entityList) return;
  
  entityList.innerHTML = '<li class="loading">Loading entities...</li>';
  
  fetch("/api/entities")
    .then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then(data => {
      if (!data.ok) {
        entityList.innerHTML = '<li class="loading">No entities found. Track some articles first!</li>';
        return;
      }
      
      entityList.innerHTML = "";
      
      if (data.entities.length === 0) {
        entityList.innerHTML = '<li class="loading">No entities found. Track some articles first!</li>';
        return;
      }
      
      data.entities.forEach(ent => {
        const li = document.createElement("li");
        const labelBadge = getLabelBadge(ent.label);
        const linkIcon = ent.link ? '🔗' : '';
        
        li.innerHTML = `
          <button class="entity-btn" data-term="${escapeHtml(ent.text)}" data-label="${ent.label}">
            <span class="entity-name">${escapeHtml(ent.text)}</span>
            <span class="entity-meta">
              ${labelBadge} <span class="entity-count">(${ent.count})</span>
              ${linkIcon}
            </span>
          </button>
        `;
        entityList.appendChild(li);
      });
      
      // Add click handlers with toggle selection
      entityList.querySelectorAll(".entity-btn").forEach(btn => {
        btn.addEventListener("click", () => {
          const wasSelected = btn.classList.contains("selected");
          btn.classList.toggle("selected");
          const term = btn.dataset.term;
          const label = btn.dataset.label;
          
          // Count selected entities after toggle
          const selectedCount = entityList.querySelectorAll(".entity-btn.selected").length;
          
          // If only one selected (and it's this one), show its timeline
          if (selectedCount === 1 && !wasSelected) {
            showTimeline(term, label);
          } else if (selectedCount === 0) {
            // If none selected, hide timeline
            hideTimeline();
          }
          // If multiple selected, don't auto-show timeline (user should click compare)
        });
      });
    })
    .catch(err => {
      console.error("Failed to load entities:", err);
      entityList.innerHTML = '<li class="loading">Error loading entities. Check console.</li>';
    });
}

/**
 * Get a badge for entity label
 */
function getLabelBadge(label) {
  const badges = {
    "PERSON": "👤",
    "ORG": "🏢",
    "GPE": "🌍",
    "LOC": "📍",
    "EVENT": "📅",
    "FAC": "🏛️",
    "PRODUCT": "📦"
  };
  return badges[label] || "🏷️";
}

/**
 * Show timeline for a given entity/term
 */
function showTimeline(term, label = null) {
  const timelineSection = document.getElementById("timelineSection");
  const timelineInfo = document.getElementById("timelineInfo");
  const canvas = document.getElementById("timelineChart");
  
  if (!timelineSection || !canvas) return;
  
  // Show loading state
  timelineSection.classList.remove("hidden");
  timelineInfo.innerHTML = `Loading timeline for "${term}"...`;
  
  // Clear any existing article results
  const existing = document.getElementById("articleResults");
  if (existing) existing.remove();
  
  fetch(`/api/timeline?q=${encodeURIComponent(term)}`)
    .then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then(data => {
      if (!data.ok || !data.timeline || data.timeline.length === 0) {
        timelineInfo.innerHTML = `No timeline data found for "${term}". This entity may not appear in dated articles.`;
        if (chart) {
          chart.destroy();
          chart = null;
        }
        return;
      }
      
      const years = data.timeline.map(p => p.year);
      const counts = data.timeline.map(p => p.count);
      
      renderTimeline(term, label, years, counts, data.timeline);
      
      // Update info
      const total = counts.reduce((a, b) => a + b, 0);
      const yearRange = years.length > 0 ? `${years[0]}-${years[years.length - 1]}` : "N/A";
      timelineInfo.innerHTML = `
        <strong>${escapeHtml(term)}</strong> appears <strong>${total}</strong> time${total !== 1 ? 's' : ''} 
        across <strong>${years.length}</strong> year${years.length !== 1 ? 's' : ''} (${yearRange})
        <br><small>Click a bar to see articles from that year</small>
      `;
    })
    .catch(err => {
      console.error("Failed to load timeline:", err);
      timelineInfo.innerHTML = `Error loading timeline: ${err.message}`;
      if (chart) {
        chart.destroy();
        chart = null;
      }
    });
}

/**
 * Render timeline chart using Chart.js
 */
function renderTimeline(term, label, labels, dataPoints, rawData) {
  const ctx = document.getElementById("timelineChart");
  if (!ctx) return;
  
  // Destroy existing chart
  if (chart) {
    chart.destroy();
  }
  
  // Create new chart
  chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: `Mentions of "${term}"`,
        data: dataPoints,
        backgroundColor: 'rgba(102, 153, 204, 0.6)',
        borderColor: 'rgba(102, 153, 204, 1)',
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          callbacks: {
            label: function(context) {
              return `${context.parsed.y} mention${context.parsed.y !== 1 ? 's' : ''} in ${context.label}`;
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            stepSize: 1
          }
        },
        x: {
          title: {
            display: true,
            text: 'Year'
          }
        }
      },
      onClick: (event, elements) => {
        if (elements.length > 0) {
          const index = elements[0].index;
          const year = labels[index];
          showArticlesFor(term, year);
        }
      }
    }
  });
}

/**
 * Show articles matching a term in a specific year
 */
function showArticlesFor(term, year) {
  const timelineSection = document.getElementById("timelineSection");
  if (!timelineSection) return;
  
  // Remove existing results
  const existing = document.getElementById("articleResults");
  if (existing) existing.remove();
  
  // Show loading
  const loadingDiv = document.createElement("div");
  loadingDiv.id = "articleResults";
  loadingDiv.innerHTML = `<h3>Loading articles for "${term}" in ${year}...</h3>`;
  timelineSection.appendChild(loadingDiv);
  
  fetch(`/api/timeline/hits?q=${encodeURIComponent(term)}&year=${year}`)
    .then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then(data => {
      if (!data.ok || !data.results || data.results.length === 0) {
        loadingDiv.innerHTML = `<h3>Articles mentioning "${escapeHtml(term)}" in ${year}</h3><p>No articles found for this year.</p>`;
        return;
      }
      
      loadingDiv.innerHTML = `
        <h3>Articles mentioning "${escapeHtml(term)}" in ${year}</h3>
        <div class="article-results-list">
          ${data.results.map(r => `
            <article class="result-article">
              <h4>${escapeHtml(r.title || 'Untitled')}</h4>
              <p class="article-meta">${escapeHtml(r.date || 'Unknown date')} • ${escapeHtml(r.source || 'Unknown source')}</p>
              <p class="article-snippet">${escapeHtml(r.snippet || '').substring(0, 200)}${r.snippet && r.snippet.length > 200 ? '...' : ''}</p>
              ${r.trove_id ? `<a class="btn btn-primary" href="/reader?id=${escapeHtml(r.trove_id)}" target="_blank">🔍 Open Article</a>` : ''}
            </article>
          `).join('')}
        </div>
      `;
    })
    .catch(err => {
      console.error("Failed to load articles:", err);
      loadingDiv.innerHTML = `<h3>Error</h3><p>Failed to load articles: ${escapeHtml(err.message)}</p>`;
    });
}

/**
 * Hide timeline panel
 */
function hideTimeline() {
  const timelineSection = document.getElementById("timelineSection");
  if (timelineSection) {
    timelineSection.classList.add("hidden");
  }
  if (chart) {
    chart.destroy();
    chart = null;
  }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Compare multiple entities on one timeline chart
 */
function compareEntities(terms) {
  const timelineSection = document.getElementById("timelineSection");
  const timelineInfo = document.getElementById("timelineInfo");
  const canvas = document.getElementById("timelineChart");
  
  if (!timelineSection || !canvas) return;
  
  // Show loading state
  timelineSection.classList.remove("hidden");
  timelineInfo.innerHTML = `Comparing ${terms.length} entities...`;
  
  // Clear any existing article results
  const existing = document.getElementById("articleResults");
  if (existing) existing.remove();
  
  fetch(`/api/timeline/compare?q=${encodeURIComponent(terms.join(","))}`)
    .then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then(data => {
      if (!data.ok || !data.datasets || data.datasets.length === 0) {
        timelineInfo.innerHTML = `No timeline data found for comparison.`;
        if (chart) {
          chart.destroy();
          chart = null;
        }
        return;
      }
      
      // Destroy existing chart
      if (chart) {
        chart.destroy();
      }
      
      // Create comparison chart (line chart for better visibility)
      chart = new Chart(canvas, {
        type: 'line',
        data: {
          labels: data.years,
          datasets: data.datasets
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: true,
              position: 'top'
            },
            tooltip: {
              callbacks: {
                label: function(context) {
                  return `${context.dataset.label}: ${context.parsed.y} mention${context.parsed.y !== 1 ? 's' : ''}`;
                }
              }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                stepSize: 1
              }
            },
            x: {
              title: {
                display: true,
                text: 'Year'
              }
            }
          }
        }
      });
      
      // Update info
      timelineInfo.innerHTML = `
        Comparing <strong>${terms.map(t => escapeHtml(t)).join('</strong>, <strong>')}</strong>
        across <strong>${data.years.length}</strong> year${data.years.length !== 1 ? 's' : ''}
        (${data.years.length > 0 ? `${data.years[0]}-${data.years[data.years.length - 1]}` : 'N/A'})
      `;
    })
    .catch(err => {
      console.error("Failed to compare entities:", err);
      timelineInfo.innerHTML = `Error comparing entities: ${escapeHtml(err.message)}`;
      if (chart) {
        chart.destroy();
        chart = null;
      }
    });
}

// Export for potential external use
window.notebookUI = {
  loadEntities,
  showTimeline,
  hideTimeline,
  compareEntities,
  showArticlesFor
};

