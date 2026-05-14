🎯 Estratégia para melhorar a precisão
Aqui está o plano completo, do mais simples ao mais estrutural:

🔹 Nível 1 — Correção no Skill (imediata, sem código)
Adicione esta instrução ao final do skill do Assistente:

REGRAS DE TRUNCAMENTO E PRECISÃO:

A ferramenta get_requirements() tem limite de ~82k caracteres. Quando o retorno incluir a frase "resultado truncado" ou "caracteres omitidos", você DEVE informar ao usuário que a lista está incompleta.
NUNCA afirme um total de requisitos baseado apenas no que viu em uma resposta truncada.
Para obter o total exato, use get_requirements() com filtros específicos (keyword, req_type, status) em vez de buscar tudo de uma vez.
Para perguntas sobre um requisito específico (ex: "quem sugeriu o REQ-229?"), busque diretamente por ele usando keyword="REQ-229" ou pelo título.
Se a busca direta por keyword não encontrar o requisito, informe ao usuário que o requisito não foi encontrado na base consultada e sugira verificar no ReqTracker.
Impacto: Zero desenvolvimento. Resolve o problema de comunicação, mas não o problema técnico.

🔹 Nível 2 — Melhoria na ferramenta get_requirements() (médio prazo)
Adicione um parâmetro count_only na ferramenta:

get_requirements(keyword=None, req_type=None, status=None, count_only=False)

Quando count_only=True, a ferramenta executa um SELECT COUNT(*) no banco em vez de trazer todos os registros. O Assistente pode chamar:

get_requirements(count_only=True) → retorna {"total": 233} — sem truncamento
Depois, para perguntas específicas, chama com filtros: get_requirements(keyword="REQ-229")
Impacto: Resolve o problema de raiz para contagens. Requer alteração no código da ferramenta.

