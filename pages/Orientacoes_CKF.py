# pages/Orientacoes_CKF.py
# ─────────────────────────────────────────────────────────────────────────────
# Guia do Context Knowledge File (CKF) — Ajuda
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
from ui.auth_gate import apply_auth_gate

apply_auth_gate()

# ── HTML guide ────────────────────────────────────────────────────────────────
_guide_html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Guia CKF</title>
<style>
  :root {
    --navy:  #0d2a4a;
    --amber: #f59e0b;
    --blue:  #1e40af;
    --light: #e0e7f0;
    --bg:    #0a1929;
    --card:  #0f2235;
    --text:  #e0e7f0;
    --sub:   #94a3b8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.7;
    font-size: 15px;
    padding: 0 0 60px;
  }

  /* ── Header ── */
  .hero {
    background: linear-gradient(135deg, var(--navy) 0%, #112240 100%);
    padding: 48px 40px 36px;
    border-bottom: 3px solid var(--amber);
  }
  .hero h1 { font-size: 2.1rem; font-weight: 700; color: #fff; margin-bottom: 8px; }
  .hero h1 span { color: var(--amber); }
  .hero p { color: var(--sub); font-size: 1.05rem; max-width: 680px; }

  /* ── Nav ── */
  .toc {
    background: var(--card);
    border-left: 4px solid var(--amber);
    padding: 20px 28px;
    margin: 32px 40px;
    border-radius: 6px;
  }
  .toc h3 { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px; color: var(--amber); margin-bottom: 12px; }
  .toc a { display: block; color: var(--light); text-decoration: none; padding: 4px 0; font-size: 0.95rem; }
  .toc a:hover { color: var(--amber); }
  .toc a::before { content: "→ "; color: var(--amber); }

  /* ── Sections ── */
  .section { padding: 36px 40px 0; max-width: 900px; }
  .section h2 {
    font-size: 1.35rem; font-weight: 700; color: var(--amber);
    border-bottom: 1px solid #1e3a5f; padding-bottom: 10px; margin-bottom: 18px;
  }
  .section h3 { font-size: 1.05rem; font-weight: 600; color: #93c5fd; margin: 20px 0 10px; }
  .section p  { color: var(--text); margin-bottom: 14px; }

  /* ── Cards ── */
  .card {
    background: var(--card);
    border: 1px solid #1e3a5f;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 16px;
  }
  .card .icon { font-size: 1.4rem; margin-bottom: 8px; }
  .card h4 { font-size: 0.95rem; font-weight: 600; color: #93c5fd; margin-bottom: 6px; }
  .card p  { font-size: 0.9rem; color: var(--sub); margin: 0; }

  .card-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px; }

  /* ── Steps ── */
  .steps { list-style: none; padding: 0; }
  .steps li {
    display: flex; gap: 16px; padding: 14px 0;
    border-bottom: 1px solid #1a3050;
  }
  .steps li:last-child { border: none; }
  .step-num {
    background: var(--amber); color: #000; font-weight: 700;
    border-radius: 50%; width: 30px; height: 30px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; font-size: 0.85rem;
  }
  .step-body { flex: 1; }
  .step-body strong { display: block; color: #fff; margin-bottom: 4px; }
  .step-body span   { font-size: 0.88rem; color: var(--sub); }

  /* ── Code ── */
  pre {
    background: #0a1929;
    border: 1px solid #1e3a5f;
    border-radius: 6px;
    padding: 16px 20px;
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    font-size: 0.82rem;
    color: #7dd3fc;
    overflow-x: auto;
    margin-bottom: 16px;
    white-space: pre;
  }
  code { font-family: 'Cascadia Code', monospace; font-size: 0.85rem; color: #7dd3fc; }

  /* ── Architecture ── */
  .arch {
    background: var(--card);
    border: 1px solid #1e3a5f;
    border-radius: 8px;
    padding: 24px;
    font-family: monospace;
    font-size: 0.82rem;
    color: #7dd3fc;
    line-height: 1.9;
    margin-bottom: 20px;
    overflow-x: auto;
  }
  .arch .hl { color: var(--amber); font-weight: 700; }
  .arch .ok { color: #4ade80; }
  .arch .dim { color: #475569; }

  /* ── Badges ── */
  .badge {
    display: inline-block; font-size: 0.72rem; font-weight: 700;
    padding: 2px 8px; border-radius: 12px; margin-right: 6px;
  }
  .badge-amber { background: #78350f; color: #fcd34d; }
  .badge-blue  { background: #1e3a8a; color: #93c5fd; }
  .badge-green { background: #14532d; color: #86efac; }

  /* ── Tip boxes ── */
  .tip {
    background: #0c2744;
    border-left: 3px solid #3b82f6;
    border-radius: 4px;
    padding: 12px 16px;
    font-size: 0.88rem;
    color: #93c5fd;
    margin-bottom: 16px;
  }
  .tip strong { color: #60a5fa; }
  .warn {
    background: #2d1a00;
    border-left: 3px solid var(--amber);
    border-radius: 4px;
    padding: 12px 16px;
    font-size: 0.88rem;
    color: #fcd34d;
    margin-bottom: 16px;
  }

  hr { border: none; border-top: 1px solid #1e3a5f; margin: 32px 40px; }
</style>
</head>
<body>

<!-- ── Hero ── -->
<div class="hero">
  <h1>📖 <span>Context Knowledge File</span> — Guia Completo</h1>
  <p>Entenda o que é o CKF, como usá-lo para enriquecer o pipeline de agentes e como funciona a sua atualização evolutiva automática.</p>
</div>

<!-- ── TOC ── -->
<div class="toc">
  <h3>Neste guia</h3>
  <a data-target="s1" href="javascript:void(0)">1. O que é o CKF?</a>
  <a data-target="s2" href="javascript:void(0)">2. Para que serve?</a>
  <a data-target="s3" href="javascript:void(0)">3. Como funciona na arquitetura</a>
  <a data-target="s4" href="javascript:void(0)">4. Arquivos de referência do contexto</a>
  <a data-target="s5" href="javascript:void(0)">5. CKF Evolutivo — atualização automática</a>
  <a data-target="s6" href="javascript:void(0)">6. Como editar o CKF manualmente</a>
  <a data-target="s7" href="javascript:void(0)">7. Boas práticas e exemplos</a>
  <a data-target="s8" href="javascript:void(0)">8. Perguntas frequentes</a>
</div>

<!-- ── 1. O que é ── -->
<div class="section" id="s1">
  <h2>1. O que é o Context Knowledge File?</h2>
  <p>O <strong>Context Knowledge File (CKF)</strong> é um documento Markdown associado a cada contexto de trabalho. Ele funciona como a <em>memória institucional</em> do contexto — um repositório de informações permanentes sobre o negócio que o sistema deve sempre ter em mente ao processar qualquer transcrição.</p>
  <div class="card-grid">
    <div class="card">
      <div class="icon">🧠</div>
      <h4>Memória do Contexto</h4>
      <p>Persiste entre reuniões. O que foi aprendido numa reunião fica disponível para todas as seguintes.</p>
    </div>
    <div class="card">
      <div class="icon">⚡</div>
      <h4>Injeção Automática</h4>
      <p>Injetado no prompt de sistema de todos os agentes LLM antes de cada execução do pipeline.</p>
    </div>
    <div class="card">
      <div class="icon">🔄</div>
      <h4>Atualização Evolutiva</h4>
      <p>O CKF Evolutivo mescla automaticamente novos insights de cada reunião, sem apagar conteúdo manual.</p>
    </div>
    <div class="card">
      <div class="icon">✍️</div>
      <h4>Editável Manualmente</h4>
      <p>Você tem controle total. Edite, expanda ou corrija via Configurações → Context Knowledge File.</p>
    </div>
  </div>
</div>

<hr>

<!-- ── 2. Para que serve ── -->
<div class="section" id="s2">
  <h2>2. Para que serve?</h2>
  <p>Sem o CKF, cada reunião é processada isoladamente — os agentes não sabem nada sobre o contexto organizacional. Com o CKF, os agentes têm acesso a:</p>
  <ul class="steps">
    <li>
      <div class="step-num">👥</div>
      <div class="step-body">
        <strong>Participantes frequentes</strong>
        <span>Nomes completos, cargos, siglas — evitam identificação errada de lanes no BPMN e atribuição incorreta de decisões.</span>
      </div>
    </li>
    <li>
      <div class="step-num">📚</div>
      <div class="step-body">
        <strong>Glossário do domínio</strong>
        <span>Termos técnicos, siglas internas, nomes de sistemas — garantem vocabulário consistente em atas, requisitos e SBVR.</span>
      </div>
    </li>
    <li>
      <div class="step-num">⚙️</div>
      <div class="step-body">
        <strong>Processos e contexto já conhecidos</strong>
        <span>Descrição do projeto, fases, restrições — o agente entende o que está sendo discutido sem depender só da transcrição.</span>
      </div>
    </li>
    <li>
      <div class="step-num">📏</div>
      <div class="step-body">
        <strong>Regras e políticas permanentes</strong>
        <span>Conformidade, padrões, aprovações — capturadas uma vez e aplicadas a todas as reuniões futuras.</span>
      </div>
    </li>
    <li>
      <div class="step-num">🔗</div>
      <div class="step-body">
        <strong>Decisões históricas relevantes</strong>
        <span>Contexto acumulado de reuniões anteriores que influencia como interpretar novas decisões.</span>
      </div>
    </li>
  </ul>
</div>

<hr>

<!-- ── 3. Arquitetura ── -->
<div class="section" id="s3">
  <h2>3. Como funciona na arquitetura</h2>
  <p>O diagrama abaixo mostra o fluxo completo — desde a transcrição até os agentes, com o CKF e os arquivos de referência injetados como contexto adicional:</p>

  <div class="arch">
<span class="hl">Contexto Ativo (Supabase)</span>
    │
    ├── <span class="ok">contexts.skill_md</span>   →  <span class="hl">CKF Manual/Evolutivo</span>
    └── <span class="ok">context_files.content_text</span>  →  <span class="hl">Arquivos de Referência</span>
              │                               │
              └───────────┬───────────────────┘
                          │
              <span class="dim">Pipeline.py carrega ambos em hub antes de executar</span>
                          │
                  ┌───────▼────────────┐
                  │  KnowledgeHub      │
                  │  hub.context_skill │
                  │  hub.context_files_text │
                  └───────┬────────────┘
                          │  (injetado no system prompt)
          ┌───────────────┼───────────────┬─────────────────┐
          ▼               ▼               ▼                 ▼
    <span class="hl">AgentBPMN</span>    <span class="hl">AgentMinutes</span>  <span class="hl">AgentSBVR</span>      <span class="hl">AgentBMM</span>
          │               │               │                 │
          └───────────────┴───────────────┴─────────────────┘
                          │
              <span class="dim">## Conhecimento do Contexto  (CKF)</span>
              <span class="dim">## Documentos de Referência  (Arquivos)</span>
                          │
                  Resultados enriquecidos
  </div>
  <div class="tip"><strong>Nota técnica:</strong> a injeção ocorre no <em>system prompt</em> de cada agente. O CKF aparece como seção <code>## Conhecimento do Contexto</code> e os arquivos de referência como <code>## Documentos de Referência do Contexto</code>, ambos após o skill do agente.</div>
</div>

<hr>

<!-- ── 4. Arquivos de Referência ── -->
<div class="section" id="s4">
  <h2>4. Arquivos de referência do contexto</h2>
  <p>Além do CKF editável manualmente, você pode fazer upload de documentos inteiros que o sistema extrai e injeta automaticamente nos agentes:</p>
  <div class="card-grid">
    <div class="card">
      <div class="icon">🌐</div>
      <h4>HTML / HTM</h4>
      <p>Páginas, wikis, políticas exportadas. O texto é extraído com segurança via parser Python — scripts e iframes são descartados.</p>
    </div>
    <div class="card">
      <div class="icon">📊</div>
      <h4>PowerPoint (PPTX)</h4>
      <p>Apresentações corporativas. Extrai texto de todos os slides e notas de apresentador por slide.</p>
    </div>
    <div class="card">
      <div class="icon">📄</div>
      <h4>PDF</h4>
      <p>Manuais, contratos, relatórios. Extrai texto página a página com cabeçalho de página.</p>
    </div>
    <div class="card">
      <div class="icon">📝</div>
      <h4>TXT / MD</h4>
      <p>Qualquer arquivo de texto simples ou Markdown. Decodificação direta UTF-8.</p>
    </div>
  </div>
  <p>Os arquivos são gerenciados em <strong>Configurações → Arquivos de Referência do Contexto</strong>. O texto extraído é persistido no Supabase (tabela <code>context_files</code>) e carregado automaticamente antes de cada execução do pipeline.</p>
  <div class="warn">Limite de tamanho: 10 MB por arquivo. Para PDFs muito longos, considere dividir em seções relevantes antes do upload.</div>

  <h3>Como adicionar um arquivo</h3>
  <ol class="steps">
    <li>
      <div class="step-num">1</div>
      <div class="step-body">
        <strong>Acesse Configurações → Arquivos de Referência do Contexto</strong>
        <span>Selecione o contexto de destino no selectbox.</span>
      </div>
    </li>
    <li>
      <div class="step-num">2</div>
      <div class="step-body">
        <strong>Arraste ou clique em "Browse files"</strong>
        <span>Formatos aceitos: .html, .htm, .pptx, .pdf, .txt, .md — máximo 10 MB.</span>
      </div>
    </li>
    <li>
      <div class="step-num">3</div>
      <div class="step-body">
        <strong>Clique em "⬆️ Extrair e Salvar"</strong>
        <span>O texto é extraído localmente e salvo no Supabase. O arquivo original não é armazenado — apenas o texto.</span>
      </div>
    </li>
    <li>
      <div class="step-num">4</div>
      <div class="step-body">
        <strong>O arquivo aparece na lista</strong>
        <span>Clique no ícone 🗑 ao lado do arquivo para removê-lo a qualquer momento.</span>
      </div>
    </li>
  </ol>
</div>

<hr>

<!-- ── 5. CKF Evolutivo ── -->
<div class="section" id="s5">
  <h2>5. CKF Evolutivo — atualização automática</h2>
  <p>O <strong>CKF Evolutivo</strong> é um agente pós-pipeline opcional (<code>AgentCKFUpdater</code>) que analisa os artefatos produzidos pela reunião e <em>mescla automaticamente</em> novos insights no CKF existente.</p>

  <div class="arch">
Pipeline principal concluído
    │
    ▼ (se "🧠 Atualizar CKF do Contexto" está habilitado)
<span class="hl">AgentCKFUpdater</span>
    │
    ├── Lê: hub.minutes    (participantes, pauta, decisões)
    ├── Lê: hub.bpmn       (nome do processo, lanes)
    ├── Lê: hub.sbvr       (vocabulário, regras)
    ├── Lê: hub.bmm        (visão, metas, estratégias)
    ├── Lê: hub.requirements (títulos dos requisitos)
    └── Lê: hub.context_skill (CKF atual — para mesclagem)
           │
           ▼  (1 chamada LLM, output: Markdown puro)
    <span class="ok">CKF atualizado</span>
           │
           ├── hub.context_skill ← atualizado na sessão
           └── Supabase: contexts.skill_md ← persistido
  </div>

  <h3>Regras de mesclagem (garantidas pelo prompt do agente)</h3>
  <ul class="steps">
    <li>
      <div class="step-num">✅</div>
      <div class="step-body">
        <strong>Preserva conteúdo manual</strong>
        <span>Nada do CKF existente é removido sem motivo. O agente só adiciona ou atualiza.</span>
      </div>
    </li>
    <li>
      <div class="step-num">✅</div>
      <div class="step-body">
        <strong>Sem duplicação</strong>
        <span>Se o participante ou termo já existe, não é adicionado novamente.</span>
      </div>
    </li>
    <li>
      <div class="step-num">✅</div>
      <div class="step-body">
        <strong>Adiciona apenas o que é novo e relevante</strong>
        <span>Participantes novos, termos do glossário descobertos, decisões estratégicas, regras de negócio novas.</span>
      </div>
    </li>
    <li>
      <div class="step-num">✅</div>
      <div class="step-body">
        <strong>Markdown limpo</strong>
        <span>Output é Markdown puro — sem bloco de código, sem JSON, sem prefixo. Pronto para edição humana.</span>
      </div>
    </li>
  </ul>

  <h3>Como ativar</h3>
  <p>Na sidebar do Pipeline, expanda <strong>⚙️ Configuração Avançada → Análise de Negócio</strong> e marque a opção <strong>"🧠 Atualizar CKF do Contexto"</strong> antes de executar o pipeline.</p>
  <div class="tip"><strong>Dica:</strong> ative o CKF Evolutivo nas primeiras 3–5 reuniões de um contexto para construir uma base sólida. Depois, revise manualmente e desative se preferir controle total.</div>
</div>

<hr>

<!-- ── 6. Edição manual ── -->
<div class="section" id="s6">
  <h2>6. Como editar o CKF manualmente</h2>
  <p>Acesse <strong>Configurações → Context Knowledge File (CKF)</strong>. Cada contexto tem seu próprio expander. O editor aceita Markdown completo.</p>

  <h3>Template padrão</h3>
  <p>Ao abrir um CKF vazio, o template é pré-carregado com as seguintes seções:</p>

<pre>## Contexto Geral
Descreva brevemente o projeto, cliente e objetivo.

## Participantes Frequentes
- **Nome Completo** — Cargo / Papel no projeto

## Glossário
| Termo | Definição |
|-------|-----------|
| ABC   | Descrição |

## Processos Conhecidos
- Nome do processo: descrição breve

## Regras e Políticas
- Regra ou política relevante

## Histórico Relevante
- Decisões ou eventos importantes do passado</pre>

  <p>Você pode personalizar livremente — adicionar seções, tabelas, listas hierárquicas. O agente lê o Markdown sem restrição de formato.</p>
</div>

<hr>

<!-- ── 7. Boas práticas ── -->
<div class="section" id="s7">
  <h2>7. Boas práticas e exemplos</h2>

  <h3>O que colocar no CKF</h3>
  <div class="card-grid">
    <div class="card">
      <div class="icon">✅</div>
      <h4>Participantes com cargos</h4>
      <p>"Maria Silva — Gerente de TI" ajuda o BPMN a criar lanes corretas e a ata a atribuir decisões com precisão.</p>
    </div>
    <div class="card">
      <div class="icon">✅</div>
      <h4>Siglas do negócio</h4>
      <p>"DCI = Documento de Confirmação de Implantação" evita que o agente invente definições incorretas.</p>
    </div>
    <div class="card">
      <div class="icon">✅</div>
      <h4>Restrições do projeto</h4>
      <p>"Prazo final: 30/06/2026" ou "Integração com SAP obrigatória" aparecem corretamente nos requisitos.</p>
    </div>
    <div class="card">
      <div class="icon">✅</div>
      <h4>Fases e marcos</h4>
      <p>"Fase 1 concluída em março" dá contexto histórico para interpretar referências nas transcrições.</p>
    </div>
  </div>

  <h3>O que <em>não</em> colocar no CKF</h3>
  <div class="tip"><strong>Evite:</strong> informações que mudam frequentemente (datas de reunião, status corrente de tarefas) — essas pertencem à ata. O CKF é para conhecimento <em>estável e permanente</em> do contexto.</div>

  <h3>Exemplo de CKF bem preenchido</h3>
<pre>## Contexto Geral
Projeto de modernização do ERP da Empresa XYZ.
Objetivo: migrar do sistema legado para SAP S/4HANA até Q3 2026.

## Participantes Frequentes
- **Carlos Drummond** — Diretor de TI (patrocinador)
- **Ana Lima** — Gerente de Projeto
- **Pedro Souza** — Arquiteto de Soluções SAP
- **Luísa Torres** — Líder de Negócios (RH)

## Glossário
| Termo | Definição |
|-------|-----------|
| S/4HANA | SAP S/4HANA — plataforma ERP de destino |
| DCI     | Documento de Confirmação de Implantação |
| Legado  | Sistema atual (Oracle EBS 12.1.3) |
| Sprint  | Ciclo de 2 semanas (metodologia Scrum) |

## Processos Conhecidos
- **Admissão de funcionários**: inicia no RH, aprovação do gestor direto e TI
- **Compras**: aprovação automática até R$5.000; acima disso requer CFO

## Regras e Políticas
- Toda mudança de escopo requer CCB (Comitê de Controle de Mudanças)
- Integração com sistemas legados mantida por 24 meses pós-go-live

## Histórico Relevante
- Jan 2026: kick-off aprovado pelo conselho
- Mar 2026: fase de mapeamento de processos concluída (27 processos)</pre>
</div>

<hr>

<!-- ── 8. FAQ ── -->
<div class="section" id="s8">
  <h2>8. Perguntas frequentes</h2>

  <h3>O CKF é compartilhado entre reuniões do mesmo contexto?</h3>
  <p>Sim. O CKF é armazenado no contexto (não na reunião) e aplicado a <em>todas</em> as reuniões daquele contexto. É exatamente isso que o torna uma memória persistente e cumulativa.</p>

  <h3>O CKF Evolutivo pode sobrescrever algo que escrevi manualmente?</h3>
  <p>O prompt do <code>AgentCKFUpdater</code> instrui explicitamente o LLM a <em>preservar</em> o conteúdo manual e apenas adicionar novidades. Porém, como qualquer output de LLM, sujeito a imprecisões. Recomendamos revisar o CKF após as primeiras atualizações automáticas.</p>

  <h3>Quanto texto o CKF deve ter?</h3>
  <p>Não há limite técnico, mas textos muito longos consomem mais tokens e podem diluir o foco do agente. Uma boa referência: 200–600 palavras. Use os arquivos de referência para documentos extensos.</p>

  <h3>O Assistente pode ler o CKF?</h3>
  <p>O Assistente pode listar os arquivos de referência com o comando <code>list_context_files</code>. O conteúdo do CKF (<code>skill_md</code>) não é diretamente consultável pelo Assistente, mas está disponível via <code>save_context_skill</code> para escrita. Para consultar, use a página Configurações.</p>

  <h3>Preciso executar alguma migração SQL?</h3>
  <p>Para o CKF manual (<code>skill_md</code>): execute <code>migrate_v4_21_context.sql</code> (já disponível em Configurações → Migração de Schema).</p>
  <p>Para os arquivos de referência (<code>context_files</code>): execute <code>migrate_v4_22_context_files.sql</code>, disponível em Configurações → Arquivos de Referência do Contexto → 🔧 Migração v4.22.</p>
</div>

<script>
document.querySelectorAll('.toc a[data-target]').forEach(function(link) {
  link.addEventListener('click', function(e) {
    e.preventDefault();
    var target = document.getElementById(link.dataset.target);
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
});
</script>

</body>
</html>"""

st.components.v1.html(_guide_html, height=900, scrolling=True)
