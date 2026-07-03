# pages/SegurancaDeDados.py
# ─────────────────────────────────────────────────────────────────────────────
# Segurança de Dados — arquitetura de proteção de dados sensíveis do P2D
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from ui.auth_gate import apply_auth_gate

apply_auth_gate()

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
:root {
  --navy:   #0B1F3A;
  --navy2:  #112848;
  --gold:   #C9973A;
  --gold2:  #E8B84B;
  --white:  #F0F4FA;
  --muted:  #A8B8D8;
  --bg:     #060E1C;
  --text:   #CDD8EC;
  --green:  #10B981;
  --red:    #E74C3C;
  --blue:   #3B82F6;
  --teal:   #14B8A6;
  --purple: #8B5CF6;
  --amber:  #F59E0B;
}

.stApp { background: var(--bg) !important; }

/* ── Page header ── */
.sec-header {
  background: linear-gradient(135deg, #071428 0%, #0B1E3D 55%, #0D2240 100%);
  border-bottom: 3px solid #10B981;
  border-radius: 14px;
  padding: 2rem 2.4rem 1.6rem;
  margin-bottom: 2rem;
  box-shadow: 0 4px 32px rgba(0,0,0,.45);
}
.sec-header .sh-tag {
  font-size: .70rem; font-weight: 700; letter-spacing: .15em;
  text-transform: uppercase; color: #10B981;
  background: rgba(16,185,129,.12); border: 1px solid rgba(16,185,129,.3);
  border-radius: 20px; padding: 2px 10px; display: inline-block;
  margin-bottom: .7rem;
}
.sec-header .sh-title { font-size: 1.65rem; font-weight: 800; color: #F0F4FA; }
.sec-header .sh-sub   { font-size: .83rem; color: #7A8EA8; margin-top: .4rem; max-width: 720px; }

/* ── Section label ── */
.sec-label {
  display: flex; align-items: center; gap: .6rem;
  font-size: .68rem; font-weight: 700; color: #6A7E98;
  letter-spacing: .14em; text-transform: uppercase;
  margin: 2rem 0 .9rem;
}
.sec-label::after {
  content: ""; flex: 1; height: 1px;
  background: linear-gradient(90deg, #1e3a55 0%, transparent 100%);
}

/* ── Layer card ── */
.layer-card {
  background: #0A1828;
  border: 1px solid #1C3252;
  border-left: 4px solid var(--layer-color, #10B981);
  border-radius: 12px;
  padding: 1.1rem 1.3rem;
  margin-bottom: .85rem;
  box-shadow: 0 2px 12px rgba(0,0,0,.22);
}
.layer-card .lc-head {
  display: flex; align-items: center; gap: .65rem;
  margin-bottom: .55rem;
}
.layer-card .lc-badge {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 28px; height: 28px; border-radius: 8px;
  background: var(--layer-color, #10B981); color: #fff;
  font-size: .70rem; font-weight: 800; flex-shrink: 0; padding: 0 6px;
}
.layer-card .lc-title { font-size: .98rem; font-weight: 700; color: #F0F4FA; }
.layer-card .lc-file  {
  font-size: .68rem; color: var(--layer-color, #10B981);
  font-family: monospace; margin-left: auto;
  background: rgba(255,255,255,.05); border-radius: 6px;
  padding: 2px 7px;
}
.layer-card .lc-body  { font-size: .82rem; color: #9AAABB; line-height: 1.60; }

/* ── Feature row ── */
.feat-row {
  display: flex; align-items: flex-start; gap: .85rem;
  background: #0D1E35; border: 1px solid #1A3050;
  border-radius: 10px; padding: .8rem 1rem;
  margin-bottom: .5rem;
}
.feat-row .fr-icon { font-size: 1.15rem; margin-top: 1px; flex-shrink: 0; }
.feat-row .fr-text { font-size: .81rem; color: #9AAABB; line-height: 1.55; }
.feat-row .fr-text strong { color: #D8E4F0; }

/* ── Data table ── */
.data-table {
  width: 100%; border-collapse: collapse;
  font-size: .79rem; color: #9AAABB;
  margin-bottom: 1rem;
}
.data-table thead tr {
  background: #0D1E35;
  border-bottom: 1px solid #1E3A55;
}
.data-table thead th {
  padding: .55rem .85rem; text-align: left;
  font-size: .67rem; font-weight: 700; letter-spacing: .10em;
  text-transform: uppercase; color: #6A7E98;
}
.data-table tbody tr {
  border-bottom: 1px solid #111E30;
}
.data-table tbody tr:hover { background: rgba(255,255,255,.025); }
.data-table td { padding: .55rem .85rem; vertical-align: top; }
.data-table .badge {
  display: inline-block; border-radius: 10px; padding: 1px 8px;
  font-size: .67rem; font-weight: 700; letter-spacing: .06em;
}
.badge-replace  { background: rgba(16,185,129,.15);  color: #10B981;  border: 1px solid rgba(16,185,129,.3); }
.badge-classify { background: rgba(59,130,246,.15);  color: #60A5FA;  border: 1px solid rgba(59,130,246,.3); }
.badge-encrypt  { background: rgba(139,92,246,.15);  color: #A78BFA;  border: 1px solid rgba(139,92,246,.3); }
.badge-session  { background: rgba(245,158,11,.15);  color: #FCD34D;  border: 1px solid rgba(245,158,11,.3); }
.badge-transit  { background: rgba(20,184,166,.15);  color: #2DD4BF;  border: 1px solid rgba(20,184,166,.3); }
.badge-none     { background: rgba(107,114,128,.12); color: #9CA3AF;  border: 1px solid rgba(107,114,128,.3); }

/* ── Highlight box ── */
.highlight-box {
  background: #071824;
  border: 1px solid rgba(16,185,129,.25);
  border-left: 4px solid #10B981;
  border-radius: 10px; padding: 1rem 1.2rem;
  margin: 1rem 0;
  font-size: .82rem; color: #9AAABB; line-height: 1.60;
}
.highlight-box strong { color: #D8E4F0; }
.highlight-box .hb-title {
  font-size: .72rem; font-weight: 700; letter-spacing: .10em;
  text-transform: uppercase; color: #10B981; margin-bottom: .5rem;
}

/* ── Warning box ── */
.warn-box {
  background: #1A1200;
  border: 1px solid rgba(245,158,11,.25);
  border-left: 4px solid #F59E0B;
  border-radius: 10px; padding: .9rem 1.1rem;
  margin: .8rem 0;
  font-size: .80rem; color: #B0A070; line-height: 1.55;
}
.warn-box strong { color: #FCD34D; }

/* ── LGPD badge grid ── */
.lgpd-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: .7rem; margin: .8rem 0;
}
.lgpd-card {
  background: #0A1828; border: 1px solid #1C3252;
  border-radius: 10px; padding: .85rem 1rem;
}
.lgpd-card .lgc-art  { font-size: .65rem; font-weight: 700; letter-spacing: .10em; text-transform: uppercase; color: #10B981; margin-bottom: .3rem; }
.lgpd-card .lgc-name { font-size: .88rem; font-weight: 700; color: #F0F4FA; margin-bottom: .3rem; }
.lgpd-card .lgc-desc { font-size: .75rem; color: #7A8EA8; line-height: 1.45; }

/* ── Overview pills row ── */
.overview-row {
  display: flex; flex-wrap: wrap; gap: .55rem; margin: 1rem 0 1.5rem;
}
.overview-pill {
  display: flex; align-items: center; gap: .4rem;
  background: #0D1E35; border: 1px solid #1A3050;
  border-radius: 20px; padding: .3rem .85rem;
  font-size: .78rem; color: #D8E4F0;
}
.overview-pill .op-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--dot-color, #10B981); flex-shrink: 0;
}
</style>
""", unsafe_allow_html=True)

# ── Cabeçalho ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="sec-header">
  <div class="sh-tag">Segurança &amp; Privacidade</div>
  <div class="sh-title">🔒 Segurança de Dados Sensíveis</div>
  <div class="sh-sub">
    Arquitetura multicamada de proteção de dados do Process2Diagram — do texto bruto da
    transcrição até o armazenamento em banco de dados. Projetada para atender aos
    requisitos da LGPD (Lei 13.709/2018) e para pilotos em ambientes institucionais.
  </div>
</div>
""", unsafe_allow_html=True)

# ── Visão Geral ───────────────────────────────────────────────────────────────
st.markdown('<div class="sec-label">Visão Geral da Arquitetura</div>', unsafe_allow_html=True)

st.markdown("""
<div class="overview-row">
  <div class="overview-pill"><div class="op-dot" style="--dot-color:#10B981"></div>6 camadas de proteção</div>
  <div class="overview-pill"><div class="op-dot" style="--dot-color:#3B82F6"></div>Nomes e PII estruturado pseudonimizados para LLMs</div>
  <div class="overview-pill"><div class="op-dot" style="--dot-color:#8B5CF6"></div>API Keys apenas em sessão</div>
  <div class="overview-pill"><div class="op-dot" style="--dot-color:#F59E0B"></div>Trilha de auditoria LGPD</div>
  <div class="overview-pill"><div class="op-dot" style="--dot-color:#14B8A6"></div>Conformidade Art. 7° LGPD</div>
  <div class="overview-pill"><div class="op-dot" style="--dot-color:#E74C3C"></div>Sem treinamento do LLM com dados do usuário</div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="highlight-box">
  <div class="hb-title">Princípio central</div>
  Todos os dados que identificam pessoas são <strong>pseudonimizados antes de qualquer chamada ao LLM</strong>
  — o modelo nunca recebe nem processa os valores reais. A restauração ocorre localmente,
  dentro do servidor Streamlit, antes de salvar no banco.<br><br>
  <strong>Tier 1 — PII estruturado</strong> (CPF, CNPJ, e-mail, telefone, valores monetários):
  substituídos por tokens <code>@LABEL_NNN</code> a cada chamada.<br>
  <strong>Tier 2 — Nomes de pessoas</strong> (PC82): detectados uma vez via spaCy NER e
  pseudonimizados como <code>[PESSOA:PG]</code> em todas as chamadas da sessão;
  restaurados nos artefatos antes de salvar no banco (nomes reais ficam no banco — RAG preservado).
</div>
""", unsafe_allow_html=True)

# ── As 6 Camadas ─────────────────────────────────────────────────────────────
st.markdown('<div class="sec-label">As 6 Camadas de Proteção</div>', unsafe_allow_html=True)

st.markdown("""
<div class="layer-card" style="--layer-color: #10B981;">
  <div class="lc-head">
    <div class="lc-badge">C1</div>
    <div class="lc-title">Sanitização de PII — Substituição Reversível por Token</div>
    <div class="lc-file">modules/pii_sanitizer.py</div>
  </div>
  <div class="lc-body">
    Dois tiers de pseudonimização aplicados antes de cada chamada ao LLM.<br><br>
    <strong>Tier 1 — PII estruturado</strong> (stateless, por chamada): regex detecta e substitui
    CPF, CNPJ, e-mail, telefone e valores monetários por tokens opacos
    (ex.: <code style="color:#10B981">@CPF_001</code>, <code style="color:#10B981">@EMAIL_002</code>).
    O mapeamento fica em memória; ao retornar, os tokens são revertidos antes de qualquer
    outra operação.<br><br>
    <strong>Tier 2 — Nomes de pessoas</strong> (PC82, session-wide): na abertura do pipeline,
    <code>detect_names()</code> usa spaCy NER para detectar nomes completos e cria
    <code>hub.meta.name_map</code>
    (ex.: <code style="color:#10B981">[PESSOA:PG]</code> → "Pedro Gentil").
    Todas as chamadas LLM substituem nomes por tokens e os restauram antes de salvar.
    O mapa existe <strong>apenas em memória</strong> — nunca persiste no banco.
    Nomes reais ficam nos artefatos armazenados para que RAG e busca semântica funcionem.
  </div>
</div>

<div class="layer-card" style="--layer-color: #3B82F6;">
  <div class="lc-head">
    <div class="lc-badge">C2</div>
    <div class="lc-title">Conformidade LGPD — Detecção, Consentimento e Auditoria</div>
    <div class="lc-file">modules/compliance/</div>
  </div>
  <div class="lc-body">
    Após o processamento de cada reunião, o sistema executa três operações de conformidade:<br><br>
    <strong>1. Detecção (detector.py)</strong> — Classifica os tipos de PII presentes na transcrição
    usando regex (estruturado) e NER via spaCy <code>pt_core_news_lg</code> (nomes de pessoas).
    Calcula o nível de risco (baixo / médio / alto).<br><br>
    <strong>2. Consentimento (consent.py)</strong> — Exibe ao operador um painel com o resumo de PII
    detectado, a base legal selecionável (Legítimo Interesse, Consentimento, Contrato, Obrigação Legal)
    e o prazo de retenção configurável (30–365 dias). O registro é salvo na tabela
    <code>compliance_consent</code>.<br><br>
    <strong>3. Trilha de Auditoria (audit.py)</strong> — Todo evento relevante (execução do pipeline,
    consentimento registrado, acesso a dados, exclusão) é gravado de forma assíncrona em
    <code>compliance_audit</code>. O log de auditoria é retido por 365 dias — mais tempo que
    os próprios dados da reunião.
  </div>
</div>

<div class="layer-card" style="--layer-color: #8B5CF6;">
  <div class="lc-head">
    <div class="lc-badge">C3</div>
    <div class="lc-title">Autenticação e Controle de Acesso por Perfil</div>
    <div class="lc-file">modules/auth.py</div>
  </div>
  <div class="lc-body">
    O acesso à plataforma é protegido por autenticação com <strong>hash SHA-256</strong>
    das senhas. As credenciais nunca são armazenadas em texto claro — apenas os
    hashes ficam no código. Após o login, a identidade do usuário é mantida apenas
    na <code>st.session_state</code> da sessão Streamlit (memória volátil do servidor).<br><br>
    <strong>Hierarquia de perfis:</strong>
    <code>master</code> › <code>admin</code> › <code>user</code><br>
    Ferramentas destrutivas e administrativas (exclusão de dados, acesso ao banco, operações
    de calendário, limpeza de cache) são restritas a <code>admin</code> e <code>master</code>
    por <code>is_admin()</code> — verificação executada a cada chamada de ferramenta.
  </div>
</div>

<div class="layer-card" style="--layer-color: #F59E0B;">
  <div class="lc-head">
    <div class="lc-badge">C4</div>
    <div class="lc-title">API Keys — Exclusivamente em Sessão, Nunca Persistidas</div>
    <div class="lc-file">modules/session_security.py</div>
  </div>
  <div class="lc-body">
    As chaves de API dos provedores LLM (DeepSeek, Claude, OpenAI, Groq, Gemini, Grok)
    são inseridas pelo usuário e mantidas <strong>somente em <code>st.session_state</code></strong>
    — memória volátil que é descartada ao fechar o navegador.<br><br>
    <strong>Garantias de proteção:</strong><br>
    • Nunca escritas em disco, banco de dados, logs ou arquivos de configuração<br>
    • Nunca incluídas em respostas, relatórios ou artefatos exportados<br>
    • Nunca transmitidas para outros usuários ou sessões<br>
    • Passadas diretamente ao SDK do provedor via HTTPS/TLS sem intermediários
  </div>
</div>

<div class="layer-card" style="--layer-color: #14B8A6;">
  <div class="lc-head">
    <div class="lc-badge">C5</div>
    <div class="lc-title">Provedores LLM — Dados em Trânsito, Sem Treinamento</div>
    <div class="lc-file">agents/base_agent.py</div>
  </div>
  <div class="lc-body">
    As transcrições são enviadas aos provedores LLM <strong>somente após a sanitização de PII (C1)</strong>.
    A comunicação é feita via HTTPS/TLS. Os provedores suportados têm políticas de
    não-retenção para fins de treinamento em suas ofertas de API:<br><br>
    • <strong>DeepSeek</strong> — sem retenção para treinamento via API (política de uso da API)<br>
    • <strong>Anthropic Claude</strong> — sem treinamento com dados de API por padrão<br>
    • <strong>OpenAI</strong> — dados de API excluídos do treinamento por padrão (configurável)<br>
    • <strong>Google Gemini, Groq, Grok (xAI)</strong> — verificar políticas de uso do provedor<br><br>
    Para ambientes com requisitos mais rígidos, recomenda-se usar <strong>DeepSeek ou Claude</strong>
    com cláusulas contratuais de proteção de dados, ou executar o modelo localmente via
    Ollama (integração planejada).
  </div>
</div>

<div class="layer-card" style="--layer-color: #E74C3C;">
  <div class="lc-head">
    <div class="lc-badge">C6</div>
    <div class="lc-title">Banco de Dados Supabase — Criptografia em Repouso e RLS</div>
    <div class="lc-file">modules/supabase_client.py</div>
  </div>
  <div class="lc-body">
    Os artefatos gerados (atas, requisitos, BPMN, SBVR) são persistidos no
    <strong>Supabase (PostgreSQL gerenciado)</strong> com:<br><br>
    • <strong>Criptografia em repouso</strong> — AES-256 no nível do provedor de infraestrutura (AWS)<br>
    • <strong>Criptografia em trânsito</strong> — TLS 1.3 entre o servidor Streamlit e o Supabase<br>
    • <strong>Row Level Security (RLS)</strong> — isolamento por <code>project_id</code>;
      cada contexto acessa apenas seus próprios dados<br>
    • <strong>Design fail-open</strong> — quando o Supabase está indisponível, o pipeline continua
      sem persistir (nunca lança exceção não tratada ao usuário)<br>
    • <strong>Conexão direta PostgreSQL</strong> (<code>psycopg2</code>) usada apenas para migrações
      DDL no ambiente local — nunca disponível no Streamlit Cloud
  </div>
</div>
""", unsafe_allow_html=True)

# ── Tabela de categorias de dados ─────────────────────────────────────────────
st.markdown('<div class="sec-label">Categorias de Dados e Seus Tratamentos</div>', unsafe_allow_html=True)

st.markdown("""
<table class="data-table">
  <thead>
    <tr>
      <th>Categoria de dado</th>
      <th>Exemplo</th>
      <th>Tratamento antes do LLM</th>
      <th>Armazenado no banco?</th>
      <th>Camada responsável</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>CPF</strong></td>
      <td style="font-family:monospace;font-size:.74rem">123.456.789-00</td>
      <td><span class="badge badge-replace">Substituído</span> por @CPF_001</td>
      <td>Não (apenas o token)</td>
      <td>C1 — pii_sanitizer</td>
    </tr>
    <tr>
      <td><strong>CNPJ</strong></td>
      <td style="font-family:monospace;font-size:.74rem">12.345.678/0001-90</td>
      <td><span class="badge badge-replace">Substituído</span> por @CNPJ_001</td>
      <td>Não (apenas o token)</td>
      <td>C1 — pii_sanitizer</td>
    </tr>
    <tr>
      <td><strong>E-mail</strong></td>
      <td style="font-family:monospace;font-size:.74rem">joao@empresa.com.br</td>
      <td><span class="badge badge-replace">Substituído</span> por @EMAIL_001</td>
      <td>Não (apenas o token)</td>
      <td>C1 — pii_sanitizer</td>
    </tr>
    <tr>
      <td><strong>Telefone</strong></td>
      <td style="font-family:monospace;font-size:.74rem">(11) 99999-9999</td>
      <td><span class="badge badge-replace">Substituído</span> por @TEL_001</td>
      <td>Não (apenas o token)</td>
      <td>C1 — pii_sanitizer</td>
    </tr>
    <tr>
      <td><strong>Valor monetário</strong></td>
      <td style="font-family:monospace;font-size:.74rem">R$ 250.000,00</td>
      <td><span class="badge badge-replace">Substituído</span> por @VALOR_001</td>
      <td>Não (apenas o token)</td>
      <td>C1 — pii_sanitizer</td>
    </tr>
    <tr>
      <td><strong>Nome de pessoa</strong></td>
      <td style="font-family:monospace;font-size:.74rem">Maria Silva</td>
      <td><span class="badge badge-classify">Pseudonimizado</span> → [PESSOA:MS] para LLM; restaurado nos artefatos</td>
      <td>Sim — com nome real (RAG preservado)</td>
      <td>C1 Tier-2 — pii_sanitizer</td>
    </tr>
    <tr>
      <td><strong>API Key LLM</strong></td>
      <td style="font-family:monospace;font-size:.74rem">sk-...</td>
      <td><span class="badge badge-session">Sessão apenas</span> — nunca sai do navegador</td>
      <td>Não</td>
      <td>C4 — session_security</td>
    </tr>
    <tr>
      <td><strong>Transcrição bruta</strong></td>
      <td>Texto da reunião</td>
      <td>Sanitizada (C1) antes de envio</td>
      <td>Sim — criptografado em repouso</td>
      <td>C1 + C6</td>
    </tr>
    <tr>
      <td><strong>Artefatos gerados</strong></td>
      <td>BPMN, ata, requisitos</td>
      <td>Gerados com texto sanitizado</td>
      <td>Sim — criptografado em repouso</td>
      <td>C5 + C6</td>
    </tr>
    <tr>
      <td><strong>Registro de consentimento</strong></td>
      <td>Base legal, TTL</td>
      <td><span class="badge badge-encrypt">Persistido</span> com metadados LGPD</td>
      <td>Sim — compliance_consent</td>
      <td>C2 — consent.py</td>
    </tr>
    <tr>
      <td><strong>Trilha de auditoria</strong></td>
      <td>pipeline_run, consent_granted</td>
      <td><span class="badge badge-encrypt">Persistido</span> assincronamente</td>
      <td>Sim — compliance_audit (365 dias)</td>
      <td>C2 — audit.py</td>
    </tr>
    <tr>
      <td><strong>Senha do usuário</strong></td>
      <td>Texto claro inserido no login</td>
      <td>Hash SHA-256 — jamais armazenada</td>
      <td>Apenas o hash (no código)</td>
      <td>C3 — auth.py</td>
    </tr>
  </tbody>
</table>
""", unsafe_allow_html=True)

# ── Pseudonimização de nomes — PC82 ────────────────────────────────────────────
st.markdown('<div class="sec-label">Pseudonimização de Nomes (PC82) — Como Funciona</div>', unsafe_allow_html=True)

st.markdown("""
<div class="highlight-box">
  <div class="hb-title">Fluxo do Tier 2</div>
  Antes do pipeline iniciar, <code>detect_names()</code> usa spaCy NER (<code>pt_core_news_lg</code>)
  para identificar nomes completos e cria o mapa de sessão <code>hub.meta.name_map</code>:<br><br>
  <code>"Pedro Gentil" → [PESSOA:PG]</code> &nbsp;·&nbsp;
  <code>"Ana Souza" → [PESSOA:AS]</code> &nbsp;·&nbsp;
  <code>"Sr. Gentil" → [PESSOA:PG]</code> (variantes título+sobrenome também substituídas)<br><br>
  Todas as chamadas LLM recebem o texto com tokens; o LLM é instruído a
  preservá-los intactos. Após retornar, os tokens são <strong>restaurados para os nomes reais
  antes de salvar</strong> — os artefatos no banco têm nomes reais, RAG e busca semântica
  funcionam normalmente.<br><br>
  <strong>O mapa existe apenas em memória</strong> — nunca persiste no Supabase. A chave de
  reversão é descartada ao encerrar a sessão.
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="warn-box">
  <strong>Por que nomes reais ainda aparecem nos artefatos finais?</strong><br>
  Os artefatos são gerados com tokens e restaurados <em>antes de salvar</em>. Os nomes reais
  ficam no banco porque são indispensáveis para as funcionalidades abaixo — o que muda
  com PC82 é que as APIs externas (DeepSeek, Claude, OpenAI, etc.) <strong>nunca mais
  recebem nomes reais no wire</strong>.
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="feat-row">
  <div class="fr-icon">🏊</div>
  <div class="fr-text"><strong>Lanes do BPMN</strong> — O LLM recebe <code>[PESSOA:PG]</code> e cria a lane
  com esse token; após restauração, a lane exibe "Pedro Gentil" com significado organizacional
  preservado, sem expor o nome ao provider LLM.</div>
</div>
<div class="feat-row">
  <div class="fr-icon">📋</div>
  <div class="fr-text"><strong>Atas de reunião</strong> — O LLM gera a ata com tokens; após restauração,
  a ata registra quem disse o quê com nomes reais. Rastreabilidade mantida;
  o provider nunca processou os nomes.</div>
</div>
<div class="feat-row">
  <div class="fr-icon">⚖️</div>
  <div class="fr-text"><strong>Debates IBIS e Requisitos</strong> — Campos <code>raised_by</code> e
  <code>cited_by</code> são gerados com tokens e restaurados antes de persistir.
  A estrutura de responsabilização fica intacta.</div>
</div>
<div class="feat-row">
  <div class="fr-icon">🔍</div>
  <div class="fr-text"><strong>RAG e busca semântica</strong> — Como os artefatos são salvos com nomes reais,
  o Assistente responde corretamente a perguntas como "o que Pedro disse?" sem
  degradação de qualidade.</div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="highlight-box">
  <div class="hb-title">Camada de conformidade LGPD complementar (C2)</div>
  O módulo <strong>detector.py (C2)</strong> classifica os nomes detectados e exibe ao operador
  o resumo de PII no painel de consentimento. O operador seleciona a base legal,
  define o prazo de retenção e o registro é salvo em <code>compliance_consent</code>.
  Para reuniões com participantes externos, o sistema alerta automaticamente para
  <strong>Consentimento explícito (Art. 7°, I)</strong> em vez de Legítimo Interesse.
</div>
""", unsafe_allow_html=True)

# ── Bases Legais LGPD ─────────────────────────────────────────────────────────
st.markdown('<div class="sec-label">Bases Legais LGPD Suportadas (Art. 7°)</div>', unsafe_allow_html=True)

st.markdown("""
<div class="lgpd-grid">
  <div class="lgpd-card">
    <div class="lgc-art">Art. 7°, IX</div>
    <div class="lgc-name">Legítimo Interesse</div>
    <div class="lgc-desc">Padrão para reuniões internas entre funcionários e pesquisadores
    da mesma organização. Aplicável quando o tratamento é necessário para as atividades
    do controlador e não viola direitos do titular.</div>
  </div>
  <div class="lgpd-card">
    <div class="lgc-art">Art. 7°, I</div>
    <div class="lgc-name">Consentimento Explícito</div>
    <div class="lgc-desc">Obrigatório quando há participantes externos (clientes, parceiros,
    convidados). O sistema alerta automaticamente quando o perfil "externo" ou "misto"
    é selecionado no painel de consentimento.</div>
  </div>
  <div class="lgpd-card">
    <div class="lgc-art">Art. 7°, V</div>
    <div class="lgc-name">Execução de Contrato</div>
    <div class="lgc-desc">Aplicável quando o tratamento é necessário para execução de
    contrato do qual o titular é parte — ex.: reuniões de projeto contratado com
    o titular como contratante ou fornecedor.</div>
  </div>
  <div class="lgpd-card">
    <div class="lgc-art">Art. 7°, II</div>
    <div class="lgc-name">Obrigação Legal</div>
    <div class="lgc-desc">Para organizações obrigadas por lei a registrar atas e processos
    (ex.: entidades públicas, reguladas). O tratamento decorre de cumprimento de
    obrigação legal ou regulatória.</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Cache semântico de LLM ────────────────────────────────────────────────────
st.markdown('<div class="sec-label">Cache Semântico — Segurança entre Sessões</div>', unsafe_allow_html=True)

st.markdown("""
<div class="feat-row">
  <div class="fr-icon">⚡</div>
  <div class="fr-text"><strong>O que é armazenado:</strong> O cache semântico (tabela <code>llm_cache</code>)
  guarda as respostas LLM <em>pré-desanitização</em> — ou seja, com os tokens
  <code>@CPF_001</code>, <code>@EMAIL_002</code> no lugar dos valores reais.
  Os valores originais <strong>nunca entram no cache</strong>.</div>
</div>
<div class="feat-row">
  <div class="fr-icon">🔑</div>
  <div class="fr-text"><strong>Como a restauração é segura entre sessões:</strong> Ao recuperar uma
  resposta cacheada, o sistema aplica o <code>token_map</code> da sessão <em>atual</em>
  — que pode ser diferente da sessão que gerou o cache. Isso garante que os dados
  do usuário A nunca são expostos ao usuário B, mesmo que ambos procesem
  a mesma transcrição.</div>
</div>
<div class="feat-row">
  <div class="fr-icon">🗑️</div>
  <div class="fr-text"><strong>TTL e limpeza:</strong> Entradas do cache expiram automaticamente.
  Administradores podem limpar o cache por agente via ferramenta
  <code>clear_llm_cache()</code> no Assistente. TTL configurável em
  <strong>Qualidade ROI-TR → Cache LLM</strong>.</div>
</div>
""", unsafe_allow_html=True)

# ── Retenção e exclusão de dados ─────────────────────────────────────────────
st.markdown('<div class="sec-label">Retenção, TTL e Exclusão de Dados</div>', unsafe_allow_html=True)

st.markdown("""
<table class="data-table">
  <thead>
    <tr>
      <th>Tabela / Dado</th>
      <th>TTL padrão</th>
      <th>Configurável?</th>
      <th>Quem pode excluir</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Transcrição + artefatos</strong> (<code>meetings</code>)</td>
      <td>Indefinido (manual)</td>
      <td>Via campo <code>expires_at</code> em <code>compliance_consent</code></td>
      <td>Admin — ferramenta <code>delete_meeting</code></td>
    </tr>
    <tr>
      <td><strong>Consentimento LGPD</strong> (<code>compliance_consent</code>)</td>
      <td>Definido no painel (30–365 dias)</td>
      <td>Sim — por reunião, no momento do registro</td>
      <td>Admin — exclusão em cascata via <code>meeting_id</code></td>
    </tr>
    <tr>
      <td><strong>Trilha de auditoria</strong> (<code>compliance_audit</code>)</td>
      <td>365 dias</td>
      <td>Via <code>pg_cron</code> ou job agendado</td>
      <td>Master admin — exclusão direta no banco</td>
    </tr>
    <tr>
      <td><strong>Cache LLM</strong> (<code>llm_cache</code>)</td>
      <td>Configurável (padrão 30 dias)</td>
      <td>Sim — TTL por entrada</td>
      <td>Admin — <code>clear_llm_cache()</code></td>
    </tr>
    <tr>
      <td><strong>Telemetria LLM</strong> (<code>llm_telemetry</code>)</td>
      <td>90 dias</td>
      <td>Via <code>delete_expired_llm_cache()</code></td>
      <td>Admin — limpeza automática</td>
    </tr>
    <tr>
      <td><strong>API Keys</strong></td>
      <td>Duração da sessão</td>
      <td>N/A — sessão volátil</td>
      <td>Automático — ao fechar o navegador</td>
    </tr>
  </tbody>
</table>
""", unsafe_allow_html=True)

# ── Rodapé ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-top: 2.5rem; padding: 1rem 1.2rem;
  border-top: 1px solid #1A3050; font-size: .72rem; color: #4A5E78; line-height: 1.6;">
  <strong style="color:#6A7E98">Process2Diagram v5.14</strong> &nbsp;·&nbsp;
  Arquitetura de segurança documentada conforme LGPD Lei 13.709/2018 &nbsp;·&nbsp;
  Para dúvidas de conformidade ou solicitação de relatório de auditoria, contate o
  responsável pelo tratamento de dados do seu contexto organizacional. &nbsp;·&nbsp;
  <em>Esta página é atualizada a cada entrega de versão.</em>
</div>
""", unsafe_allow_html=True)
