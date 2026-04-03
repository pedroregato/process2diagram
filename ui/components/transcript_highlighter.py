# ui/components/transcript_highlighter.py
import html
import streamlit.components.v1 as components

def render_highlighted_transcript(clean_text, inconsistencies):
    if not inconsistencies:
        components.html(
            f"<div style='height:400px;overflow-y:scroll;font-family:monospace;padding:1rem;border:1px solid #ccc'>{html.escape(clean_text).replace(chr(10), '<br>')}</div>",
            height=420,
        )
        return
    spans = []
    for inc in inconsistencies:
        candidates = [f"[? {inc.text.rstrip('.')}]", f"[? {inc.text}]", inc.text]
        for cand in candidates:
            idx = clean_text.find(cand)
            if idx >= 0:
                spans.append((idx, idx + len(cand), inc.reason))
                break
    spans.sort(key=lambda s: s[0])
    merged = []
    for s in spans:
        if merged and s[0] < merged[-1][1]:
            continue
        merged.append(s)
    parts = []
    prev = 0
    for start, end, reason in merged:
        parts.append(html.escape(clean_text[prev:start]))
        tooltip = html.escape(reason[:120])
        highlighted = html.escape(clean_text[start:end])
        parts.append(f'<mark title="{tooltip}" style="background:#fef08a;cursor:help">{highlighted}</mark>')
        prev = end
    parts.append(html.escape(clean_text[prev:]))
    body = "".join(parts).replace("\n", "<br>")
    components.html(
        f"<div style='height:400px;overflow-y:scroll;font-family:monospace;padding:1rem;border:1px solid #ccc'>{body}</div>",
        height=420,
    )
