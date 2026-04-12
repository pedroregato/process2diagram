# ui/components/copy_button.py
import json
import streamlit.components.v1 as components


def copy_button(text: str, key: str, label: str = "📋 Copy to Clipboard", compact: bool = False):
    """Clipboard copy button rendered as an inline HTML component.

    Args:
        text:    Text to copy.
        key:     Unique HTML element ID suffix.
        label:   Button label (shown and restored after 2 s).
        compact: If True, renders a smaller pill-style button (height=28).
                 Use compact=True inside st.chat_message to avoid whitespace.
    """
    safe = json.dumps(text)
    if compact:
        style = (
            "padding:3px 10px;border:1px solid #cbd5e1;border-radius:20px;"
            "background:transparent;cursor:pointer;font-size:0.75rem;"
            "font-family:'Inter',sans-serif;font-weight:500;color:#94a3b8;"
            "line-height:1.4;"
        )
        height = 28
    else:
        style = (
            "padding:8px 16px;border:1px solid #cbd5e1;border-radius:8px;"
            "background:#ffffff;cursor:pointer;font-size:0.85rem;"
            "font-family:'Inter',sans-serif;font-weight:500;color:#475569;"
        )
        height = 45

    components.html(
        f"""
        <button id="cbtn_{key}"
          onclick="(function(){{
            var el = document.createElement('textarea');
            el.value = {safe};
            el.style.position='fixed'; el.style.opacity='0';
            document.body.appendChild(el);
            el.focus(); el.select();
            try {{ document.execCommand('copy'); }} catch(e) {{}}
            document.body.removeChild(el);
            var b = document.getElementById('cbtn_{key}');
            b.innerHTML = '✅';
            b.style.borderColor = '#22c55e';
            b.style.color = '#22c55e';
            setTimeout(function(){{
                b.innerHTML = {json.dumps(label)};
                b.style.borderColor = '#cbd5e1';
                b.style.color = '{'#94a3b8' if compact else '#475569'}';
            }}, 2000);
          }})()"
          style="{style}">
          {label}
        </button>
        """,
        height=height,
    )
