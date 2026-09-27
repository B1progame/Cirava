const INLINE_PATTERN = /\[([^\]]+)\]\((https:\/\/[^\s)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*|__([^_]+)__|\*([^*]+)\*|_([^_]+)_/g;

function appendInline(parent, text) {
  let cursor = 0;
  for (const match of text.matchAll(INLINE_PATTERN)) {
    const index = match.index ?? 0;
    if (index > cursor) parent.append(document.createTextNode(text.slice(cursor, index)));
    let node;
    if (match[2]) {
      node = document.createElement('a');
      node.href = match[2];
      node.rel = 'noopener noreferrer';
      node.target = '_blank';
      node.textContent = match[1];
    } else if (match[3]) {
      node = document.createElement('code'); node.textContent = match[3];
    } else if (match[4] || match[5]) {
      node = document.createElement('strong'); node.textContent = match[4] || match[5];
    } else {
      node = document.createElement('em'); node.textContent = match[6] || match[7];
    }
    parent.append(node);
    cursor = index + match[0].length;
  }
  if (cursor < text.length) parent.append(document.createTextNode(text.slice(cursor)));
}

/** Render release-note Markdown using DOM text nodes; release text is never treated as HTML. */
export function renderUpdateMarkdown(container, markdown, version = '') {
  const source = String(markdown || '').replace(/\r\n?/g, '\n').slice(0, 64 * 1024);
  let lines = source.split('\n');
  const firstContent = lines.findIndex((line) => line.trim());
  if (firstContent >= 0) {
    const heading = lines[firstContent].match(/^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$/)?.[1]?.trim();
    if (heading && version && heading.replace(/^[vV]/, '') === String(version).replace(/^[vV]/, '')) {
      lines = lines.slice(0, firstContent).concat(lines.slice(firstContent + 1));
    }
  }

  container.replaceChildren();
  let list = null;
  let paragraph = [];
  const flushParagraph = () => {
    if (!paragraph.length) return;
    const node = document.createElement('p');
    appendInline(node, paragraph.join(' '));
    container.append(node);
    paragraph = [];
  };
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) { flushParagraph(); list = null; continue; }
    const heading = trimmed.match(/^(#{1,4})\s+(.+?)\s*#*$/);
    if (heading) {
      flushParagraph(); list = null;
      const node = document.createElement(`h${Math.min(4, heading[1].length + 1)}`);
      appendInline(node, heading[2]); container.append(node); continue;
    }
    const bullet = trimmed.match(/^[-*+]\s+(.+)$/);
    const ordered = trimmed.match(/^\d+[.)]\s+(.+)$/);
    if (bullet || ordered) {
      flushParagraph();
      const kind = ordered ? 'ol' : 'ul';
      if (!list || list.tagName.toLowerCase() !== kind) {
        list = document.createElement(kind); container.append(list);
      }
      const item = document.createElement('li'); appendInline(item, (bullet || ordered)[1]); list.append(item); continue;
    }
    const quote = trimmed.match(/^>\s?(.*)$/);
    if (quote) {
      flushParagraph(); list = null;
      const node = document.createElement('blockquote'); appendInline(node, quote[1]); container.append(node); continue;
    }
    if (/^(---+|\*\*\*+|___+)$/.test(trimmed)) { flushParagraph(); list = null; container.append(document.createElement('hr')); continue; }
    list = null;
    paragraph.push(trimmed);
  }
  flushParagraph();
  container.hidden = container.childElementCount === 0;
}

export function releaseNotesMarkdown(markdown, notes, version = '') {
  if (typeof markdown === 'string' && markdown.trim()) return markdown;
  const lines = Array.isArray(notes) ? notes.filter((line) => typeof line === 'string' && line.trim()) : [];
  return lines.length ? `## ${version ? `What's new in ${version}` : 'Highlights'}\n\n${lines.map((line) => `- ${line}`).join('\n')}` : '';
}
