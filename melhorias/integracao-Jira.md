A integração do **RawToInsights AI** com o **Jira** é vista como um dos pilares fundamentais para transformar conversas em execução direta, posicionando a solução como uma ferramenta indispensável para equipes de TI e Product Owners.

Abaixo, detalho como essa integração deve ocorrer, o que pode ser explorado e os ganhos diretos para os clientes:

### 1. Como deve se dar a integração
A integração está planejada para evoluir de um modelo de exportação para uma conexão nativa via API:

*   **Agile Bridge (Ponte Ágil):** Através de uma camada técnica denominada "Agile Bridge", o sistema converte as decisões tomadas em reuniões de planejamento ou refinamento diretamente em itens de backlog.
*   **Fluxo de "Um Clique":** A visão de futuro para a ferramenta é permitir que, ao finalizar o processamento de uma reunião, o usuário aperte um botão (seja no app Streamlit ou em um Add-on do Google Docs) para enviar os requisitos e histórias de usuário diretamente para o projeto correspondente no Jira.
*   **Plugin Nativo:** Existe o potencial de lançar o "RawToInsights AI for Jira" como um aplicativo dentro do próprio Marketplace da Atlassian, permitindo que a inteligência de negócio seja consumida onde o trabalho já acontece.

### 2. O que pode ser explorado
A integração permite que o Jira deixe de ser apenas um repositório manual de tarefas e passe a ser alimentado por inteligência de negócio estruturada:

*   **Geração Automática de User Stories:** O sistema extrai decisões e as formata como Histórias de Usuário prontas para o backlog.
*   **Critérios de Aceitação Automatizados:** Além da história, a IA gera automaticamente os critérios de aceitação com base no que foi discutido, garantindo que o "Definition of Done" esteja alinhado com as expectativas dos stakeholders.
*   **Rastreabilidade (Traceability):** Cada tarefa no Jira pode conter um link de volta para a transcrição original ou para o **Relatório Executivo em HTML**, permitindo que os desenvolvedores consultem o contexto exato de quem disse o quê e por que aquela decisão foi tomada.
*   **Mapeamento de Processos (BPMN) para Tasks:** O fluxo desenhado em BPMN 2.0 pode ser quebrado em tarefas menores, organizando o fluxo de trabalho da equipe de desenvolvimento de forma lógica.

### 3. Benefícios para os Clientes
A conexão com o Jira resolve problemas críticos de gestão de produtos e projetos:

*   **Redução Drástica do Retrabalho:** Elimina o "telefone sem fio" entre a reunião de requisitos e a escrita do código, pois as regras de negócio são traduzidas sem as ambiguidades inerentes ao processo manual.
*   **Economia de Tempo para POs e PMs:** Estima-se que um Product Owner gaste cerca de 15 horas por semana transcrevendo decisões; a automação pode reduzir o tempo de *grooming* (refinamento) em até **50%**.
*   **Aumento da Qualidade do Backlog:** Ao gerar critérios de aceitação consistentes e completos, evita-se que histórias entrem em desenvolvimento com lacunas de informação, o que reduz o ciclo de retrabalho técnico.
*   **Memória Corporativa Ativa:** O Jira passa a refletir a "memória" da empresa armazenada no **Knowledge Hub**, garantindo que nenhuma decisão de reunião seja esquecida ou contradita por uma tarefa criada posteriormente.

============================================================

Para implementar tecnicamente a integração com o Jira no **RawToInsights AI**, utilizamos a camada denominada **Agile Bridge (Ponte Ágil)**. Esta camada atua como um tradutor entre a inteligência extraída dos agentes e a API REST do Jira, permitindo que decisões capturadas em tempo real tornem-se itens executáveis no backlog.

Abaixo, detalho o fluxo técnico de como essa integração deve ser construída dentro da arquitetura atual:

### 1. Extração via Agente de Requisitos
O processo começa no **AgentRequirements**, que já faz parte do pipeline multi-agente do sistema.
*   **Identificação:** O agente analisa a transcrição e identifica requisitos funcionais, atribuindo-os ao falante (rastreabilidade) e classificando-os (ex: IEEE 830).
*   **Formatação:** O agente gera um objeto JSON no **KnowledgeHub** contendo o título da história, a descrição no formato *"Como [persona], eu quero [ação] para [valor]"* e os **Critérios de Aceitação**.

