# tests/test_agent_bpmn_canonical_patterns.py
"""
Tests for the canonical pattern few-shot mechanism in agents/agent_bpmn.py
(PC111 — "Few-Shot Learning Nível 3").

Regression guard for a real bug found 2026-07-04: none of the pattern JSON
files in agents/agent_bpmn/examples/ had a `trigger_signals` field, so
_select_canonical_pattern() always scored 0 hits for every pattern and never
matched — the whole auto-injection mechanism was silently dead since PC111,
with zero test coverage catching it.
"""

from agents.agent_bpmn import AgentBPMN, _load_canonical_patterns


class TestPatternsHaveTriggerSignals:
    def test_every_selectable_pattern_has_nonempty_trigger_signals(self):
        patterns = _load_canonical_patterns()
        assert patterns, "no canonical patterns loaded — examples/ directory empty or unreadable"
        for pid, pattern in patterns.items():
            signals = pattern.get("trigger_signals")
            assert signals, f"pattern '{pid}' has no trigger_signals — _select_canonical_pattern() can never match it"
            assert len(signals) >= 2, f"pattern '{pid}' needs >=2 signals to ever reach the >=2-hit threshold"

    def test_style_guide_excluded_from_selectable_patterns(self):
        patterns = _load_canonical_patterns()
        assert "bpmn_style_guide" not in patterns

    def test_new_collab_callactivity_pattern_loaded(self):
        patterns = _load_canonical_patterns()
        assert "bpmn_pattern_collab_callactivity_phases" in patterns


class TestSelectCanonicalPattern:
    def test_generic_transcript_matches_nothing(self):
        transcript = "O cliente liga para o suporte e pede ajuda com o produto."
        assert AgentBPMN._select_canonical_pattern(transcript) is None

    def test_single_signal_hit_is_not_enough(self):
        # Only one signal from collab_four_eyes ("dupla aprovação") — below the
        # >=2 threshold, must not match.
        transcript = "O processo depende de dupla aprovação para prosseguir."
        result = AgentBPMN._select_canonical_pattern(transcript)
        assert result is None or result.get("id") != "bpmn_pattern_collab_four_eyes"

    def test_four_eyes_pattern_matches_with_two_signals(self):
        transcript = (
            "O pagamento precisa de aprovação conjunta do gerente e do diretor — "
            "é um caso de dupla aprovação obrigatória antes de liberar o valor."
        )
        result = AgentBPMN._select_canonical_pattern(transcript)
        assert result is not None
        assert result.get("id") == "bpmn_pattern_collab_four_eyes"

    def test_periodic_continuous_pattern_matches(self):
        transcript = (
            "O atendimento acontece todo dia normalmente, mas o fechamento mensal "
            "roda como uma rotina periódica separada no final de cada mês."
        )
        result = AgentBPMN._select_canonical_pattern(transcript)
        assert result is not None
        assert result.get("id") == "bpmn_pattern_periodic_continuous"

    def test_collab_callactivity_phases_pattern_matches(self):
        transcript = (
            "A empresa firma um contrato de prestação de serviços com um fornecedor "
            "externo de consultoria contratada. Ao longo do contrato, a consultoria "
            "envia relatórios mensais para validação e pagamento, até o encerramento "
            "do contrato com avaliação final do fornecedor."
        )
        result = AgentBPMN._select_canonical_pattern(transcript)
        assert result is not None
        assert result.get("id") == "bpmn_pattern_collab_callactivity_phases"

    def test_collab_callactivity_phases_matches_varied_natural_phrasing(self):
        # PC123 regression: the original trigger_signals were near-exact
        # phrases lifted from prior OUTPUT vocabulary ("reabrir concorrência",
        # "avaliação final do fornecedor") — 2 of 3 plausible, naturally
        # phrased INPUT descriptions of this exact scenario scored 0 hits
        # against them (verb conjugation / word order differences broke the
        # substring match). These transcripts intentionally avoid the exact
        # phrasing used in the pattern's own transcript_excerpt.
        transcripts = [
            (
                "A empresa contratante precisa contratar uma consultoria especializada "
                "em transformação digital. O departamento de compras abre uma "
                "solicitação, elabora um termo de referência e envia para fornecedores "
                "pré-qualificados, como a TechAdvisor Ltda. Após receber as propostas, "
                "a empresa analisa e aprova uma, ou reabre a concorrência se nenhuma "
                "for aceita. Uma vez aprovada, o jurídico elabora o contrato e envia "
                "para assinatura da consultoria. Depois de assinado, o gerente do "
                "projeto define o escopo e o cronograma junto com o fornecedor. A "
                "execução ocorre com entregas mensais de relatórios, que são validados "
                "pelo gerente; se houver problemas, retornam para correção; se "
                "aprovados, o financeiro processa o pagamento e notifica o fornecedor. "
                "Isso se repete até a última entrega, quando é feita uma avaliação "
                "final do fornecedor e a documentação é arquivada."
            ),
            (
                "Contratação de consultoria de TI com uma empresa terceirizada. "
                "Processo de RFP, análise de propostas, assinatura de contrato, "
                "execução com entregas periódicas e encerramento com avaliação de "
                "desempenho do parceiro."
            ),
        ]
        for transcript in transcripts:
            result = AgentBPMN._select_canonical_pattern(transcript)
            assert result is not None, f"no pattern matched: {transcript[:60]}..."
            assert result.get("id") == "bpmn_pattern_collab_callactivity_phases"

    def test_collab_callactivity_phases_ideal_output_has_two_pools(self):
        patterns = _load_canonical_patterns()
        pattern = patterns["bpmn_pattern_collab_callactivity_phases"]
        pools = pattern["ideal_json_output"]["pools"]
        assert len(pools) == 2
        assert len(pattern["ideal_json_output"]["message_flows"]) == 6
        # Every callActivity step in the template must carry a description —
        # the pattern's own common_mistakes explicitly warns against this.
        for pool in pools:
            for step in pool["process"]["steps"]:
                if step["task_type"] == "callActivity":
                    assert step.get("description"), f"callActivity {step['id']} missing description"


class TestBuildPromptInjectsPattern:
    def test_build_prompt_injects_canonical_gabarito_marker(self):
        from unittest.mock import MagicMock
        from core.knowledge_hub import KnowledgeHub

        agent = MagicMock(spec=AgentBPMN)
        agent._skill = "SKILL PLACEHOLDER {output_language}"
        agent._language_instruction = AgentBPMN._language_instruction
        agent._select_canonical_pattern = AgentBPMN._select_canonical_pattern

        hub = KnowledgeHub.new()
        hub.transcript_clean = (
            "Firmamos um contrato de prestação de serviços com um fornecedor "
            "externo. A consultoria contratada envia relatórios mensais até o "
            "encerramento do contrato, quando fazemos a avaliação final do fornecedor."
        )

        system, user = AgentBPMN.build_prompt(agent, hub, "Auto-detect")
        assert "[GABARITO CANÔNICO: bpmn_pattern_collab_callactivity_phases]" in user
        assert "pool_contratante" in user
