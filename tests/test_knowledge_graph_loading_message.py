# tests/test_knowledge_graph_loading_message.py
"""
UX-14 (melhorias/ux-amigabilidade-e-elegancia.md, Onda C): pages/
KnowledgeGraph.py mostrava só o "Running..." generico do Streamlit
enquanto _build_pyvis_graph() computava o grafo (~30s num contexto com
150 entidades/608 arestas, antes do cache do NAV-17/PC224) -- sem
nenhuma pista do que estava acontecendo.

Fix: st.spinner(f"Calculando grafo de {n} entidades...") envolvendo a
chamada -- só aparece de fato num cache miss, ja que _build_pyvis_graph()
e cacheada (@st.cache_data, PC224); em cache hits o spinner nem chega a
piscar na tela.

pages/CostBenefitScenarios.py (o outro alvo original do UX-14) foi
avaliado e EXCLUIDO: o arquivo e Python puro, sem LLM/rede (comentario no
cabecalho do proprio arquivo); a lentidao medida originalmente (~30s) era
causada pelo numero de widgets renderizados via st.tabs(), ja corrigido
no PC225 (st.tabs -> st.radio) -- nao ha calculo genuinamente lento
sobrando pra justificar um spinner com mensagem especifica.

st.spinner() e um context manager sem representacao persistente na
arvore de elementos do AppTest (o texto só existe durante a execucao,
nao depois) -- checagem estatica, mesmo padrao usado pra outros
elementos transientes nesta sessao.
"""

from pathlib import Path

_KG_SRC = (
    Path(__file__).resolve().parent.parent / "pages" / "KnowledgeGraph.py"
).read_text(encoding="utf-8")


class TestSpinnerWrapsTheExpensiveCall:
    def test_spinner_message_mentions_entity_count(self):
        anchor = _KG_SRC.index('with st.spinner(f"Calculando grafo de')
        block = _KG_SRC[anchor:anchor + 400]
        assert "_n_nodes_est" in block
        assert "entidades" in block

    def test_build_pyvis_graph_call_is_nested_inside_the_spinner_block(self):
        spinner_idx = _KG_SRC.index('with st.spinner(f"Calculando grafo de')
        call_idx = _KG_SRC.index("_build_pyvis_graph(", spinner_idx)
        # A chamada deve vir logo depois do spinner, nao antes (senao o
        # spinner nao cobre o trabalho de verdade) nem numa secao distante.
        assert 0 < call_idx - spinner_idx < 200

    def test_node_count_estimate_respects_the_max_nodes_cap(self):
        anchor = _KG_SRC.index("_n_nodes_est = ")
        line = _KG_SRC[anchor:anchor + 80]
        assert "min(max_nodes, len(entities))" in line


class TestCostBenefitScenariosDeliberatelyUnchanged:
    def test_cost_benefit_scenarios_has_no_new_spinner_for_ux14(self):
        src = (
            Path(__file__).resolve().parent.parent / "pages" / "CostBenefitScenarios.py"
        ).read_text(encoding="utf-8")
        assert "Calculando" not in src, (
            "CostBenefitScenarios.py ganhou um spinner de 'Calculando...' -- "
            "revisar a nota do PC225/UX-14: a lentidao real era widgets "
            "(st.tabs), ja corrigida; nao ha calculo lento a anunciar aqui"
        )
