Perfeito! Aqui está a lista completa das tools disponíveis para o Claude Code criar a funcionalidade de gerar atas faltantes:

TOOLS DISPONÍVEIS NO ASSISTENTE:
1. Ferramentas de Consulta (Somente Leitura)
get_meeting_list() - Lista todas as reuniões com status
get_meeting_participants(meeting_number) - Participantes de uma reunião
get_meeting_decisions(meeting_number) - Decisões formais
get_meeting_action_items(meeting_number) - Itens de ação
get_meeting_summary(meeting_number) - Ata completa
search_transcript(query, meeting_number) - Busca em transcrições
get_requirements(keyword, req_type, status) - Requisitos do projeto
list_bpmn_processes() - Processos BPMN
get_sbvr_terms(keyword) - Termos SBVR
get_sbvr_rules(keyword) - Regras SBVR
calculate_meeting_roi(meeting_number, cost_per_hour) - ROI das reuniões
get_recurring_topics(threshold) - Tópicos recorrentes
get_meeting_metadata(meeting_number) - Metadados detalhados
preview_meeting_deletion(meeting_number) - Pré-visualiza exclusão
preview_text_correction(find_text, replace_text, scope, meeting_number) - Pré-visualiza correção
2. Ferramentas de Escrita/Modificação
add_sbvr_term(term, definition, category) - Adiciona termo SBVR
update_sbvr_term(term, definition, category, origin) - Atualiza termo SBVR
add_sbvr_rule(statement, rule_type, source) - Adiciona regra SBVR
apply_text_correction(find_text, replace_text, scope, meeting_number) - Aplica correção de texto
delete_meeting(meeting_number, confirmed) - Exclui reunião
reprocess_meeting_requirements(meeting_number, output_language) - Reprocessa requisitos
LACUNA IDENTIFICADA:
NÃO EXISTE: generate_missing_minutes() ou similar para:

Detectar reuniões sem atas (minutes_md IS NULL)
Mas com transcrições (transcript_clean IS NOT NULL)
Gerar atas usando AgentMinutes
Salvar no campo minutes_md
ESPECIFICAÇÕES PARA A NOVA FUNCIONALIDADE:
Nome Sugerido:
generate_missing_minutes(project_id=None, meeting_numbers=None, force_regenerate=False)

Parâmetros:
project_id (opcional): Filtrar por projeto específico
meeting_numbers (opcional): Lista de números de reunião específicos
force_regenerate (opcional): Regenerar mesmo se já existir ata
Comportamento:
Consulta reuniões onde:

minutes_md IS NULL OR minutes_md = ''
transcript_clean IS NOT NULL
transcript_clean != ''
(opcional) Filtro por project_id
Para cada reunião:

Chama AgentMinutes com transcript_clean
Salva resultado em minutes_md
Registra log de sucesso/erro
Retorna:

Total de reuniões processadas
Sucessos vs. falhas
Lista de reuniões atualizadas
Integração com Sistema Existente:
Usar mesma lógica do AgentMinutes da página principal
Mesmo formato de saída (Markdown estruturado)
Mesmo tratamento de idioma (Auto-detect)
Log no batch_log para auditoria
CASO DE USO ATUAL (SDEA):
8 reuniões com transcript_clean preenchido
0 reuniões com minutes_md preenchido
Necessidade urgente de completar as atas
IMPLEMENTAÇÃO SUGERIDA:
O Claude Code pode criar:

Nova tool no assistente
Nova página no Streamlit (ex: "Minutes Generator")
Integração no Batch Runner como opção adicional
Botão no ReqTracker para "Completar Atas Faltantes"
DADOS DE EXEMPLO PARA TESTE:
# Reuniões do SDEA que precisam de atas:
meetings_needing_minutes = [1, 2, 3, 4, 5, 6, 7, 8]
# Todas têm transcript_clean, nenhuma tem minutes_md

PRIORIDADE:
ALTA - Esta funcionalidade resolveria um problema crítico de completude dos dados e permitiria análises mais precisas (ROI, participantes, decisões).

Pronto para passar essas especificações para o Claude Code?
