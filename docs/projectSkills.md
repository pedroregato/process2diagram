🎯 Nova Arquitetura - Multi-projeto:
1. Estrutura de tabelas no Supabase:
-- Tabela project_skills (1:1 com projects)
CREATE TABLE project_skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID UNIQUE REFERENCES projects(id) ON DELETE CASCADE,

    -- Metadados da skill
    skill_name TEXT NOT NULL DEFAULT 'Project Skill',
    version TEXT DEFAULT '1.0',
    priority INTEGER DEFAULT 1,  -- 1=baixa, 2=média, 3=alta
    is_active BOOLEAN DEFAULT TRUE,

    -- Conteúdo estruturado (JSONB para flexibilidade)
    content JSONB NOT NULL DEFAULT '{}',

    -- Controle de versões
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'system',
    updated_by TEXT DEFAULT 'system'
);

-- Tabela de histórico de versões das skills
CREATE TABLE project_skill_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_skill_id UUID REFERENCES project_skills(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,

    -- Snapshot do conteúdo
    version_number TEXT NOT NULL,
    content JSONB NOT NULL,
    change_summary TEXT,

    created_at TIMESTAMPTz DEFAULT NOW(),
    created_by TEXT
);

-- Índices para performance
CREATE INDEX idx_project_skills_project_id ON project_skills(project_id);
CREATE INDEX idx_project_skills_active ON project_skills(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_project_skill_versions_project ON project_skill_versions(project_id);

2. Esquema JSON para o conteúdo da skill:
{
  "metadata": {
    "template": "software_project",
    "language": "pt-BR",
    "last_reviewed": "2026-04-10"
  },
  "sections": {
    "overview": {
      "title": "Visão Geral",
      "content": "Texto em markdown...",
      "order": 1
    },
    "objectives": {
      "title": "Objetivos",
      "content": "1. Objetivo 1\n2. Objetivo 2",
      "order": 2
    },
    "stakeholders": {
      "title": "Stakeholders",
      "content": "- Stakeholder 1: Papel",
      "order": 3
    },
    "glossary": {
      "title": "Glossário",
      "content": "**DCI:** Documento de Controle Interno",
      "order": 10
    }
  },
  "custom_fields": {
    "budget": "R$ 500.000,00",
    "timeline": "18 meses",
    "risk_level": "médio"
  }
}

3. Sistema de gerenciamento de skills:
# skill_manager.py
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import markdown
from supabase import create_client

class ProjectSkillManager:
    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase = create_client(supabase_url, supabase_key)
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, Dict]:
        """Carrega templates pré-definidos"""
        return {
            "software_project": {
                "name": "Projeto de Software",
                "sections": {
                    "overview": {"title": "Visão Geral", "order": 1},
                    "objectives": {"title": "Objetivos", "order": 2},
                    "scope": {"title": "Escopo", "order": 3},
                    "stakeholders": {"title": "Stakeholders", "order": 4},
                    "architecture": {"title": "Arquitetura", "order": 5},
                    "constraints": {"title": "Restrições", "order": 6},
                    "glossary": {"title": "Glossário", "order": 10}
                }
            },
            "business_process": {
                "name": "Processo de Negócio",
                "sections": {
                    "process_flow": {"title": "Fluxo do Processo", "order": 1},
                    "participants": {"title": "Participantes", "order": 2},
                    "documents": {"title": "Documentos", "order": 3},
                    "business_rules": {"title": "Regras de Negócio", "order": 4}
                }
            },
            "audit_project": {
                "name": "Projeto de Auditoria",
                "sections": {
                    "audit_objective": {"title": "Objetivo da Auditoria", "order": 1},
                    "scope": {"title": "Escopo da Auditoria", "order": 2},
                    "team": {"title": "Equipe de Auditoria", "order": 3},
                    "methodology": {"title": "Metodologia", "order": 4},
                    "timeline": {"title": "Cronograma", "order": 5},
                    "deliverables": {"title": "Entregáveis", "order": 6}
                }
            }
        }

    def get_or_create_skill(self, project_id: str, template: str = "software_project") -> Dict:
        """Obtém ou cria uma skill para o projeto"""

        # Verificar se já existe
        result = self.supabase.table('project_skills')\
            .select('*')\
            .eq('project_id', project_id)\
            .execute()

        if result.data:
            return result.data[0]

        # Criar nova skill
        template_config = self.templates.get(template, self.templates["software_project"])

        skill_data = {
            "project_id": project_id,
            "skill_name": template_config["name"],
            "version": "1.0",
            "is_active": True,
            "content": {
                "metadata": {
                    "template": template,
                    "created_at": datetime.now().isoformat(),
                    "language": "pt-BR"
                },
                "sections": self._initialize_sections(template_config["sections"])
            }
        }

        result = self.supabase.table('project_skills')\
            .insert(skill_data)\
            .execute()

        # Criar versão inicial
        self._create_version(result.data[0]["id"], project_id, "1.0", "Criação inicial")

        return result.data[0]

    def _initialize_sections(self, sections_config: Dict) -> Dict:
        """Inicializa seções com conteúdo padrão"""
        sections = {}
        for section_id, config in sections_config.items():
            sections[section_id] = {
                "title": config["title"],
                "content": f"# {config['title']}\n\n*Adicione conteúdo aqui...*",
                "order": config.get("order", 99)
            }
        return sections

    def update_skill_section(self, project_id: str, section_id: str, content: str) -> Dict:
        """Atualiza uma seção específica da skill"""

        # Buscar skill atual
        skill = self.get_or_create_skill(project_id)
        current_content = skill["content"]

        # Atualizar seção
        if "sections" in current_content and section_id in current_content["sections"]:
            current_content["sections"][section_id]["content"] = content
            current_content["metadata"]["updated_at"] = datetime.now().isoformat()

            # Incrementar versão (ex: 1.0 -> 1.1)
            version_parts = skill["version"].split(".")
            minor_version = int(version_parts[1]) + 1 if len(version_parts) > 1 else 1
            new_version = f"{version_parts[0]}.{minor_version}"

            # Atualizar no banco
            result = self.supabase.table('project_skills')\
                .update({
                    "content": current_content,
                    "version": new_version,
                    "updated_at": datetime.now().isoformat(),
                    "updated_by": "user"  # Será substituído pelo usuário real
                })\
                .eq("project_id", project_id)\
                .execute()

            # Criar nova versão
            self._create_version(
                skill["id"], 
                project_id, 
                new_version, 
                f"Atualização da seção '{section_id}'"
            )

            return result.data[0]

        raise ValueError(f"Seção '{section_id}' não encontrada na skill")

    def _create_version(self, skill_id: str, project_id: str, version: str, summary: str):
        """Cria um snapshot da versão"""
        # Buscar conteúdo atual
        skill = self.supabase.table('project_skills')\
            .select('content')\
            .eq('id', skill_id)\
            .single()\
            .execute()

        version_data = {
            "project_skill_id": skill_id,
            "project_id": project_id,
            "version_number": version,
            "content": skill.data["content"],
            "change_summary": summary,
            "created_by": "system"
        }

        self.supabase.table('project_skill_versions')\
            .insert(version_data)\
            .execute()

    def get_skill_as_markdown(self, project_id: str) -> str:
        """Converte a skill para markdown formatado"""
        skill = self.get_or_create_skill(project_id)
        content = skill["content"]

        markdown_parts = []

        # Cabeçalho
        markdown_parts.append(f"# {skill['skill_name']}")
        markdown_parts.append(f"*Versão: {skill['version']}*")
        markdown_parts.append("")

        # Ordenar seções por ordem
        sections = content.get("sections", {})
        sorted_sections = sorted(
            sections.items(), 
            key=lambda x: x[1].get("order", 99)
        )

        for section_id, section_data in sorted_sections:
            markdown_parts.append(f"## {section_data['title']}")
            markdown_parts.append(section_data['content'])
            markdown_parts.append("")

        # Campos customizados
        custom_fields = content.get("custom_fields", {})
        if custom_fields:
            markdown_parts.append("## Informações Adicionais")
            for key, value in custom_fields.items():
                markdown_parts.append(f"- **{key.replace('_', ' ').title()}:** {value}")
            markdown_parts.append("")

        # Rodapé
        metadata = content.get("metadata", {})
        if "created_at" in metadata:
            markdown_parts.append(f"---\n*Criado em: {metadata['created_at']}*")
        if "updated_at" in metadata:
            markdown_parts.append(f"*Última atualização: {metadata['updated_at']}*")

        return "\n".join(markdown_parts)

    def get_skill_for_assistant(self, project_id: str) -> str:
        """Gera o prompt de contexto para o assistente"""
        markdown_content = self.get_skill_as_markdown(project_id)

        # Adicionar instruções específicas para o assistente
        assistant_context = f"""
## CONTEXTO DO PROJETO PARA O ASSISTENTE

Abaixo estão as informações do projeto que você deve usar como referência:

{markdown_content}

### INSTRUÇÕES PARA O ASSISTENTE:
1. Use estas informações como contexto principal para responder perguntas sobre este projeto
2. Consulte o glossário para termos técnicos específicos
3. Considere as restrições e objetivos listados
4. Quando mencionar stakeholders, use os nomes e papéis definidos
5. Mantenha consistência com a terminologia do projeto
"""

        return assistant_context

    def search_in_skill(self, project_id: str, query: str) -> List[Dict]:
        """Busca texto dentro da skill do projeto"""
        skill = self.get_or_create_skill(project_id)
        content = skill["content"]

        results = []

        # Buscar em todas as seções
        sections = content.get("sections", {})
        for section_id, section_data in sections.items():
            content_text = section_data["content"].lower()
            if query.lower() in content_text:
                results.append({
                    "section": section_data["title"],
                    "section_id": section_id,
                    "content_preview": self._extract_preview(section_data["content"], query),
                    "relevance": self._calculate_relevance(section_data["content"], query)
                })

        # Ordenar por relevância
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results

    def _extract_preview(self, content: str, query: str, context_chars: int = 100) -> str:
        """Extrai um trecho do conteúdo com o contexto da busca"""
        query_lower = query.lower()
        content_lower = content.lower()

        pos = content_lower.find(query_lower)
        if pos == -1:
            return content[:context_chars] + "..."

        start = max(0, pos - context_chars)
        end = min(len(content), pos + len(query) + context_chars)

        preview = content[start:end]
        if start > 0:
            preview = "..." + preview
        if end < len(content):
            preview = preview + "..."

        return preview

    def _calculate_relevance(self, content: str, query: str) -> float:
        """Calcula a relevância da busca"""
        content_lower = content.lower()
        query_lower = query.lower()

        # Frequência do termo
        frequency = content_lower.count(query_lower)

        # Posição no texto (primeiras ocorrências são mais relevantes)
        first_pos = content_lower.find(query_lower)
        position_score = 1.0 if first_pos < 100 else 0.5

        return frequency * position_score

    def list_project_skills(self) -> List[Dict]:
        """Lista todas as skills de projetos"""
        result = self.supabase.table('project_skills')\
            .select('''
                id, project_id, skill_name, version, is_active, updated_at,
                projects!inner(name, sigla)
            ''')\
            .execute()

        return result.data

    def get_skill_history(self, project_id: str) -> List[Dict]:
        """Obtém o histórico de versões da skill"""
        result = self.supabase.table('project_skill_versions')\
            .select('*')\
            .eq('project_id', project_id)\
            .order('created_at', desc=True)\
            .execute()

        return result.data

