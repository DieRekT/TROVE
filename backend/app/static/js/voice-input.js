/**
 * Voice-to-Text Input Component
 * Unified voice input system with best practices
 * - Real-time interim results
 * - Proper error handling
 * - Permission management
 * - Accessibility support
 * - Graceful degradation
 */

class VoiceInput {
  constructor() {
    this.recognition = null;
    this.isListening = false;
    this.currentInput = null;
    this.currentButton = null;
    this.interimTranscript = '';
    this.finalTranscript = '';
    this.permissionState = 'prompt'; // 'granted', 'denied', 'prompt'
    this.timeoutId = null;
    this.maxListenTime = 60000; // 60 seconds max
    
    // Configuration
    this.config = {
      lang: 'en-AU', // Australian English (can be overridden)
      continuous: false, // Set to true for continuous listening
      interimResults: true, // Show real-time results
      maxAlternatives: 1,
      autoSubmit: false, // Auto-submit after recognition (for forms)
      insertAtCursor: true, // Insert at cursor position vs replace
      showInterim: true, // Show interim results in input
      timeout: 60000, // Max listening time in ms
    };
    
    this.init();
  }

  init() {
    // Check browser support
    if (!this.isSupported()) {
      console.warn('Speech recognition not supported in this browser');
      this.hideAllVoiceButtons();
      return;
    }

    // Initialize Speech Recognition
    this.initRecognition();
    
    // Request microphone permission
    this.requestPermission();
    
    // Add voice input buttons to all inputs
    this.attachToAllInputs();
    
    // Handle visibility changes (tab switching)
    document.addEventListener('visibilitychange', () => {
      if (document.hidden && this.isListening) {
        this.stopListening();
      }
    });
  }

  isSupported() {
    return 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
  }

  initRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    this.recognition = new SpeechRecognition();
    
    // Configure recognition
    this.recognition.continuous = this.config.continuous;
    this.recognition.interimResults = this.config.interimResults;
    this.recognition.lang = this.config.lang;
    this.recognition.maxAlternatives = this.config.maxAlternatives;

