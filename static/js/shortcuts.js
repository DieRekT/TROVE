/**
 * Keyboard shortcuts for Troveing
 */

document.addEventListener('DOMContentLoaded', () => {
  // Prevent shortcuts when typing in inputs
  const isInputFocused = () => {
    const active = document.activeElement;
    return active && (
      active.tagName === 'INPUT' ||
      active.tagName === 'TEXTAREA' ||
      active.isContentEditable
    );
  };

  // Global keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (isInputFocused()) return;

    // Ctrl/Cmd + K - Focus search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      const searchInput = document.querySelector('input[type="search"], input[placeholder*="Search"]');
      if (searchInput) {
        searchInput.focus();
        searchInput.select();
      }
    }

    // Ctrl/Cmd + / - Show shortcuts help (if implemented)
    if ((e.ctrlKey || e.metaKey) && e.key === '/') {
      e.preventDefault();
      // Could show a shortcuts modal here
      console.log('Shortcuts help (not yet implemented)');
    }
  });
});