### 2. O Funcionamento da Agile Bridge
A "Agile Bridge" é o módulo de serviço (ex: `services/jira_connector.py`) que consome os dados validados do KnowledgeHub. Tecnicamente, a integração segue estes passos:

*   **Autenticação:** Utiliza-se a autenticação via **API Token** do Jira (Basic Auth codificada em Base64) ou OAuth 2.0 para ambientes corporativos.
*   **Mapeamento de Campos (Payload):** O JSON do KnowledgeHub é mapeado para o endpoint do Jira (`POST /rest/api/3/issue`):
    *   `summary`: Título do requisito.
    *   `description`: História do usuário + link para o **Relatório Executivo HTML** (para manter o contexto original).
    *   `issuetype`: Definido como "Story" ou "Task".
    *   `customfield_XXXX`: Critérios de aceitação (geralmente um campo de texto rico ou checklist no Jira).

### 3. Automação de "Um Clique" no Streamlit
Na interface do usuário, a integração é exposta na aba **"📦 Exportar"**.
*   **Seleção de Projeto:** O sistema lista os projetos do Jira via API (`GET /rest/api/3/project`).
*   **Envio em Lote:** O usuário seleciona quais requisitos validados deseja enviar. A Agile Bridge executa chamadas assíncronas (via `ThreadPoolExecutor`) para criar as issues sem travar a interface.

### 4. Benefícios Técnicos e de Negócio
*   **Redução de Grooming:** Para empresas com múltiplos squads, essa automação reduz o tempo de refinamento (grooming) em até **50%**, pois o PO não precisa transcrever manualmente o que foi decidido.
*   **Eliminação da Ambiguidade:** Como os critérios de aceitação são gerados diretamente das regras de negócio extraídas (SBVR), o risco de má interpretação pelo time de TI é drasticamente reduzido.
*   **Rastreabilidade Total:** Cada ticket no Jira herda o `meeting_id` e a citação direta do stakeholder que solicitou a funcionalidade, garantindo transparência.

Esta integração pode ser expandida para se tornar um **plugin nativo (Add-on)** no Marketplace da Atlassian, o que abriria um mercado potencial de milhões de dólares em assinaturas por assento.

============================================================

Como solicitado, aqui está um exemplo técnico de como implementar a **Agile Bridge** em Python para integrar o **RawToInsights AI** ao **Jira**.

Esta implementação utiliza os dados estruturados pelo **AgentRequirements** e persistidos no **Knowledge Hub**. O foco é transformar os requisitos identificados (classificados pelo padrão IEEE 830) em *User Stories* completas com critérios de aceitação.

### Exemplo de Implementação (Python 3.13)

O código abaixo demonstra como mapear os objetos do sistema para o payload da API v3 do Jira:

```python
import requests
import json

def push_to_jira(requirement, project_key, jira_url, auth_token):
    """
    Envia um requisito do Knowledge Hub para o Backlog do Jira.
    Mapeia os campos do AgentRequirements para o formato Jira.
    """
    
    # Endpoint para criação de issues na API v3
    url = f"{jira_url}/rest/api/3/issue"
    
    # Mapeamento do requisito para o User Story (Formato ADF - Atlassian Document Format)
    # Requisito extraído: "Como [persona], eu quero [ação] para [valor]"
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": f"Req: {requirement['title']}",
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": f"História: {requirement['user_story']}\n\n"}
                        ]
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "Critérios de Aceitação:\n", "marks": [{"type": "strong"}]}
                        ]
                    },
                    {
                        "type": "bulletList",
                        "content": [
                            {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": c}]}]}
                            for c in requirement['acceptance_criteria']
                        ]
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": f"\nOrigem: Relatório Executivo {requirement['report_url']}"}
                        ]
                    }
                ]
            },
            "issuetype": {"name": "Story"},
            "priority": {"name": requirement['priority']} # Mapeado da prioridade IEEE 830
        }
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Basic {auth_token}"
    }

    response = requests.post(url, data=json.dumps(payload), headers=headers)
    return response.status_code, response.json()
```

### Detalhes Técnicos da Integração

