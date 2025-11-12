// Deep Research UI JavaScript

let currentJobId = null;
let eventSource = null;
let currentReport = null;

// New deep research function using streaming /api/research/deep/stream
async function startDeepResearch() {
  const questionEl = document.getElementById('question');
  const regionEl = document.getElementById('region');
  const timeWindowEl = document.getElementById('time_window');
  const depthEl = document.getElementById('depth');
  const form = document.getElementById('researchForm');
  const progressSection = document.getElementById('progressSection');
  const resultsSection = document.getElementById('resultsSection');
  const reportContent = document.getElementById('reportContent');
  const progressText = document.getElementById('progressText');
  const progressFill = document.getElementById('progressFill');
  const progressStatus = document.getElementById('progressStatus');
  
  const query = questionEl?.value?.trim();
  if (!query) {
    alert('Enter a research question');
    return;
  }
  
  const region = regionEl?.value?.trim() || null;
  const tw = timeWindowEl?.value?.trim() || "";
  
  // Get depth from radio buttons
  const depthRadio = document.querySelector('input[name="depth"]:checked');
  const depth = depthRadio?.value || "standard";
  
  let years_from = null, years_to = null;
  if (tw) {
    // Parse YYYY-YYYY format
    const m = tw.match(/^\s*(\d{4})\s*[-–]\s*(\d{4})\s*$/);
    if (m) {
      years_from = parseInt(m[1], 10);
      years_to = parseInt(m[2], 10);
    }
  }
  
  // Show progress
  if (form) form.style.display = 'none';
  if (progressSection) progressSection.style.display = 'block';
  if (resultsSection) resultsSection.style.display = 'none';
  if (progressText) progressText.textContent = '0%';
  if (progressFill) progressFill.style.width = '0%';
  if (progressStatus) progressStatus.textContent = 'Initializing...';
  if (reportContent) reportContent.innerHTML = '<p>Starting research...</p>';
  
  try {
    const payload = { query, region, years_from, years_to, depth, max_sources: 12 };
    
    // Use streaming endpoint
    const response = await fetch('/api/research/deep/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      if (errorText.includes('<!DOCTYPE') || errorText.includes('<html') || errorText.includes('ngrok')) {
        throw new Error('Server error: The server may be unavailable or experiencing issues. Please try again later.');
      }
      try {
        const errorJson = JSON.parse(errorText);
        throw new Error(errorJson.detail || errorJson.message || `HTTP ${response.status}`);
      } catch {
        throw new Error(errorText.substring(0, 200) || `HTTP ${response.status}`);
      }
    }
    
    // Handle Server-Sent Events stream
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let report = null;
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep incomplete line in buffer
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            
            if (data.type === 'progress') {
              // Update progress
              if (progressText) progressText.textContent = `${data.progress}%`;
              if (progressFill) progressFill.style.width = `${data.progress}%`;
              if (progressStatus) progressStatus.textContent = data.message || 'Processing...';
            } else if (data.type === 'cached') {
              // Cached result
              report = data.data;
            } else if (data.type === 'result') {
              // Final result
              report = data.data;
            } else if (data.type === 'error') {
              throw new Error(data.message || 'Unknown error');
            }
          } catch (e) {
            console.error('Error parsing SSE data:', e, line);
          }
        }
      }
    }
    
    if (!report) {
      throw new Error('No report received from server');
    }
    
    currentReport = report;
    
    // Render report
    const lines = [];
    lines.push(`<h2>Executive Summary</h2><p>${report.executive_summary}</p>`);
    
    if (report.key_findings?.length) {
      lines.push('<h2>Key Findings</h2>');
      report.key_findings.forEach((f, i) => {
        lines.push(`<h3>${i + 1}. ${f.title}</h3><p>${f.insight}</p>`);
        if (f.evidence?.length) {
          lines.push('<blockquote>');
          f.evidence.forEach(q => {
            // Ensure quotes are properly formatted
            const quote = String(q).replace(/^["']|["']$/g, ''); // Remove surrounding quotes if present
            lines.push(`<p>"${quote}"</p>`);
          });
          lines.push('</blockquote>');
        }
        if (f.citations?.length) {
          lines.push(`<p><strong>Citations:</strong> ${f.citations.join(', ')}</p>`);
        }
      });
    }
    
    if (report.timeline?.length) {
      lines.push('<h2>Timeline</h2><ul>');
      report.timeline.forEach(t => {
        lines.push(`<li>${t.date}: ${t.event} (${(t.citations || []).join(', ')})</li>`);
      });
      lines.push('</ul>');
    }
    
    if (report.sources?.length) {
      lines.push('<h2>Sources</h2><ul>');
      report.sources.forEach(s => {
        let row = `<li>${s.title}`;
        if (s.url) row += ` — <a href="${s.url}" target="_blank" rel="noopener">${s.url}</a>`;
        if (s.year) row += ` — ${s.year}`;
        if (s.relevance !== undefined) row += ` — rel=${s.relevance.toFixed(2)}</li>`;
        else row += '</li>';
        lines.push(row);
      });
      lines.push('</ul>');
    }
    
    if (reportContent) reportContent.innerHTML = lines.join('\n');
    if (progressText) progressText.textContent = '100%';
    if (progressFill) progressFill.style.width = '100%';
    if (progressSection) progressSection.style.display = 'none';
    if (resultsSection) resultsSection.style.display = 'block';
    
    // Setup download handlers
    const downloadMd = document.getElementById('downloadMd');
    const downloadJsonl = document.getElementById('downloadJsonl');
    
    if (downloadMd) {
      downloadMd.onclick = async (e) => {
        e.preventDefault();
        const r = await fetch('/api/research/markdown', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ report })
        });
        const text = await r.text();
        const blob = new Blob([text], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = Object.assign(document.createElement('a'), { href: url, download: 'deep-research.md' });
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      };
    }
    
    if (downloadJsonl) {
      downloadJsonl.onclick = async (e) => {
        e.preventDefault();
        const r = await fetch('/api/research/evidence', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ report })
        });
        const text = await r.text();
        const blob = new Blob([text], { type: 'application/jsonl' });
        const url = URL.createObjectURL(blob);
        const a = Object.assign(document.createElement('a'), { href: url, download: 'evidence.jsonl' });
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      };
    }
    
  } catch (error) {
    console.error('Error starting deep research:', error);
    let errorMessage = error.message || 'Unknown error';
    
    // Better error handling for empty sources
    if (errorMessage.includes('No evidence found') || errorMessage.includes('No sources')) {
      errorMessage = 'No evidence found — widen years or try: "Iluka mineral sands rutile zircon"';
    }
    
    if (reportContent) {
      reportContent.innerHTML = `
        <div class="error" style="padding: 1rem; background: #fee; border: 1px solid #fcc; border-radius: 4px; color: #c33;">
          <h3>❌ Research Failed</h3>
          <p>${errorMessage}</p>
          <p style="margin-top: 0.75rem; font-size: 0.9rem;">
            <strong>Suggestions:</strong><br>
            • Widen the year range (e.g., 1940-2000)<br>
            • Use more specific search terms<br>
            • Check that the query matches historical terminology
          </p>
        </div>
      `;
    }
    if (progressText) progressText.textContent = 'Error';
    if (progressSection) progressSection.style.display = 'none';
    if (resultsSection) resultsSection.style.display = 'block';
    if (form) form.style.display = 'block';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('researchForm');
  const startBtn = document.getElementById('startBtn');
  const sampleIluka = document.getElementById('sampleIluka');
  
  // One-click seed: Iluka mining sample
  if (sampleIluka) {
    sampleIluka.addEventListener('click', async () => {
      const questionEl = document.getElementById('question');
      const regionEl = document.getElementById('region');
      const timeWindowEl = document.getElementById('time_window');
      const depthStandard = document.getElementById('depth-standard');
      
      if (questionEl) questionEl.value = 'Iluka mining';
      if (regionEl) regionEl.value = '';
      if (timeWindowEl) timeWindowEl.value = '1945–1980';
      if (depthStandard) depthStandard.checked = true;
      
      // Auto-submit
      if (form) {
        form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
      }
    });
  }
  
  // Try new deep research API first, fall back to old job-based system
  if (form && startBtn) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      // Try new API first
      try {
        await startDeepResearch();
      } catch (error) {
        console.log('New API failed, trying old system:', error);
        // Fall back to old system if new API not available
        startOldResearch();
      }
    });
  }
});

