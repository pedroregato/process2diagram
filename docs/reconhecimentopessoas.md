Para implementar reconhecimento de pessoas, áreas e unidades organizacionais nas reuniões do SDEA, você precisa de uma solução de NER (Named Entity Recognition) customizada. Aqui está o que precisa construir:

🎯 Arquitetura da Solução:
1. Bibliotecas Python necessárias:
# NER básico
pip install spacy
python -m spacy download pt_core_news_lg  # Modelo em português

# NER customizado (opcional)
pip install transformers
pip install torch

# Processamento de texto
pip install nltk
pip install unidecode

# Para treinamento (se necessário)
pip install scikit-learn
pip install joblib

2. Estrutura de dados no Supabase:
-- Tabela para entidades reconhecidas
CREATE TABLE meeting_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id UUID REFERENCES meetings(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    entity_text TEXT NOT NULL,
    entity_type TEXT NOT NULL,  -- 'PESSOA', 'AREA', 'UNIDADE', 'CARGO'
    normalized_name TEXT,  -- Nome padronizado
    confidence_score FLOAT DEFAULT 1.0,
    context TEXT,  -- Trecho onde a entidade aparece
    start_position INTEGER,
    end_position INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabela de dicionário de entidades conhecidas
CREATE TABLE entity_dictionary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    entity_text TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    category TEXT,  -- 'INTERNO', 'EXTERNO', 'CLIENTE', 'FORNECEDOR'
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, entity_text, entity_type)
);

3. Módulo Python para NER customizado:
# ner_extractor.py
import spacy
import re
from typing import List, Dict, Tuple
import unidecode
from collections import defaultdict

class SDEAEntityRecognizer:
    def __init__(self):
        # Carregar modelo spaCy em português
        self.nlp = spacy.load("pt_core_news_lg")

        # Padrões regex para entidades específicas
        self.patterns = {
            'PESSOA': [
                r'\b(Sr\.|Sra\.|Dr\.|Dra\.|Eng\.)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',
                r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b',  # Nome e sobrenome
            ],
            'CARGO': [
                r'\b(Coordenador|Gerente|Analista|Auditor|Diretor|Supervisor|Consultor)\b',
                r'\b(Chefe|Líder|Especialista|Técnico|Assistente)\b',
            ],
            'AREA': [
                r'\b(TI|RH|Financeiro|Comercial|Jurídico|Operações|Auditoria)\b',
                r'\b(Departamento|Setor|Divisão|Coordenação|Gerência)\s+de\s+[A-Za-z]+\b',
            ],
            'UNIDADE': [
                r'\b(Diretoria|Superintendência|Secretaria|Presidência)\b',
                r'\b(Unidade|Filial|Regional|Nacional)\s+[A-Za-z]+\b',
            ]
        }

        # Dicionário de entidades conhecidas (pode ser carregado do banco)
        self.known_entities = {
            'PESSOA': ['João Silva', 'Maria Santos', 'Carlos Oliveira'],
            'AREA': ['TI', 'Auditoria Interna', 'Financeiro'],
            'UNIDADE': ['Diretoria Executiva', 'Superintendência de Operações'],
            'CARGO': ['Coordenador de TI', 'Gerente de Projetos']
        }

    def extract_entities(self, text: str) -> List[Dict]:
        """Extrai entidades do texto"""
        entities = []

        # 1. Usar spaCy para NER básico
        doc = self.nlp(text)
        for ent in doc.ents:
            if ent.label_ in ['PER', 'ORG', 'MISC']:
                entity_type = self.map_spacy_label(ent.label_)
                entities.append({
                    'text': ent.text,
                    'type': entity_type,
                    'start': ent.start_char,
                    'end': ent.end_char,
                    'source': 'spacy',
                    'confidence': 0.8
                })

        # 2. Aplicar regex patterns
        for entity_type, patterns in self.patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    entities.append({
                        'text': match.group(),
                        'type': entity_type,
                        'start': match.start(),
                        'end': match.end(),
                        'source': 'regex',
                        'confidence': 0.7
                    })

        # 3. Buscar entidades conhecidas
        for entity_type, known_list in self.known_entities.items():
            for known_entity in known_list:
                if known_entity.lower() in text.lower():
                    # Encontrar todas as ocorrências
                    start = 0
                    while True:
                        pos = text.lower().find(known_entity.lower(), start)
                        if pos == -1:
                            break
                        entities.append({
                            'text': text[pos:pos+len(known_entity)],
                            'type': entity_type,
                            'start': pos,
                            'end': pos + len(known_entity),
                            'source': 'dictionary',
                            'confidence': 0.9
                        })
                        start = pos + 1

        # 4. Remover duplicatas e sobreposições
        entities = self.deduplicate_entities(entities)

        return entities

    def map_spacy_label(self, label: str) -> str:
        """Mapeia labels do spaCy para nossos tipos"""
        mapping = {
            'PER': 'PESSOA',
            'ORG': 'UNIDADE',
            'MISC': 'AREA',
            'LOC': 'UNIDADE'
        }
        return mapping.get(label, 'OUTRO')

    def deduplicate_entities(self, entities: List[Dict]) -> List[Dict]:
        """Remove entidades duplicadas e sobrepostas"""
        # Ordenar por posição de início
        entities.sort(key=lambda x: x['start'])

        deduplicated = []
        last_end = -1

        for entity in entities:
            # Se não sobrepõe com a anterior, adiciona
            if entity['start'] >= last_end:
                deduplicated.append(entity)
                last_end = entity['end']
            # Se sobrepõe, mantém a com maior confiança
            elif entity['confidence'] > deduplicated[-1]['confidence']:
                deduplicated[-1] = entity
                last_end = entity['end']

        return deduplicated

    def normalize_entity(self, entity_text: str, entity_type: str) -> str:
        """Normaliza o nome da entidade"""
        # Remover acentos e converter para maiúsculas
        normalized = unidecode.unidecode(entity_text).upper()

        # Padronizações específicas
        if entity_type == 'CARGO':
            normalized = normalized.replace('COORDENADOR DE', 'COORDENADOR')
            normalized = normalized.replace('GERENTE DE', 'GERENTE')

        return normalized.strip()

