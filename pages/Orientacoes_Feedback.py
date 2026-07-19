# pages/Orientacoes_Feedback.py
# ─────────────────────────────────────────────────────────────────────────────
# Guia do fluxo de Avaliação/Feedback (PC191) — Ajuda
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
<title>Guia de Avaliação e Feedback</title>
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

  /* ── Value table ── */
  table.value { width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 0.88rem; }
  table.value th, table.value td { padding: 10px 14px; border-bottom: 1px solid #1e3a5f; text-align: left; vertical-align: top; }
  table.value th { color: var(--amber); font-weight: 600; }
  table.value td { color: var(--text); }
</style>
</head>
<body>

<!-- ── Hero ── -->
<div class="hero">
  <h1>⭐ <span>Avaliação e Feedback</span> — Guia Completo</h1>
  <p>Como avaliar respostas do Assistente e artefatos gerados, o que acontece com essa avaliação, e por que isso importa para o negócio — não é um contador de estrelinhas, é o único sinal de qualidade que vem de quem realmente usa o resultado.</p>
</div>

<!-- ── TOC ── -->
<div class="toc">
  <h3>Neste guia</h3>
  <a data-target="s1" href="javascript:void(0)">1. O problema que isso resolve</a>
  <a data-target="s2" href="javascript:void(0)">2. Onde avaliar — os dois pontos</a>
  <a data-target="s3" href="javascript:void(0)">3. Como funciona cada widget</a>
  <a data-target="s4" href="javascript:void(0)">4. Para onde vai a avaliação</a>
  <a data-target="s5" href="javascript:void(0)">5. Valor para o negócio</a>
  <a data-target="s6" href="javascript:void(0)">6. O que isto NÃO faz (por decisão deliberada)</a>
  <a data-target="s7" href="javascript:void(0)">7. Boas práticas</a>
  <a data-target="s8" href="javascript:void(0)">8. Perguntas frequentes</a>
</div>

<!-- ── 1. O problema ── -->
<div class="section" id="s1">
  <h2>1. O problema que isso resolve</h2>
  <p>O P2D roda um pipeline multi-agente e entrega artefatos — BPMN, ata, requisitos, respostas
  do Assistente. O pipeline reportar "sucesso" (sem erro, sem exceção) prova que ele
  <strong>executou</strong>. Não prova que o resultado foi <strong>bom</strong>.</p>
  <p>Até esta funcionalidade existir, não havia nenhuma forma de um usuário sinalizar
  "este BPMN não reflete bem o processo" ou "esta resposta não respondeu minha pergunta" —
  o único sinal de qualidade disponível era técnico (telemetria de erro, latência,
  validação de schema), nunca <em>percebido por quem usa</em>.</p>
  <div class="tip"><strong>Em uma frase:</strong> telemetria mede se o sistema funcionou;
  feedback mede se o resultado serviu. São sinais diferentes, e só o segundo vem de gente,
  não de código.</div>
</div>

<hr>

<!-- ── 2. Onde avaliar ── -->
<div class="section" id="s2">
  <h2>2. Onde avaliar — os dois pontos</h2>
  <div class="card-grid">
    <div class="card">
      <div class="icon">💬</div>
      <h4>Respostas do Assistente</h4>
      <p><strong>Análise → Assistente</strong>, modo "💬 Assistente" (não no modo "🔬 Análise
      Autônoma"). Aparece 👍/👎 logo abaixo de cada resposta, ao lado do botão
      "📋 Copiar resposta".</p>
    </div>
    <div class="card">
      <div class="icon">📐</div>
      <h4>Processos BPMN</h4>
      <p><strong>Análise → Artefatos</strong>, aba "📐 Processos BPMN". Depois de selecionar
      uma reunião no seletor, botão "⭐ Avaliar" ao lado do botão de promoção a Ativo de
      Negócio.</p>
    </div>
    <div class="card">
      <div class="icon">📋</div>
      <h4>Atas de reunião</h4>
      <p><strong>Análise → Artefatos</strong>, aba "🗓️ Reuniões". Dentro do expander de cada
      reunião, na seção da ata, mesmo botão "⭐ Avaliar" ao lado da promoção.</p>
    </div>
    <div class="card">
      <div class="icon">🔜</div>
      <h4>Requisitos e SBVR — ainda não</h4>
      <p>Decisão deliberada de escopo: uma reunião pode ter dezenas de requisitos — avaliação
      item a item exigiria um desenho de UI próprio, tratado como decisão de produto
      separada, não incluída nesta primeira versão.</p>
    </div>
  </div>
</div>

<hr>

<!-- ── 3. Como funciona cada widget ── -->
<div class="section" id="s3">
  <h2>3. Como funciona cada widget</h2>

  <h3>👍 / 👎 — respostas do Assistente</h3>
  <p>Um clique, sem formulário. Selecionar um dos dois já registra a avaliação
  imediatamente — não existe botão "enviar" separado. Depois de avaliada, a mensagem para
  de mostrar o widget (rastreado durante a sessão atual; recarregar a página faz o widget
  reaparecer, já que o histórico do chat não guarda um identificador permanente por
  mensagem).</p>

  <h3>⭐ 1–5 + aceitável + comentário — artefatos (BPMN, ata)</h3>
  <p>Clique em "⭐ Avaliar" para abrir o formulário: nota de 1 a 5 estrelas, uma caixa
  "✅ Aceitável para uso", e um campo de comentário opcional — depois "Enviar avaliação".
  Clicar em "⭐ Avaliar" de novo fecha o formulário sem enviar nada.</p>
  <div class="tip"><strong>Por que dois tipos de widget diferentes?</strong> Uma resposta de
  chat é lida em segundos — pedir 4 critérios numa mensagem de chat seria fricção maior que
  o valor do dado coletado. Um artefato (BPMN, ata) é revisado com mais calma — vale o
  formulário mais completo, com espaço para explicar o que não ficou bom.</div>
</div>

<hr>

<!-- ── 4. Para onde vai ── -->
<div class="section" id="s4">
  <h2>4. Para onde vai a avaliação</h2>
  <div class="arch">
<span class="hl">Clique no widget (👍/👎 ou ⭐+aceitável+comentário)</span>
              │
              ▼
   <span class="ok">save_feedback()</span>  →  tabela <span class="hl">feedback</span> (Supabase)
              <span class="dim">1 linha crua por avaliação — nota, aceitável, comentário,</span>
              <span class="dim">tipo de artefato, id do artefato, quem avaliou, quando</span>
              │
              ▼
   <span class="ok">get_feedback_summary(project_id)</span>
              <span class="dim">agrega na LEITURA (não existe uma tabela de médias pré-calculadas</span>
              <span class="dim">— evita inconsistência de atualizar 2 lugares a cada avaliação nova)</span>
              │
              ▼
   <span class="ok">diagnostico_projeto()</span>  ← ferramenta do Assistente, sem LLM
              <span class="dim">8º item do checkup: taxa de aceitação e nota média por tipo</span>
              <span class="dim">de artefato — com mínimo de 3 avaliações antes de virar sinal</span>
              │
              ▼
   Aparece como <span class="hl">🔴 Crítico</span> / <span class="hl">🟡 Atenção</span> / <span class="hl">🟢 OK</span>
   + ação recomendada, quando você pedir um diagnóstico do projeto
  </div>
  <p>Pergunte ao Assistente <em>"faça um diagnóstico do projeto"</em> ou <em>"checkup do
  projeto"</em> para ver a avaliação incorporada junto com integridade do banco,
  contradições, ROI-TR e outros sinais já existentes.</p>
</div>

<hr>

<!-- ── 5. Valor para o negócio ── -->
<div class="section" id="s5">
  <h2>5. Valor para o negócio</h2>
  <table class="value">
    <tr><th>Sem feedback</th><th>Com feedback</th></tr>
    <tr>
      <td>"O pipeline processou 40 reuniões sem erro" — não diz nada sobre se os BPMNs
      gerados realmente representam os processos discutidos.</td>
      <td>"Processos BPMN: 60% de aceitação nas últimas avaliações" — um número que aponta
      exatamente onde investigar, com comentários específicos anexados.</td>
    </tr>
    <tr>
      <td>Decisão de melhorar um prompt/skill é baseada em intuição de quem desenvolve, ou
      em reclamação informal que não fica registrada em lugar nenhum.</td>
      <td>Decisão é baseada em evidência agregada e rastreável — quantas avaliações, qual
      nota média, quais comentários — a mesma fonte de dado toda vez que a pergunta for
      feita de novo.</td>
    </tr>
    <tr>
      <td>Degradação de qualidade (um provider mudou de comportamento, um skill ficou
      desatualizado) só aparece quando alguém reclama diretamente — tarde, e sem dado
      estruturado por trás.</td>
      <td>Cai abaixo do limiar de aceitação → aparece como 🟡/🔴 no diagnóstico do projeto
      antes de virar reclamação recorrente — mesmo princípio já usado pela telemetria de
      erro de provider (ver <strong>Ajuda → Cache LLM</strong> para o conceito irmão de
      observabilidade nesta arquitetura).</td>
    </tr>
    <tr>
      <td>Comentários qualitativos de usuários se perdem em conversas, e-mails ou não são
      registrados de jeito nenhum.</td>
      <td>Comentário fica anexado ao artefato específico (qual BPMN, qual ata) — contexto
      concreto para quem for revisar, não uma média genérica sem explicação.</td>
    </tr>
  </table>
  <div class="tip"><strong>Em uma frase:</strong> isto fecha o loop entre "o sistema gerou
  um artefato" e "o artefato foi útil de verdade" — sem esse loop, qualidade percebida pelo
  usuário final nunca vira dado que o time de desenvolvimento consegue agir em cima.</div>
</div>

<hr>

<!-- ── 6. O que NÃO faz ── -->
<div class="section" id="s6">
  <h2>6. O que isto NÃO faz (por decisão deliberada)</h2>
  <p>Esta funcionalidade nasceu de uma proposta maior, de 3 camadas: (1) coleta de feedback,
  (2) um agente que diagnostica o sistema a partir desse feedback, e (3) um mecanismo que
  <strong>aplicaria mudanças automaticamente</strong> (ajustar prompts, pesos de validador)
  com base nas próprias recomendações — sem revisão humana clara para as de baixa
  prioridade.</p>
  <div class="warn"><strong>Só a Camada 1 (coleta) foi implementada.</strong> As camadas 2 e
  3 foram avaliadas e descartadas: a camada 2 seria um agente LLM redundante com
  <code>diagnostico_projeto()</code> — que já faz esse diagnóstico de forma determinística,
  sem custo de LLM; a camada 3 (auto-aplicar mudanças no sistema sem supervisão humana) não
  tem precedente neste projeto e contraria os princípios de arquitetura já estabelecidos
  (Fail-Open — degradar graciosamente, nunca agir sozinho — e supervisão humana como regra
  de governança). Nenhuma avaliação, por pior que seja, modifica automaticamente um prompt,
  um skill ou o comportamento de um agente.</div>
  <p>Outras limitações conhecidas desta primeira versão:</p>
  <ul class="steps">
    <li>
      <div class="step-num">1</div>
      <div class="step-body">
        <strong>Thumbs não persiste "já avaliado" entre sessões</strong>
        <span>Recarregar a página do Assistente faz o widget de uma resposta já avaliada
        reaparecer — o histórico do chat não guarda um identificador permanente por
        mensagem.</span>
      </div>
    </li>
    <li>
      <div class="step-num">2</div>
      <div class="step-body">
        <strong>Sinal exige volume mínimo</strong>
        <span>Menos de 3 avaliações de um tipo de artefato não aparece no diagnóstico — evita
        que 1 avaliação isolada (boa ou ruim) pareça uma tendência real.</span>
      </div>
    </li>
  </ul>
</div>

<hr>

<!-- ── 7. Boas práticas ── -->
<div class="section" id="s7">
  <h2>7. Boas práticas</h2>
  <div class="card-grid">
    <div class="card">
      <div class="icon">✅</div>
      <h4>Seja específico no comentário</h4>
      <p>"Faltou a lane do jurídico" ajuda muito mais que "não ficou bom" — o comentário fica
      anexado ao artefato exato, use isso a seu favor.</p>
    </div>
    <div class="card">
      <div class="icon">✅</div>
      <h4>Avalie mesmo quando está bom</h4>
      <p>Uma nota alta também é dado — sem ela, a taxa de aceitação fica artificialmente
      baixa (só quem reclama avalia).</p>
    </div>
    <div class="card">
      <div class="icon">✅</div>
      <h4>Use "aceitável para uso" com critério prático</h4>
      <p>Pergunta é "dá pra usar isso como está?", não "está perfeito?" — um BPMN com nota 3
      ainda pode ser aceitável se cobre o essencial.</p>
    </div>
    <div class="card">
      <div class="icon">✅</div>
      <h4>Peça o diagnóstico periodicamente</h4>
      <p>"Faça um diagnóstico do projeto" no Assistente mostra a avaliação já agregada junto
      com os outros sinais de saúde do projeto.</p>
    </div>
  </div>
</div>

<hr>

<!-- ── 8. FAQ ── -->
<div class="section" id="s8">
  <h2>8. Perguntas frequentes</h2>

  <h3>Quem vê minha avaliação e meu comentário?</h3>
  <p>Fica registrada com <code>created_by</code> (seu usuário) na tabela <code>feedback</code>
  do projeto — visível para quem tiver acesso ao projeto, não é anônima. O objetivo é dar
  contexto de revisão, não coletar denúncia anônima.</p>

  <h3>Avaliar um artefato muda ele automaticamente?</h3>
  <p>Não, nunca. Avaliação é só um sinal registrado — nenhuma mudança automática acontece a
  partir dela (ver seção 6). Regenerar o artefato continua sendo uma ação manual separada
  (botão de reprocessar, ou pedir ao Assistente).</p>

  <h3>Posso avaliar o mesmo artefato mais de uma vez?</h3>
  <p>Sim — cada envio grava uma nova linha na tabela. Se o artefato foi regenerado
  (reprocessado) desde a última avaliação, uma nova avaliação reflete a versão atual;
  avaliações antigas continuam no histórico, não são apagadas.</p>

  <h3>Por que requisitos e SBVR não têm avaliação ainda?</h3>
  <p>Uma reunião pode ter dezenas de requisitos — avaliar item a item exige um desenho de
  UI diferente do "um botão por artefato" usado em BPMN/ata. Ficou fora desta primeira
  versão por decisão deliberada de escopo, não esquecimento.</p>

  <h3>O que acontece se pouca gente avaliar?</h3>
  <p>Nada de errado — "Feedback de usuário: volume insuficiente para diagnóstico ainda"
  aparece no checkup em vez de um sinal, até acumular pelo menos 3 avaliações por tipo de
  artefato. Zero avaliações não é tratado como problema, só como dado ainda não
  disponível.</p>
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