function startOldResearch() {
  const form = document.getElementById('researchForm');
  const progressSection = document.getElementById('progressSection');
  const resultsSection = document.getElementById('resultsSection');
  
  const formData = new FormData(form);
  const sources = Array.from(form.querySelectorAll('input[name="sources"]:checked')).map(cb => cb.value);
  
  const payload = {
    question: formData.get('question'),
    region: formData.get('region') || null,
    time_window: formData.get('time_window') || null,
    depth: formData.get('depth'),
    sources: sources.length > 0 ? sources : ['web', 'trove']
  };
  
  fetch('/research/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  .then(response => {
    if (!response.ok) {
      const errorText = response.text();
      let errorMessage = `HTTP ${response.status}`;
      return errorText.then(text => {
        try {
          const errorJson = JSON.parse(text);
          errorMessage = errorJson.detail || errorJson.message || errorMessage;
        } catch {
          if (text.includes('<!DOCTYPE') || text.includes('<html')) {
            errorMessage = `Server error (${response.status}). The server may be unavailable or experiencing issues.`;
          } else {
            errorMessage = text.substring(0, 200);
          }
        }
        throw new Error(errorMessage);
      });
    }
    return response.json();
  })
  .then(data => {
    currentJobId = data.job_id;
    form.style.display = 'none';
    progressSection.style.display = 'block';
    resultsSection.style.display = 'none';
    startProgressStream(currentJobId);
  })
  .catch(error => {
    console.error('Error starting research:', error);
    alert(`Failed to start research: ${error.message}`);
  });
}

