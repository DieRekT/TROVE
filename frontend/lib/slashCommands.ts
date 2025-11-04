export type SlashCommand = {
  type: 'context' | 'cite' | 'clear' | 'none';
  args?: string;
};

export function parseSlashCommand(input: string): SlashCommand {
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

export function handleSlashCommand(
  command: SlashCommand,
  callbacks: {
    onContext?: () => void;
    onCite?: (args?: string) => void;
    onClear?: () => void;
  }
): string | null {
  switch (command.type) {
    case 'context':
      if (callbacks.onContext) {
        callbacks.onContext();
      }
      return null; // Don't send to backend

    case 'cite':
      if (callbacks.onCite) {
        callbacks.onCite(command.args);
      }
      return null; // Don't send to backend

    case 'clear':
      if (callbacks.onClear) {
        callbacks.onClear();
      }
      return null; // Don't send to backend

    default:
      return null; // No special handling
  }
}