4. Interface Streamlit para múltiplos projetos:
# pages/ProjectSkills.py
import streamlit as st
from skill_manager import ProjectSkillManager
import json

st.set_page_config(page_title="Skills de Projetos", layout="wide")

# Inicializar manager
manager = ProjectSkillManager(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

# Sidebar - Seleção de projeto
st.sidebar.title("📁 Projetos")

# Listar projetos disponíveis
projects_result = manager.supabase.table('projects')\
    .select('id, name, sigla')\
    .order('name')\
    .execute()

projects = {f"{p['sigla']} - {p['name']}": p['id'] for p in projects_result.data}

if not projects:
    st.sidebar.warning("Nenhum projeto cadastrado")
    st.stop()

selected_project_name = st.sidebar.selectbox(
    "Selecione o projeto",
    list(projects.keys())
)

project_id = projects[selected_project_name]
project_info = next(p for p in projects_result.data if p['id'] == project_id)

# Carregar skill do projeto
skill = manager.get_or_create_skill(project_id)

# Layout principal
st.title(f"📚 Skill do Projeto: {project_info['name']}")
st.caption(f"ID: {project_id} | Versão: {skill['version']}")

# Abas principais
tab1, tab2, tab3, tab4 = st.tabs(["📝 Editar", "👁️ Visualizar", "🔍 Buscar", "📊 Histórico"])

with tab1:
    st.header("Editar Skill")

    # Selecionar template
    template_options = {k: v["name"] for k, v in manager.templates.items()}
    current_template = skill["content"]["metadata"].get("template", "software_project")

    new_template = st.selectbox(
        "Template da Skill",
        options=list(template_options.keys()),
        format_func=lambda x: template_options[x],
        index=list(template_options.keys()).index(current_template) if current_template in template_options else 0
    )

    if new_template != current_template:
        if st.button("Aplicar Novo Template"):
            # Recriar skill com novo template
            manager.supabase.table('project_skills')\
                .delete()\
                .eq('project_id', project_id)\
                .execute()

            skill = manager.get_or_create_skill(project_id, new_template)
            st.success(f"Template alterado para '{template_options[new_template]}'")
            st.rerun()

    # Editor de seções
    sections = skill["content"].get("sections", {})

    if sections:
        selected_section = st.selectbox(
            "Seção para editar",
            options=list(sections.keys()),
            format_func=lambda x: sections[x]["title"]
        )

        section_content = sections[selected_section]["content"]

        new_content = st.text_area(
            f"Conteúdo da seção '{sections[selected_section]['title']}'",
            value=section_content,
            height=300,
            help="Use markdown para formatação"
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Salvar Seção"):
                if new_content != section_content:
                    updated_skill = manager.update_skill_section(
                        project_id, 
                        selected_section, 
                        new_content
                    )
                    st.success(f"Seção '{sections[selected_section]['title']}' atualizada!")
                    st.rerun()
                else:
                    st.info("Nenhuma alteração detectada")

        with col2:
            if st.button("📋 Pré-visualizar Markdown"):
                st.markdown(new_content)

    # Campos customizados
    st.subheader("Campos Customizados")

    custom_fields = skill["content"].get("custom_fields", {})

    col1, col2 = st.columns(2)
    with col1:
        new_field_key = st.text_input("Nome do campo")
    with col2:
        new_field_value = st.text_input("Valor do campo")

    if st.button("➕ Adicionar Campo") and new_field_key:
        # Atualizar campos customizados
        content = skill["content"]
        if "custom_fields" not in content:
            content["custom_fields"] = {}

        content["custom_fields"][new_field_key] = new_field_value

        manager.supabase.table('project_skills')\
            .update({"content": content})\
            .eq('project_id', project_id)\
            .execute()

        st.success(f"Campo '{new_field_key}' adicionado!")
        st.rerun()

    # Mostrar campos existentes
    if custom_fields:
        st.write("**Campos existentes:**")
        for key, value in custom_fields.items():
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.text_input(f"Chave", value=key, key=f"key_{key}", disabled=True)
            with col2:
                st.text_input(f"Valor", value=value, key=f"value_{key}", disabled=True)
            with col3:
                if st.button("🗑️", key=f"delete_{key}"):
                    del content["custom_fields"][key]
                    manager.supabase.table('project_skills')\
                        .update({"content": content})\
                        .eq('project_id', project_id)\
                        .execute()
                    st.rerun()

with tab2:
    st.header("Visualização Completa")

    # Opções de visualização
    view_mode = st.radio(
        "Modo de visualização",
        ["Markdown", "HTML", "JSON", "Para o Assistente"],
        horizontal=True
    )

    if view_mode == "Markdown":
        markdown_content = manager.get_skill_as_markdown(project_id)
        st.text_area("Conteúdo Markdown", markdown_content, height=500)

        # Botão para copiar
        if st.button("📋 Copiar Markdown"):
            st.session_state['clipboard'] = markdown_content
            st.success("Markdown copiado para a área de transferência!")

    elif view_mode == "HTML":
        markdown_content = manager.get_skill_as_markdown(project_id)
        html_content = markdown.markdown(markdown_content)
        st.components.v1.html(f"""
            <div style="padding: 20px; background: white; border-radius: 10px;">
                {html_content}
            </div>
        """, height=600, scrolling=True)

    elif view_mode == "JSON":
        st.json(skill["content"])

    elif view_mode == "Para o Assistente":
        assistant_context = manager.get_skill_for_assistant(project_id)
        st.text_area("Contexto para o Assistente", assistant_context, height=500)

        st.info("""
        Este é o contexto que será injetado no prompt do assistente quando 
        ele estiver respondendo perguntas sobre este projeto específico.
        """)

with tab3:
    st.header("Busca na Skill")

    search_query = st.text_input("Digite o termo para buscar")

    if search_query:
        results = manager.search_in_skill(project_id, search_query)

        if results:
            st.write(f"**{len(results)} resultado(s) encontrado(s):**")

            for i, result in enumerate(results[:10], 1):  # Limitar a 10 resultados
                with st.expander(f"{i}. {result['section']} (relevância: {result['relevance']:.2f})"):
                    st.write(f"**Seção:** {result['section']}")
                    st.write(f"**Trecho:** {result['content_preview']}")

                    # Botão para ir direto para a seção
                    if st.button(f"✏️ Editar esta seção", key=f"edit_{i}"):
                        st.session_state['selected_section'] = result['section_id']
                        st.switch_page("pages/ProjectSkills.py#editar")
        else:
            st.info("Nenhum resultado encontrado para a busca.")

with tab4:
    st.header("Histórico de Versões")

    history = manager.get_skill_history(project_id)

    if history:
        for version in history:
            with st.expander(f"Versão {version['version_number']} - {version['created_at'][:10]}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**Resumo da mudança:** {version['change_summary']}")
                    st.write(f"**Criado por:** {version['created_by']}")
                    st.write(f"**Data:** {version['created_at']}")

                with col2:
                    if st.button("👁️ Visualizar", key=f"view_{version['id']}"):
                        st.json(version['content'])

                    if st.button("🔄 Restaurar", key=f"restore_{version['id']}"):
                        # Restaurar esta versão
                        manager.supabase.table('project_skills')\
                            .update({
                                "content": version['content'],
                                "version": version['version_number'],
                                "updated_at": datetime.now().isoformat()
                            })\
                            .eq('project_id', project_id)\
                            .execute()

                        st.success(f"Skill restaurada para versão {version['version_number']}!")
                        st.rerun()
    else:
        st.info("Nenhum histórico de versões disponível.")

# Barra lateral inferior - Ações globais
st.sidebar.markdown("---")
st.sidebar.subheader("Ações Globais")

if st.sidebar.button("🔄 Recarregar Skill"):
    st.rerun()

if st.sidebar.button("📥 Exportar como JSON"):
    st.sidebar.download_button(
        label="Baixar JSON",
        data=json.dumps(skill, indent=2, ensure_ascii=False),
        file_name=f"skill_{project_info['sigla']}_{skill['version']}.json",
        mime="application/json"
    )

if st.sidebar.button("📊 Ver Todas as Skills"):
    all_skills = manager.list_project_skills()

    if all_skills:
        st.sidebar.write("**Skills por projeto:**")
        for skill_info in all_skills:
            project_ref = skill_info.get('projects', {})
            st.sidebar.write(f"• {project_ref.get('sigla', 'N/A')}: v{skill_info['version']}")
    else:
        st.sidebar.info("Nenhuma skill criada ainda")

5. Integração com o Assistente principal:
# Atualize o Assistente.py
import streamlit as st
from skill_manager import ProjectSkillManager

# Inicializar manager
skill_manager = ProjectSkillManager(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

# Na sidebar do Assistente
with st.sidebar.expander("🔧 Contexto do Projeto"):
    # Listar projetos
    projects_result = skill_manager.supabase.table('projects')\
        .select('id, name, sigla')\
        .order('name')\
        .execute()

    if projects_result.data:
        project_options = {f"{p['sigla']} - {p['name']}": p['id'] for p in projects_result.data}

        selected_project = st.selectbox(
            "Projeto para contexto",
            options=list(project_options.keys()),
            index=0
        )

        project_id = project_options[selected_project]

        # Carregar skill
        skill_context = skill_manager.get_skill_for_assistant(project_id)

        # Armazenar no session state
        st.session_state['project_context'] = skill_context
        st.session_state['current_project_id'] = project_id

        st.success(f"✅ Contexto do projeto '{selected_project}' carregado")

        # Link para editar skill
        if st.button("✏️ Editar Skill deste Projeto"):
            st.switch_page("pages/ProjectSkills.py")
    else:
        st.warning("Nenhum projeto cadastrado")

# No sistema do assistente, injetar o contexto
def get_assistant_system_prompt():
    base_prompt = """Você é um assistente especializado em análise de reuniões e projetos."""

    if 'project_context' in st.session_state:
        return base_prompt + "\n\n" + st.session_state['project_context']

    return base_prompt

6. Script de migração para projetos existentes:
# migrate_existing_projects.py
from skill_manager import ProjectSkillManager
from supabase import create_client

def migrate_all_projects():
    """Cria skills para todos os projetos existentes"""
    supabase = create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

    manager = ProjectSkillManager(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

    # Buscar todos os projetos
    projects = supabase.table('projects')\
        .select('id, name, sigla')\
        .execute()

    created_count = 0
    for project in projects.data:
        try:
            # Determinar template baseado no nome
            template = "audit_project" if "auditoria" in project['name'].lower() else "software_project"

            # Criar skill
            skill = manager.get_or_create_skill(project['id'], template)

            # Preencher com dados das reuniões (se houver)
            _enrich_skill_from_meetings(manager, project['id'])

            created_count += 1
            print(f"✅ Skill criada para: {project['sigla']} - {project['name']}")

        except Exception as e:
            print(f"❌ Erro em {project['sigla']}: {e}")

    print(f"\n🎉 Migração concluída: {created_count}/{len(projects.data)} skills criadas")

def _enrich_skill_from_meetings(manager, project_id):
    """Enriquece a skill com dados das reuniões"""
    supabase = manager.supabase

    # Buscar reuniões do projeto
    meetings = supabase.table('meetings')\
        .select('title, meeting_date, participants')\
        .eq('project_id', project_id)\
        .order('meeting_date')\
        .execute()

    if meetings.data:
        # Extrair stakeholders únicos
        stakeholders = set()
        for meeting in meetings.data:
            if meeting.get('participants'):
                # Parse participants (ajuste conforme seu formato)
                participants = meeting['participants'].split(',')
                stakeholders.update([p.strip() for p in participants])

        # Atualizar seção de stakeholders
        if stakeholders:
            stakeholders_content = "\n".join([f"- **{s}:** Participante das reuniões" for s in stakeholders])
            manager.update_skill_section(
                project_id,
                "stakeholders",
                f"# Stakeholders\n\n{stakeholders_content}"
            )

🚀 Plano de implementação:
Fase 1 (Banco + Core):

Criar tabelas project_skills e project_skill_versions
Implementar ProjectSkillManager básico
Script de migração para projetos existentes
Fase 2 (Interface):

Página ProjectSkills.py com abas básicas
Integração com sidebar do Assistente
Visualização em markdown/HTML/JSON
Fase 3 (Funcionalidades avançadas):

Busca full-text nas skills
Histórico de versões com restore
Templates customizáveis
Import/export de skills
Fase 4 (Integração inteligente):

Auto-preenchimento com dados das reuniões
Sugestões baseadas em outros projetos similares
Análise de completude da skill
📈 Benefícios desta arquitetura:
Escalável: Suporta múltiplos projetos simultaneamente
Relacional: 1:1 com a tabela projects do Supabase
Versionada: Histórico completo de mudanças
Estruturada: JSON schema permite validação e queries complexas
Integrada: Contexto injetado automaticamente no assistente
Customizável: Templates diferentes para tipos de projeto
Colaborativa: Múltiplos usuários podem editar com histórico
Esta solução permite que cada projeto no seu sistema tenha sua própria "memória institucional" que evolui junto com o projeto, enquanto mantém uma arquitetura limpa e escalável!
