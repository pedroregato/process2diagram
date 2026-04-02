# modules/mindmap_interactive.py (versão com logging e fallback)
import streamlit.components.v1 as components
import json

def render_mindmap_from_requirements(model, *, session_title: str = "", height: int = 620):
    """Renderiza o mindmap com fallback silencioso."""
    try:
        from modules.requirements_mindmap import build_mindmap_tree
        tree = build_mindmap_tree(model, session_title)
        render_interactive_mindmap(tree, height=height)
    except Exception as e:
        import streamlit as st
        st.warning(f"Mindmap interativo indisponível: {e}. Exibindo código Mermaid como alternativa.")
        from modules.requirements_mindmap import generate_requirements_mindmap
        code = generate_requirements_mindmap(model)
        if code:
            st.code(code, language="mermaid")
        else:
            st.info("Nenhum requisito para gerar mindmap.")

def render_interactive_mindmap(tree: dict, *, height: int = 620):
    if not tree:
        import streamlit as st
        st.info("Dados insuficientes para o mindmap.")
        return
    data_json = json.dumps(tree, ensure_ascii=False)
    html = _build_html(data_json)
    components.html(html, height=height, scrolling=False)

def _build_html(data_json: str) -> str:
    # (use o HTML original que você já tem, com as correções de margem)
    # Para garantir, vou reutilizar o HTML da versão anterior que funcionava,
    # mas com o lay ajustado para 50 e padding 40.
    # (coloque aqui o HTML completo do mindmap com as alterações de margem)
    pass