    // Event handlers
    this.recognition.onstart = () => this.handleStart();
    this.recognition.onresult = (event) => this.handleResult(event);
    this.recognition.onerror = (event) => this.handleError(event);
    this.recognition.onend = () => this.handleEnd();
  }

  async requestPermission() {
    // Check if we can request permission
    if (navigator.permissions && navigator.permissions.query) {
      try {
        const result = await navigator.permissions.query({ name: 'microphone' });
        this.permissionState = result.state;
        
        result.onchange = () => {
          this.permissionState = result.state;
          this.updatePermissionUI();
        };
      } catch (e) {
        // Permissions API not fully supported
        console.debug('Permissions API not fully supported');
      }
    }
  }

  handleStart() {
    this.isListening = true;
    this.interimTranscript = '';
    this.finalTranscript = '';
    
    if (this.currentInput) {
      this.updateButtonState(this.currentInput, true);
      this.showListeningIndicator();
      
      // Set timeout for max listening time
      this.timeoutId = setTimeout(() => {
        if (this.isListening) {
          this.stopListening();
          this.showToast('Maximum listening time reached', 'info');
        }
      }, this.config.timeout);
    }
  }

  handleResult(event) {
    let interimTranscript = '';
    let finalTranscript = '';

    // Process all results
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript;
      
      if (event.results[i].isFinal) {
        finalTranscript += transcript;
      } else {
        interimTranscript += transcript;
      }
    }

    // Store previous interim transcript before updating (needed for proper removal)
    const previousInterimTranscript = this.interimTranscript;

    // Update transcripts
    this.interimTranscript = interimTranscript;
    if (finalTranscript) {
      this.finalTranscript += finalTranscript;
    }

    // Update input field
    if (this.currentInput && this.config.showInterim) {
      this.updateInputText(interimTranscript || finalTranscript, previousInterimTranscript);
    }
  }

  updateInputText(transcript, previousInterimTranscript = '') {
    if (!this.currentInput) return;
    
    const input = this.currentInput;
    const currentValue = input.value || '';
    
    if (this.config.insertAtCursor) {
      // Insert at cursor position
      const cursorPos = input.selectionStart || currentValue.length;
      const beforeCursor = currentValue.slice(0, cursorPos);
      const afterCursor = currentValue.slice(input.selectionEnd || cursorPos);
      
      // Remove previous interim text if any (use the passed parameter, not current value)
      // This ensures we remove the old interim text even if it has a different length
      const oldInterim = previousInterimTranscript || this.interimTranscript;
      const cleanBefore = oldInterim ? beforeCursor.replace(oldInterim, '') : beforeCursor;
      
      // Build new value
      const newValue = cleanBefore + this.finalTranscript + transcript + afterCursor;
      input.value = newValue;
      
      // Set cursor position
      const newPos = cleanBefore.length + this.finalTranscript.length + transcript.length;
      input.setSelectionRange(newPos, newPos);
    } else {
      // Replace entire value
      input.value = this.finalTranscript + transcript;
    }
    
    // Trigger input event
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    
    // Focus input
    input.focus();
  }

  handleError(event) {
    console.error('Speech recognition error:', event.error);
    
    let errorMessage = 'Voice input error';
    let errorType = 'error';
    
    switch (event.error) {
      case 'no-speech':
        errorMessage = 'No speech detected. Please try again.';
        errorType = 'info';
        break;
      case 'audio-capture':
        errorMessage = 'Microphone not found or not accessible.';
        break;
      case 'not-allowed':
        this.permissionState = 'denied';
        errorMessage = 'Microphone permission denied. Please enable it in your browser settings.';
        this.updatePermissionUI();
        break;
      case 'network':
        errorMessage = 'Network error. Please check your connection.';
        break;
      case 'aborted':
        // User stopped or timeout - not really an error
        return;
      case 'service-not-allowed':
        errorMessage = 'Speech recognition service not allowed.';
        break;
      default:
        errorMessage = `Voice input error: ${event.error}`;
    }
    
    this.showToast(errorMessage, errorType);
    this.stopListening();
  }

  handleEnd() {
    this.isListening = false;
    
    if (this.timeoutId) {
      clearTimeout(this.timeoutId);
      this.timeoutId = null;
    }
    
    if (this.currentInput) {
      // Finalize the transcript
      if (this.finalTranscript || this.interimTranscript) {
        const finalText = this.finalTranscript + this.interimTranscript;
        // Pass current interim transcript so it gets removed properly
        this.updateInputText(finalText, this.interimTranscript);
        
        // Auto-submit if configured
        if (this.config.autoSubmit && finalText.trim()) {
          const form = this.currentInput.closest('form');
          if (form) {
            setTimeout(() => {
              form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
            }, 100);
          }
        }
      }
      
      this.updateButtonState(this.currentInput, false);
      this.hideListeningIndicator();
    }
    
    // Reset transcripts
    this.interimTranscript = '';
    this.finalTranscript = '';
    this.currentInput = null;
    this.currentButton = null;
  }

  attachToAllInputs() {
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => this.addVoiceButtons());
    } else {
      this.addVoiceButtons();
    }

    // Watch for dynamically added inputs
    const observer = new MutationObserver(() => {
      this.addVoiceButtons();
    });
    observer.observe(document.body, { 
      childList: true, 
      subtree: true,
      attributes: true,
      attributeFilter: ['data-voice-attached']
    });
  }

  addVoiceButtons() {
    // Find all text inputs and textareas that don't already have voice buttons
    const inputs = document.querySelectorAll(
      'input[type="text"], input[type="search"], textarea, input:not([type])'
    );
    
    inputs.forEach(input => {
      // Skip if already processed
      if (input.hasAttribute('data-voice-attached')) {
        return;
      }

      // Skip readonly, disabled, or special input types
      if (input.readOnly || input.disabled) {
        return;
      }

      // Skip number, email, password, etc.
      const skipTypes = ['number', 'email', 'password', 'tel', 'url', 'date', 'time'];
      if (skipTypes.includes(input.type)) {
        return;
      }

      // Skip if parent says no voice
      if (input.closest('[data-no-voice]')) {
        return;
      }

      this.addVoiceButton(input);
    });
  }

  addVoiceButton(input) {
    // Mark as processed
    input.setAttribute('data-voice-attached', 'true');

    // Create wrapper if input doesn't have one
    let wrapper = input.parentElement;
    if (!wrapper || !wrapper.classList.contains('input-with-voice')) {
      wrapper = document.createElement('div');
      wrapper.className = 'input-with-voice';
      input.parentNode.insertBefore(wrapper, input);
      wrapper.appendChild(input);
    }

    // Check if button already exists
    if (wrapper.querySelector('.voice-input-btn')) {
      return;
    }

    // Create voice button
    const voiceBtn = document.createElement('button');
    voiceBtn.type = 'button';
    voiceBtn.className = 'voice-input-btn';
    voiceBtn.setAttribute('aria-label', 'Start voice input');
    voiceBtn.setAttribute('role', 'button');
    voiceBtn.setAttribute('tabindex', '0');
    voiceBtn.innerHTML = '<span class="voice-icon" aria-hidden="true">🎤</span>';
    voiceBtn.title = 'Click to speak (Voice input)';

    // Click handler
    voiceBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.toggleListening(input, voiceBtn);
    });

    // Keyboard handler
    voiceBtn.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        this.toggleListening(input, voiceBtn);
      }
    });

    wrapper.appendChild(voiceBtn);
  }

  toggleListening(input, button) {
    if (this.isListening) {
      if (this.currentInput === input) {
        // Stop listening
        this.stopListening();
      } else {
        // Switch to different input
        this.stopListening();
        setTimeout(() => {
          this.startListening(input, button);
        }, 200);
      }
    } else {
      this.startListening(input, button);
    }
  }

  startListening(input, button) {
    if (!this.recognition) {
      this.showToast('Voice input not supported in this browser', 'error');
      return;
    }

    // Check permission
    if (this.permissionState === 'denied') {
      this.showToast('Microphone permission denied. Please enable it in browser settings.', 'error');
      return;
    }

    this.currentInput = input;
    this.currentButton = button;
    input.focus();
    
    // Check for auto-submit config on form
    const form = input.closest('form');
    if (form && form.hasAttribute('data-voice-auto-submit')) {
      this.config.autoSubmit = form.getAttribute('data-voice-auto-submit') === 'true';
    }
    
    try {
      this.recognition.start();
    } catch (error) {
      console.error('Failed to start speech recognition:', error);
      
      if (error.name === 'InvalidStateError') {
        // Already listening, stop first
        this.recognition.stop();
        setTimeout(() => {
          try {
            this.recognition.start();
          } catch (e2) {
            this.showToast('Voice input is already active', 'info');
          }
        }, 100);
      } else {
        this.showToast('Failed to start voice input. Please try again.', 'error');
        this.updateButtonState(input, false);
      }
    }
  }

  stopListening() {
    if (this.recognition && this.isListening) {
      try {
        this.recognition.stop();
      } catch (error) {
        // Ignore errors when stopping
        console.debug('Error stopping recognition:', error);
      }
    }
    
    if (this.timeoutId) {
      clearTimeout(this.timeoutId);
      this.timeoutId = null;
    }
    
    this.isListening = false;
    if (this.currentInput) {
      this.updateButtonState(this.currentInput, false);
      this.hideListeningIndicator();
    }
  }

  updateButtonState(input, listening) {
    const wrapper = input.closest('.input-with-voice');
    if (!wrapper) return;

    const button = wrapper.querySelector('.voice-input-btn');
    if (!button) return;

    if (listening) {
      button.classList.add('listening');
      button.setAttribute('aria-label', 'Stop voice input');
      button.setAttribute('aria-pressed', 'true');
      button.title = 'Listening... Click to stop';
      button.innerHTML = '<span class="voice-icon" aria-hidden="true">🔴</span>';
    } else {
      button.classList.remove('listening');
      button.setAttribute('aria-label', 'Start voice input');
      button.setAttribute('aria-pressed', 'false');
      button.title = 'Click to speak (Voice input)';
      button.innerHTML = '<span class="voice-icon" aria-hidden="true">🎤</span>';
    }
  }

  showListeningIndicator() {
    if (!this.currentInput) return;
    
    // Add visual indicator
    const wrapper = this.currentInput.closest('.input-with-voice');
    if (wrapper) {
      wrapper.classList.add('voice-listening');
    }
    
    // Update placeholder
    const originalPlaceholder = this.currentInput.getAttribute('data-original-placeholder') || 
                                this.currentInput.placeholder;
    this.currentInput.setAttribute('data-original-placeholder', originalPlaceholder);
    this.currentInput.placeholder = '🎤 Listening...';
  }

  hideListeningIndicator() {
    if (!this.currentInput) return;
    
    const wrapper = this.currentInput.closest('.input-with-voice');
    if (wrapper) {
      wrapper.classList.remove('voice-listening');
    }
    
    // Restore placeholder
    const originalPlaceholder = this.currentInput.getAttribute('data-original-placeholder');
    if (originalPlaceholder !== null) {
      this.currentInput.placeholder = originalPlaceholder;
      this.currentInput.removeAttribute('data-original-placeholder');
    }
  }

  updatePermissionUI() {
    // Update all voice buttons based on permission state
    const buttons = document.querySelectorAll('.voice-input-btn');
    buttons.forEach(btn => {
      if (this.permissionState === 'denied') {
        btn.classList.add('permission-denied');
        btn.title = 'Microphone permission denied';
      } else {
        btn.classList.remove('permission-denied');
      }
    });
  }

  hideAllVoiceButtons() {
    const buttons = document.querySelectorAll('.voice-input-btn');
    buttons.forEach(btn => {
      btn.style.display = 'none';
    });
  }

  showToast(message, type = 'info') {
    // Use existing toast system if available
    if (typeof showToast === 'function') {
      showToast(message, type);
      return;
    }
    
    // Fallback: simple alert
    console.log(`[Voice Input ${type}]:`, message);
  }

  // Public API
  setConfig(config) {
    this.config = { ...this.config, ...config };
    if (this.recognition) {
      this.recognition.continuous = this.config.continuous;
      this.recognition.interimResults = this.config.interimResults;
      this.recognition.lang = this.config.lang;
    }
  }

  getConfig() {
    return { ...this.config };
  }
}

// Initialize voice input when script loads
let voiceInputInstance = null;
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    voiceInputInstance = new VoiceInput();
  });
} else {
  voiceInputInstance = new VoiceInput();
}

// Export for use in other scripts
window.VoiceInput = VoiceInput;
window.voiceInput = voiceInputInstance;