*   **Rastreabilidade (Traceability):** O payload inclui automaticamente um link para o **Relatório Executivo HTML**, permitindo que o desenvolvedor no Jira acesse o contexto original da reunião e os comentários dos stakeholders.
*   **Processamento Paralelo:** Para garantir que o envio de múltiplos requisitos não congele a interface do Streamlit, a Agile Bridge utiliza o `ThreadPoolExecutor` para realizar as chamadas de API de forma assíncrona.
*   **Defesa Programática:** Antes do envio, o sistema utiliza funções de validação (como a lógica do `AgentValidator`) para garantir que os requisitos não possuam ambiguidades que gerariam retrabalho técnico no Jira.

### Benefícios Diretos para o Fluxo Ágil
A automação desse processo permite reduzir o tempo de *grooming* (refinamento) em até **50%**, uma vez que as histórias e critérios de aceitação já chegam pré-estruturados para o time de desenvolvimento. Além disso, elimina-se o erro humano na tradução de regras de negócio complexas (SBVR) para tarefas técnicas.

===========================================================================

Guia Técnico: Implementação da Camada Agile Bridge via Claude Code

Este documento estabelece as diretrizes de engenharia para a implementação da Agile Bridge (Camada 2) dentro do ecossistema RawToInsights AI. Como Lead Architect, exijo que esta implementação siga rigorosamente os padrões de escalabilidade e desacoplamento definidos na transição para a infraestrutura Google Cloud.

1. Visão Geral e Preparação do Ambiente

A Agile Bridge é o componente crítico da Camada 2 projetado para converter a inteligência bruta extraída pelo AgentRequirements em artefatos executáveis de backlog. Diferente da versão legada (Process2Diagram), o RawToInsights AI opera sob uma estratégia de agnosticismo de provedor e persistência gerenciada no Google Cloud.

Pré-requisitos Técnicos

A implementação deve ser realizada via Claude Code CLI, respeitando o seguinte stack:

* Linguagem: Python 3.13 (obrigatório o uso de Type Hinting rigoroso).
* IDE: PyCharm com o plugin Google Cloud Code.
* Engine de IA: Gemini 1.5 Flash (via Google AI Studio) para processamento de alto volume.
* Infraestrutura: Google Cloud Run (Hosting) e Firestore (Persistência em modo Nativo).

Checklist de Discovery Técnica

* [ ] Google Cloud Project ID: Configurado no ambiente local.
* [ ] Firestore Collection Configuration: Coleções para backlog_artefacts e traceability_links definidas.
* [ ] KnowledgeHub Schema: Validação da migração de campos para suporte a metadados do Jira.
* [ ] Acesso ao Terminal: Claude Code CLI autenticado e com permissão de leitura no diretório /core e /agents.

2. Configuração de Autenticação: Jira API v3

A integração com o ecossistema Atlassian deve ser abstraída para permitir flexibilidade futura (ClickUp/Trello). Utilize o padrão de API Tokens (v3) em vez de autenticação básica.

Gerenciamento de Segredos

As credenciais não devem ser persistidas no código. Em desenvolvimento, utilize .env; em produção, as variáveis devem ser injetadas via Google Secret Manager e acessadas através de um wrapper agnóstico.

# Exemplo de Wrapper Agnóstico para Integração de Gestão de Projetos
from abc import ABC, abstractmethod

class ProjectManagementBridge(ABC):
    @abstractmethod
    def create_issue(self, summary: str, description: str, issue_type: str):
        pass

class JiraBridge(ProjectManagementBridge):
    def __init__(self, base_url: str, email: str, token: str):
        self.auth = (email, token)
        self.base_url = base_url

    def validate_connection(self) -> bool:
        # Implementar tratamento de erro 401/403 com log específico
        pass


3. Provisionamento de Contexto para Claude Code

Para garantir que o Claude Code atue com precisão cirúrgica na refatoração, forneça o prompt mestre abaixo no terminal do PyCharm. Este prompt instrui a IA a respeitar a arquitetura de isolamento de condições de corrida (race-condition isolation).

Prompt Mestre de Contextualização

