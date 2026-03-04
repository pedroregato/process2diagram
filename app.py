from __future__ import annotations
import streamlit as st
from modules.config import Settings
from modules.ingest import load_transcript
from modules.preprocess import preprocess_transcript
from modules.extract_heuristic import extract_process_heuristic
from modules.diagram_mermaid import to_mermaid_flowchart
from modules.diagram_drawio import to_drawio_xml
from modules.utils import to_json

st.set_page_config(page_title="Process → Diagram (PoC)", layout="wide")
settings = Settings()

st.title("Process → Diagram (PoC)")
st.caption("Cole a transcrição, extraia o processo e gere diagrama (Mermaid + draw.io).")

with st.sidebar:
    st.subheader("Opções")
    proc_name = st.text_input("Nome do processo", value="Process")
    extractor = st.selectbox(
        "Extrator",
        options=["Heurístico (sem LLM)"],
        index=0,
        help="Deixo LLM para plugar depois."
    )
    st.divider()
    st.write("Saídas")
    show_json = st.checkbox("Mostrar JSON estruturado", value=True)
    show_mermaid = st.checkbox("Mostrar Mermaid", value=True)

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Entrada")
    transcript = st.text_area(
        "Transcrição da reunião",
        height=320,
        placeholder="Cole aqui a transcrição (texto livre)."
    )
    run = st.button("Gerar diagrama", type="primary")

with col2:
    st.subheader("Dicas de entrada")
    st.markdown(
        "- Se houver **passos numerados** (1), 2), etc.) a heurística melhora.\n"
        "- Bullets (•, -) também ajudam.\n"
        "- Se for texto corrido, ela tenta separar por conectores (depois, então...)."
    )

if run:
    raw = load_transcript(transcript)
    if not raw:
        st.error("Cole alguma transcrição antes de gerar.")
        st.stop()

    clean = preprocess_transcript(raw)
    proc = extract_process_heuristic(clean, name=proc_name)

    mermaid = to_mermaid_flowchart(proc)
    drawio_xml = to_drawio_xml(proc)

    st.success("Processo extraído e diagramas gerados.")

    out1, out2 = st.columns([1, 1])

    with out1:
        st.subheader("Pré-processado")
        st.text_area("Texto limpo", value=clean, height=220)

        if show_json:
            st.subheader("Estrutura (JSON)")
            st.code(to_json(proc), language="json")

        st.download_button(
            "Baixar draw.io (.drawio)",
            data=drawio_xml.encode("utf-8"),
            file_name=f"{proc_name.replace(' ', '_')}.drawio",
            mime="application/xml",
        )

    with out2:
        if show_mermaid:
            st.subheader("Diagrama (Mermaid)")
            # Render Mermaid via HTML
            html = f"""
            <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
            <div class="mermaid">
            {mermaid}
            </div>
            <script>
              mermaid.initialize({{ startOnLoad: true }});
            </script>
            """
            st.components.v1.html(html, height=520, scrolling=True)

        st.subheader("Código Mermaid")
        st.code(mermaid, language="text")
