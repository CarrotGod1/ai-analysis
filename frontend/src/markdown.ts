function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// Minimal, safe renderer for LLM replies: fenced code, inline code, bold, bullet lists, line breaks.
export function renderReply(raw: string): string {
  const blocks = raw.split(/```([\s\S]*?)```/g);
  let html = "";
  blocks.forEach((block, i) => {
    if (i % 2 === 1) {
      const codeText = block.replace(/^\w*\n/, "");
      html += `<pre class="reply-code"><code>${escapeHtml(codeText)}</code></pre>`;
      return;
    }
    const escaped = escapeHtml(block);
    const withInline = escaped
      .replace(/`([^`]+)`/g, '<code class="reply-inline-code">$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

    const lines = withInline.split("\n");
    let listOpen = false;
    let out = "";
    for (const line of lines) {
      const bullet = line.match(/^\s*[-*]\s+(.*)$/);
      if (bullet) {
        if (!listOpen) {
          out += "<ul>";
          listOpen = true;
        }
        out += `<li>${bullet[1]}</li>`;
        continue;
      }
      if (listOpen) {
        out += "</ul>";
        listOpen = false;
      }
      if (line.trim() === "") {
        out += "<br>";
      } else {
        out += `<p>${line}</p>`;
      }
    }
    if (listOpen) out += "</ul>";
    html += out;
  });
  return html;
}
