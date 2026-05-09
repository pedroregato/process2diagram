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

    Strategy:
      1. navigator.clipboard.writeText() — preferred when browser grants
         clipboard-write permission to the iframe (Chrome/Edge/Firefox HTTPS).
      2. execCommand('copy') fallback — textarea in the iframe, focused and
         selected within the same user-gesture, then immediately removed.
         Does NOT use opacity:0 (prevents focus in some browsers).
         Does NOT try window.parent (always throws SecurityError cross-origin).
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

    restore_color = '#94a3b8' if compact else '#475569'
    components.html(
        f"""
        <script>
        function _cbtn_{key}() {{
          var text = {safe};
          var b    = document.getElementById('cbtn_{key}');

          function _ok() {{
            b.textContent = '\u2705';
            b.style.borderColor = '#22c55e';
            b.style.color       = '#22c55e';
            setTimeout(function() {{
              b.textContent       = {json.dumps(label)};
              b.style.borderColor = '#cbd5e1';
              b.style.color       = '{restore_color}';
            }}, 2000);
          }}

          function _execFallback() {{
            var ta = document.createElement('textarea');
            ta.value = text;
            ta.style.cssText = 'position:fixed;top:0;left:0;width:2em;height:2em;'
              + 'padding:0;border:none;outline:none;box-shadow:none;background:transparent;';
            document.body.appendChild(ta);
            ta.focus();
            ta.select();
            try {{ document.execCommand('copy'); _ok(); }} catch(e) {{}}
            document.body.removeChild(ta);
          }}

          if (navigator.clipboard && navigator.clipboard.writeText) {{
            navigator.clipboard.writeText(text).then(_ok, _execFallback);
          }} else {{
            _execFallback();
          }}
        }}
        </script>
        <button id="cbtn_{key}" onclick="_cbtn_{key}()" style="{style}">
          {label}
        </button>
        """,
        height=height,
    )