function startProgressStream(jobId) {
  if (eventSource) {
    eventSource.close();
  }
  
  eventSource = new EventSource(`/research/${jobId}/stream`);
  
  eventSource.addEventListener('progress', (e) => {
    const progress = parseInt(e.data);
    updateProgress(progress);
  });
  
  eventSource.addEventListener('done', async (e) => {
    eventSource.close();
    updateProgress(100);
    document.getElementById('progressStatus').textContent = 'Research complete!';
    await loadReport(jobId);
  });
  
  eventSource.addEventListener('error', (e) => {
    eventSource.close();
    document.getElementById('progressStatus').textContent = `Error: ${e.data}`;
    document.getElementById('progressStatus').classList.add('error');
  });
  
  // Poll for status updates as fallback
  pollProgress(jobId);
}

function updateProgress(percent) {
  const fill = document.getElementById('progressFill');
  const text = document.getElementById('progressText');
  fill.style.width = `${percent}%`;
  text.textContent = `${percent}%`;
}

async function pollProgress(jobId) {
  const interval = setInterval(async () => {
    try {
      const response = await fetch(`/research/${jobId}/progress`);
      if (!response.ok) return;
      
      const job = await response.json();
      updateProgress(job.progress_pct || 0);
      
      if (job.status === 'done') {
        clearInterval(interval);
        if (eventSource) eventSource.close();
        updateProgress(100);
        document.getElementById('progressStatus').textContent = 'Research complete!';
        await loadReport(jobId);
      } else if (job.status === 'error') {
        clearInterval(interval);
        if (eventSource) eventSource.close();
        document.getElementById('progressStatus').textContent = `Error: ${job.error_message || 'Unknown error'}`;
        document.getElementById('progressStatus').classList.add('error');
      }
    } catch (error) {
      console.error('Error polling progress:', error);
    }
  }, 2000);
}

async function loadReport(jobId) {
  const resultsSection = document.getElementById('resultsSection');
  const reportContent = document.getElementById('reportContent');
  const downloadMd = document.getElementById('downloadMd');
  const downloadJsonl = document.getElementById('downloadJsonl');
  
  resultsSection.style.display = 'block';
  reportContent.innerHTML = '<p>Loading report...</p>';
  
  try {
    // Fetch markdown report
    const response = await fetch(`/research/${jobId}/report.md`);
    if (!response.ok) {
      throw new Error(`Failed to load report: ${response.status}`);
    }
    
    const markdown = await response.text();
    
    // Simple markdown to HTML conversion (basic)
    const html = markdownToHtml(markdown);
    reportContent.innerHTML = html;
    
    // Set download links
    downloadMd.href = `/research/${jobId}/report.md`;
    downloadJsonl.href = `/files/research/${jobId}/evidence.jsonl`;
    
  } catch (error) {
    console.error('Error loading report:', error);
    reportContent.innerHTML = `<p class="error">Failed to load report: ${error.message}</p>`;
  }
}

function markdownToHtml(markdown) {
  // Enhanced markdown to HTML converter with better formatting
  let html = markdown;
  
  // Headers (must be done first, before other replacements)
  html = html.replace(/^#### (.*$)/gim, '<h4>$1</h4>');
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
  
  // Horizontal rules
  html = html.replace(/^---$/gim, '<hr>');
  html = html.replace(/^\*\*\*$/gim, '<hr>');
  
  // Bold and italic (bold first to avoid conflicts)
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  
  // Links
  html = html.replace(/\[([^\]]+)\]\(([^\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  
  // Code blocks (before inline code)
  html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
  
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  
  // Tables (improved parsing)
  const tableRegex = /^\|(.+)\|$/gm;
  let inTable = false;
  let tableRows = [];
  html = html.split('\n').map(line => {
    if (tableRegex.test(line)) {
      if (!inTable) {
        inTable = true;
        tableRows = [];
      }
      const cells = line.match(/^\|(.+)\|$/)[1].split('|').map(c => c.trim());
      const isHeader = cells.some(c => /^[-:]+$/.test(c));
      if (isHeader) {
        return '<table><thead><tr>' + cells.map(c => `<th>${c}</th>`).join('') + '</tr></thead><tbody>';
      }
      return '<tr>' + cells.map(c => `<td>${c}</td>`).join('') + '</tr>';
    } else {
      if (inTable) {
        inTable = false;
        return '</tbody></table>' + line;
      }
      return line;
    }
  }).join('\n');
  if (inTable) {
    html += '</tbody></table>';
  }
  
  // Lists (ordered and unordered)
  html = html.replace(/^\d+\.\s+(.*$)/gim, '<li>$1</li>');
  html = html.replace(/^[-*]\s+(.*$)/gim, '<li>$1</li>');
  
  // Wrap consecutive list items
  html = html.replace(/(<li>.*<\/li>\n?)+/g, (match) => {
    return '<ul>' + match + '</ul>';
  });
  
  // Blockquotes
  html = html.replace(/^>\s+(.*$)/gim, '<blockquote>$1</blockquote>');
  
  // Paragraphs (split by double newlines, but preserve existing HTML)
  html = html.split('\n\n').map(p => {
    p = p.trim();
    if (!p) return '';
    if (p.startsWith('<')) {
      return p; // Already HTML
    }
    return `<p>${p}</p>`;
  }).join('\n');
  
  return html;
}

