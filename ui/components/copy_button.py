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

    Strategy (most-reliable first):
      1. navigator.clipboard.writeText()  — works in HTTPS when the component
         iframe has allow="clipboard-write" (Streamlit sets this) and the click
         is the active user gesture in the SAME iframe document.
      2. Parent-document execCommand     — creates a hidden textarea in the
         same-origin parent frame and uses execCommand('copy') there; works in
         local HTTP dev where navigator.clipboard requires a secure context.
      3. Iframe execCommand              — last resort; deprecated but broadly
         supported in most browsers as of 2025.
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
        <button id="cbtn_{key}"
          onclick="(function(){{
            var text = {safe};
            var b = document.getElementById('cbtn_{key}');
            function _ok() {{
              b.innerHTML = '✅';
              b.style.borderColor = '#22c55e';
              b.style.color = '#22c55e';
              setTimeout(function(){{
                b.innerHTML = {json.dumps(label)};
                b.style.borderColor = '#cbd5e1';
                b.style.color = '{restore_color}';
              }}, 2000);
            }}
            // Strategy 2: parent-document execCommand (same-origin, HTTP-safe)
            function _parent_exec() {{
              try {{
                var pd = window.parent && window.parent.document;
                if (!pd) return false;
                var ta = pd.createElement('textarea');
                ta.value = text;
                ta.style.cssText = 'position:fixed;left:-9999px;opacity:0;pointer-events:none;';
                pd.body.appendChild(ta);
                ta.focus(); ta.select();
                var ok = pd.execCommand('copy');
                pd.body.removeChild(ta);
                if (ok) {{ _ok(); return true; }}
              }} catch(e) {{}}
              return false;
            }}
            // Strategy 3: in-iframe execCommand (last resort)
            function _iframe_exec() {{
              var ta = document.createElement('textarea');
              ta.value = text;
              ta.style.cssText = 'position:fixed;left:-9999px;opacity:0;';
              document.body.appendChild(ta);
              ta.focus(); ta.select();
              try {{ document.execCommand('copy'); _ok(); }} catch(e) {{}}
              document.body.removeChild(ta);
            }}
            // Strategy 1: navigator.clipboard (HTTPS + allow="clipboard-write")
            // Must be called on the SAME document that has focus (the iframe),
            // NOT window.parent.navigator.clipboard — Chrome v102+ rejects that.
            if (navigator.clipboard && window.isSecureContext) {{
              navigator.clipboard.writeText(text).then(_ok, function() {{
                if (!_parent_exec()) _iframe_exec();
              }});
            }} else {{
              if (!_parent_exec()) _iframe_exec();
            }}
          }})()"
          style="{style}">
          {label}
        </button>
        """,
        height=height,
    )