4. Pipeline de processamento:
# entity_pipeline.py
from supabase import create_client
import json
from ner_extractor import SDEAEntityRecognizer

class EntityPipeline:
    def __init__(self, supabase_url, supabase_key):
        self.supabase = create_client(supabase_url, supabase_key)
        self.recognizer = SDEAEntityRecognizer()

    def process_meeting(self, meeting_number: int):
        """Processa uma reunião para extrair entidades"""

        # 1. Buscar transcrição da reunião
        meeting_data = self.supabase.table('meetings')\
            .select('id, project_id, transcript_clean')\
            .eq('meeting_number', meeting_number)\
            .single()\
            .execute()

        if not meeting_data.data:
            return {"error": "Reunião não encontrada"}

        meeting_id = meeting_data.data['id']
        project_id = meeting_data.data['project_id']
        transcript = meeting_data.data['transcript_clean']

        # 2. Extrair entidades
        entities = self.recognizer.extract_entities(transcript)

        # 3. Salvar no banco
        saved_count = 0
        for entity in entities:
            # Normalizar nome
            normalized = self.recognizer.normalize_entity(
                entity['text'], 
                entity['type']
            )

            # Extrair contexto (50 caracteres antes e depois)
            start_context = max(0, entity['start'] - 50)
            end_context = min(len(transcript), entity['end'] + 50)
            context = transcript[start_context:end_context]

            # Inserir no banco
            result = self.supabase.table('meeting_entities').insert({
                'meeting_id': meeting_id,
                'project_id': project_id,
                'entity_text': entity['text'],
                'entity_type': entity['type'],
                'normalized_name': normalized,
                'confidence_score': entity['confidence'],
                'context': context,
                'start_position': entity['start'],
                'end_position': entity['end']
            }).execute()

            saved_count += 1

        return {
            "meeting_id": meeting_id,
            "entities_found": len(entities),
            "entities_saved": saved_count,
            "by_type": self._count_by_type(entities)
        }

    def _count_by_type(self, entities):
        """Conta entidades por tipo"""
        counts = defaultdict(int)
        for entity in entities:
            counts[entity['type']] += 1
        return dict(counts)

    def get_entity_statistics(self, project_id: str = None):
        """Obtém estatísticas das entidades"""
        query = self.supabase.table('meeting_entities')

        if project_id:
            query = query.eq('project_id', project_id)

        # Contar por tipo
        result = query.select('entity_type').execute()

        counts = defaultdict(int)
        for row in result.data:
            counts[row['entity_type']] += 1

        return dict(counts)

5. Interface no Streamlit:
# pages/EntityRecognition.py
import streamlit as st
import pandas as pd
from entity_pipeline import EntityPipeline

st.title("🔍 Reconhecimento de Entidades - SDEA")

