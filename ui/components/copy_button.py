# ui/components/copy_button.py
import json
import streamlit.components.v1 as components

def copy_button(text: str, key: str, label: str = "📋 Copy to Clipboard"):
    safe = json.dumps(text)
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
            b.innerHTML = '✅ Copied!';
            b.style.borderColor = '#22c55e';
            b.style.color = '#22c55e';
            setTimeout(function(){{ 
                b.innerHTML = '{label}'; 
                b.style.borderColor = '#cbd5e1';
                b.style.color = '#475569';
            }}, 2000);
          }})()"
          style="padding:8px 16px;border:1px solid #cbd5e1;border-radius:8px;
                 background:#ffffff;cursor:pointer;font-size:0.85rem;
                 font-family:'Inter',sans-serif;font-weight:500;color:#475569;">
          {label}
        </button>
        """,
        height=45,
    )
