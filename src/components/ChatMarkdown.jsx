import React from 'react';

/** Escape HTML entities for safe text nodes (we render via React, not dangerouslySetInnerHTML). */
function inlineNodes(text, keyPrefix = 'i') {
  if (!text) return null;
  // Split on **bold** and *italic* (non-greedy)
  const parts = String(text).split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return parts.map((part, idx) => {
    const key = `${keyPrefix}-${idx}`;
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return (
        <strong key={key} className="font-semibold">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2 && !part.startsWith('**')) {
      return (
        <em key={key} className="italic">
          {part.slice(1, -1)}
        </em>
      );
    }
    return <React.Fragment key={key}>{part}</React.Fragment>;
  });
}

/**
 * Light markdown for chat bubbles: bold/italic, bullet & numbered lists.
 * Strips decorative --- rules that look like "loads of dashes" as plain text.
 */
export function ChatMarkdown({ content, className = '' }) {
  const raw = String(content || '')
    .replace(/\r\n/g, '\n')
    // Drop horizontal-rule lines (---, ***, ___)
    .replace(/^[ \t]*(-{3,}|\*{3,}|_{3,})[ \t]*$/gm, '')
    // Collapse 3+ blank lines after stripping rules
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  if (!raw) return null;

  const lines = raw.split('\n');
  const blocks = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const bullet = line.match(/^[ \t]*[-•*]\s+(.+)$/);
    const numbered = line.match(/^[ \t]*(\d+)[.)]\s+(.+)$/);

    if (bullet) {
      const items = [];
      while (i < lines.length) {
        const m = lines[i].match(/^[ \t]*[-•*]\s+(.+)$/);
        if (!m) break;
        items.push(m[1]);
        i += 1;
      }
      blocks.push({ type: 'ul', items });
      continue;
    }

    if (numbered) {
      const items = [];
      while (i < lines.length) {
        const m = lines[i].match(/^[ \t]*\d+[.)]\s+(.+)$/);
        if (!m) break;
        items.push(m[1]);
        i += 1;
      }
      blocks.push({ type: 'ol', items });
      continue;
    }

    // Blank line → paragraph break
    if (!line.trim()) {
      i += 1;
      continue;
    }

    // Gather consecutive non-list, non-blank lines into a paragraph
    const para = [];
    while (i < lines.length) {
      const l = lines[i];
      if (!l.trim()) break;
      if (/^[ \t]*[-•*]\s+/.test(l) || /^[ \t]*\d+[.)]\s+/.test(l)) break;
      if (/^[ \t]*(-{3,}|\*{3,}|_{3,})[ \t]*$/.test(l)) {
        i += 1;
        break;
      }
      para.push(l.trim());
      i += 1;
    }
    if (para.length) {
      blocks.push({ type: 'p', text: para.join(' ') });
    }
  }

  return (
    <div className={`space-y-2 text-sm leading-relaxed ${className}`}>
      {blocks.map((block, idx) => {
        if (block.type === 'ul') {
          return (
            <ul key={`b-${idx}`} className="list-disc pl-4 space-y-1">
              {block.items.map((item, j) => (
                <li key={`u-${idx}-${j}`}>{inlineNodes(item, `u${idx}${j}`)}</li>
              ))}
            </ul>
          );
        }
        if (block.type === 'ol') {
          return (
            <ol key={`b-${idx}`} className="list-decimal pl-4 space-y-1">
              {block.items.map((item, j) => (
                <li key={`o-${idx}-${j}`}>{inlineNodes(item, `o${idx}${j}`)}</li>
              ))}
            </ol>
          );
        }
        return (
          <p key={`b-${idx}`}>{inlineNodes(block.text, `p${idx}`)}</p>
        );
      })}
    </div>
  );
}

export default ChatMarkdown;