"Claude, atue como Sênior Solutions Architect. Analise os arquivos core/knowledge_hub.py e agents/agent_requirements.py. Note que o KnowledgeHub é uma pure Python dataclass que exige o uso do método hub.migrate() para qualquer evolução de schema. Implemente a Agile Bridge como uma subclasse de BaseAgent, herdando obrigatoriamente os métodos _call_llm() e _parse_json(). Durante a transformação, utilize a lógica de _enforce_rules() para resolver atores identificados pelo NLP (como 'Usuário' ou 'Sistema') em unidades organizacionais reais mapeadas no hub.nlp.actors. Garanta que a escrita no Firestore respeite o isolamento de seções do Hub para evitar sobreposição de dados entre agentes concorrentes."

4. Lógica de Transformação: Requisitos (IEEE 830) para User Stories

A transformação deve converter requisitos classificados em histórias de usuário no formato: "Como [Papel], eu quero [Ação], para que [Valor/Benefício]".

Mapeamento de Requisitos e Estimativa de Complexidade

O sistema deve inferir automaticamente os Story Points com base na taxonomia do requisito:

Tipo IEEE 830	Prioridade Jira	Estimativa (Points)	Justificativa Técnica
Confiabilidade	Crítica / High	8 - 13	Exige protocolos de segurança/compliance.
Funcional	High / Medium	3 - 5	Impacto direto no fluxo BPMN.
Performance	Medium	5 - 8	Envolve otimização de infra e latência.
Usabilidade	Medium / Low	2 - 3	Ajustes de interface e experiência.
Suporte	Low	1 - 2	Manutenibilidade e extensibilidade.

Geração de Critérios de Aceitação (Gherkin + SBVR)

Os critérios de aceitação (Dado/Quando/Então) devem ser enriquecidos utilizando o vocabulário de negócios presente em hub.sbvr.rules. Isso garante que as histórias de usuário sejam "bridge-aware" e terminologicamente consistentes com as regras de negócio extraídas na Camada 1.

5. Implementação da Rastreabilidade e Relatório Executivo

A rastreabilidade é a "Single Source of Truth" para auditorias. Cada User Story gerada no Jira deve conter links bidirecionais.

1. URL de Origem: Insira um hyperlink na descrição da issue do Jira apontando para a seção de "Especificação de Requisitos" do Relatório Executivo HTML hospedado no Google Cloud Storage.
2. ID de Auditoria: O metadado meeting_id deve ser incluído em um campo customizado ou tag no Jira, permitindo que qualquer desenvolvedor rastreie a decisão original na ata da reunião.
3. Referência Cruzada: Utilize o AgentSynthesizer para injetar o ID da Issue gerada (ex: JIRA-123) de volta no relatório executivo, fechando o ciclo de visibilidade.

6. Tratamento de Erros, Logs e Monitoramento

A resiliência da ponte deve ser garantida via LangGraph Adaptive Retry. Se a sincronização com a API do Jira falhar ou retornar dados malformados, o sistema deve re-executar a lógica de formatação até 3 vezes antes de emitir um alerta de falha crítica.

Diretrizes de Registro (Logs)

Proíbo o uso de strings não estruturadas em logs de produção. Utilize o padrão de dicionário para posterior ingestão no Google Cloud Logging:

* Sucesso/Falha: Status da transação de criação de issue.
* Token Consumption: Registro via hub.meta.total_tokens_used para monitoramento de custos.
* Artefact IDs: Lista de IDs de tickets criados e persistidos no Firestore para auditoria posterior.

7. Estratégia de Deploy e Validação (Sandbox)

Mantenha o Streamlit como Sandbox para experimentação rápida de novas "Lentes de Análise". Uma vez validada a lógica de conversão, promova o código para o Google Cloud Run.

Comando Final de Validação (Claude Code CLI)

Após a implementação, execute a validação de integridade para garantir que a transição de dados entre o KnowledgeHub e o Firestore está operando sob latência aceitável:

claude run "Validar integridade da Agile Bridge: Verifique se os objetos UserStory gerados a partir do KnowledgeHub estão sendo persistidos corretamente no Firestore com o meeting_id correto e se os Gherkin Acceptance Criteria estão utilizando os termos definidos em hub.sbvr.vocabulary."


Esta arquitetura garante que o RawToInsights AI não seja apenas uma ferramenta de transcrição, mas uma Memória Ativa que reduz o grooming técnico em até 50%, transformando o caos de reuniões em ativos digitais auditáveis.