# Inicializar pipeline
pipeline = EntityPipeline(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

# Seção 1: Processar reuniões
st.header("Processar Reuniões")
meeting_number = st.number_input("Número da reunião", min_value=1, value=1)

if st.button("Extrair Entidades"):
    with st.spinner("Processando..."):
        result = pipeline.process_meeting(meeting_number)

        if "error" in result:
            st.error(result["error"])
        else:
            st.success(f"✅ Extraídas {result['entities_found']} entidades")

            # Mostrar estatísticas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Pessoas", result['by_type'].get('PESSOA', 0))
            with col2:
                st.metric("Áreas", result['by_type'].get('AREA', 0))
            with col3:
                st.metric("Unidades", result['by_type'].get('UNIDADE', 0))
            with col4:
                st.metric("Cargos", result['by_type'].get('CARGO', 0))

# Seção 2: Visualizar entidades
st.header("Entidades Reconhecidas")

# Filtros
entity_type = st.selectbox(
    "Tipo de entidade",
    ["TODOS", "PESSOA", "AREA", "UNIDADE", "CARGO"]
)

# Buscar entidades
if st.button("Buscar Entidades"):
    query = pipeline.supabase.table('meeting_entities')\
        .select('*')\
        .order('created_at', desc=True)\
        .limit(100)

    if entity_type != "TODOS":
        query = query.eq('entity_type', entity_type)

    result = query.execute()

    if result.data:
        df = pd.DataFrame(result.data)
        st.dataframe(df[['entity_text', 'entity_type', 'normalized_name', 'confidence_score']])

        # Gráfico de distribuição
        if not df.empty:
            chart_data = df['entity_type'].value_counts()
            st.bar_chart(chart_data)
    else:
        st.info("Nenhuma entidade encontrada")

# Seção 3: Dicionário de entidades
st.header("📚 Dicionário de Entidades")

# Adicionar nova entidade ao dicionário
with st.expander("➕ Adicionar Entidade Manualmente"):
    col1, col2 = st.columns(2)
    with col1:
        new_entity = st.text_input("Nome da entidade")
        entity_type = st.selectbox("Tipo", ["PESSOA", "AREA", "UNIDADE", "CARGO"])
    with col2:
        normalized = st.text_input("Nome normalizado")
        category = st.selectbox("Categoria", ["INTERNO", "EXTERNO", "CLIENTE", "FORNECEDOR"])

    if st.button("Salvar no Dicionário"):
        # Salvar no banco
        result = pipeline.supabase.table('entity_dictionary').insert({
            'project_id': st.session_state.get('project_id'),
            'entity_text': new_entity,
            'normalized_name': normalized or new_entity.upper(),
            'entity_type': entity_type,
            'category': category
        }).execute()

        st.success(f"Entidade '{new_entity}' salva no dicionário!")

6. Script de inicialização do dicionário:
# init_entity_dictionary.py
def initialize_sdea_dictionary(pipeline):
    """Inicializa o dicionário com entidades comuns do SDEA"""

    common_entities = [
        # Pessoas (exemplo)
        {"text": "Coordenador de TI", "type": "CARGO", "normalized": "COORDENADOR TI"},
        {"text": "Gerente de Projetos", "type": "CARGO", "normalized": "GERENTE PROJETOS"},

        # Áreas
        {"text": "Auditoria Interna", "type": "AREA", "normalized": "AUDITORIA INTERNA"},
        {"text": "TI", "type": "AREA", "normalized": "TI"},
        {"text": "Financeiro", "type": "AREA", "normalized": "FINANCEIRO"},

        # Unidades
        {"text": "Diretoria Executiva", "type": "UNIDADE", "normalized": "DIRETORIA EXECUTIVA"},
        {"text": "Superintendência", "type": "UNIDADE", "normalized": "SUPERINTENDENCIA"},
    ]

    for entity in common_entities:
        pipeline.supabase.table('entity_dictionary').insert({
            'project_id': 'seu-project-id',
            'entity_text': entity['text'],
            'normalized_name': entity['normalized'],
            'entity_type': entity['type'],
            'category': 'INTERNO'
        }).execute()

    print("Dicionário inicializado com sucesso!")

7. Integração com o pipeline existente:
No seu pipeline principal, adicione:

# No AgentRequirements ou AgentTranscriptQuality
from entity_pipeline import EntityPipeline

class EnhancedAgent:
    def __init__(self):
        self.entity_pipeline = EntityPipeline()

    def process_transcript(self, transcript, meeting_id):
        # Processamento normal...

        # Extrair entidades
        entity_result = self.entity_pipeline.process_meeting(meeting_id)

        # Adicionar entidades aos metadados
        metadata['entities'] = entity_result

        return metadata

🚀 Plano de implementação:
Fase 1 (Básica):

Instalar spaCy e configurar modelo português
Criar tabelas no Supabase
Implementar NER com regex patterns simples
Interface básica no Streamlit
Fase 2 (Aprimorada):

Treinar modelo customizado com exemplos do SDEA
Implementar aprendizado incremental
Adicionar validação manual das entidades
Integrar com busca semântica
Fase 3 (Avançada):

Relacionamento entre entidades
Hierarquia organizacional
Análise de rede de colaboração
Dashboard de stakeholders
📊 Benefícios para o SDEA:
Identificação automática de participantes e áreas envolvidas
Rastreamento de quem mencionou cada requisito/regra
Análise de influência nas decisões
Mapa de stakeholders do projeto
Busca por pessoa/área nas transcrições
Esta solução permitirá que você comece com uma abordagem simples (regex + spaCy) e evolua para um sistema mais sofisticado conforme coleta mais dados das reuniões do SDEA.
