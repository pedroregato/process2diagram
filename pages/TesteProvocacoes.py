# pages/TesteProvocacoes.py
# ─────────────────────────────────────────────────────────────────────────────
# Roteiro de teste manual das Provocacoes (PC190/PC200/PC201/PC202) - Manutencao,
# admin-only. Checklist interativo (persistencia via localStorage do navegador)
# com transcricoes prontas para reproduzir as 4 kinds em producao: absence,
# asymmetry, premise (LLM + validador deterministico) e contradiction (bridge
# deterministico sobre kh_contradictions/AgentContradictionDetector). "analogy"
# nao existe - avaliada e adiada (PC202).
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
from ui.auth_gate import apply_auth_gate

apply_auth_gate()

_guide_html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dossiê de Teste — Provocações</title>
<style>
  :root{
    --bg:#12181f;
    --panel:#1a222c;
    --panel-2:#212b37;
    --border:#2b3642;
    --text:#e8e6df;
    --text-muted:#8b93a0;
    --text-faint:#5b6472;
    --accent:#d9a441;
    --accent-dim:rgba(217,164,65,.14);
    --accent-line:rgba(217,164,65,.35);
    --ok:#4caf7d;
    --ok-dim:rgba(76,175,125,.14);
    --danger:#d9636b;
    --danger-dim:rgba(217,99,107,.14);
    --font-display:"Iowan Old Style","Palatino Linotype","Book Antiqua",Georgia,serif;
    --font-body:-apple-system,"Segoe UI",system-ui,sans-serif;
    --font-mono:ui-monospace,"Cascadia Code","SF Mono",Consolas,monospace;
  }

  *{box-sizing:border-box;}
  html,body{margin:0;padding:0;}
  body{
    background:
      radial-gradient(1200px 500px at 15% -10%, rgba(217,164,65,.06), transparent 60%),
      var(--bg);
    color:var(--text);
    font-family:var(--font-body);
    line-height:1.6;
    -webkit-font-smoothing:antialiased;
  }

  a{color:var(--accent);}

  .wrap{
    max-width:760px;
    margin:0 auto;
    padding:0 24px 96px;
  }

  /* ── progress rail ─────────────────────────────────────────── */
  .rail{
    position:sticky;
    top:0;
    z-index:20;
    background:rgba(18,24,31,.88);
    backdrop-filter:blur(6px);
    border-bottom:1px solid var(--border);
  }
  .rail-inner{
    max-width:760px;
    margin:0 auto;
    padding:12px 24px;
    display:flex;
    align-items:center;
    gap:14px;
  }
  .rail-label{
    font-family:var(--font-mono);
    font-size:.72rem;
    letter-spacing:.06em;
    color:var(--text-muted);
    white-space:nowrap;
  }
  .rail-bar{
    flex:1;
    height:5px;
    background:var(--panel-2);
    border-radius:3px;
    overflow:hidden;
  }
  .rail-fill{
    height:100%;
    width:0%;
    background:linear-gradient(90deg, var(--accent), #e8c27a);
    transition:width .35s ease;
  }
  .rail-count{
    font-family:var(--font-mono);
    font-variant-numeric:tabular-nums;
    font-size:.78rem;
    color:var(--text);
    white-space:nowrap;
  }

  /* ── header ────────────────────────────────────────────────── */
  header{
    padding:56px 0 36px;
    border-bottom:1px solid var(--border);
    margin-bottom:40px;
  }
  .eyebrow{
    font-family:var(--font-mono);
    font-size:.75rem;
    letter-spacing:.14em;
    text-transform:uppercase;
    color:var(--accent);
    margin-bottom:14px;
  }
  h1{
    font-family:var(--font-display);
    font-weight:600;
    font-size:2.35rem;
    line-height:1.15;
    margin:0 0 14px;
    text-wrap:balance;
    color:#f4f1e9;
  }
  .dek{
    font-size:1.02rem;
    color:var(--text-muted);
    max-width:60ch;
    margin:0 0 22px;
  }
  .meta-row{
    display:flex;
    flex-wrap:wrap;
    gap:10px;
  }
  .tag{
    font-family:var(--font-mono);
    font-size:.72rem;
    padding:4px 10px;
    border-radius:3px;
    border:1px solid var(--border);
    color:var(--text-muted);
  }
  .tag.kind-a{color:#e8c27a;border-color:var(--accent-line);}
  .tag.kind-s{color:#7fbf9e;border-color:rgba(76,175,125,.35);}
  .tag.kind-p{color:#d59aa0;border-color:rgba(217,99,107,.35);}
  .tag.kind-c{color:#8fb4d9;border-color:rgba(143,180,217,.35);}

  .callout{
    background:var(--accent-dim);
    border:1px solid var(--accent-line);
    border-radius:6px;
    padding:16px 18px;
    font-size:.92rem;
    color:#e9d9b8;
    margin-top:24px;
  }
  .callout b{color:var(--accent);}

  /* ── sections ──────────────────────────────────────────────── */
  section.step{
    margin-bottom:52px;
  }
  .step-head{
    display:flex;
    align-items:baseline;
    gap:16px;
    margin-bottom:6px;
  }
  .step-num{
    font-family:var(--font-mono);
    font-size:.85rem;
    color:var(--text-faint);
    letter-spacing:.04em;
  }
  h2{
    font-family:var(--font-display);
    font-weight:600;
    font-size:1.5rem;
    margin:0;
    color:#f4f1e9;
    text-wrap:balance;
  }
  .step-sub{
    color:var(--text-muted);
    font-size:.94rem;
    margin:6px 0 22px;
    max-width:64ch;
  }

  h3{
    font-family:var(--font-body);
    font-weight:600;
    font-size:.82rem;
    letter-spacing:.08em;
    text-transform:uppercase;
    color:var(--text-muted);
    margin:28px 0 12px;
  }

  /* ── transcript card ───────────────────────────────────────── */
  .transcript{
    background:var(--panel);
    border:1px solid var(--border);
    border-left:3px solid var(--accent);
    border-radius:0 8px 8px 0;
    padding:18px 20px;
    overflow-x:auto;
    margin-bottom:6px;
  }
  .transcript pre{
    margin:0;
    font-family:var(--font-mono);
    font-size:.83rem;
    line-height:1.75;
    white-space:pre-wrap;
    color:var(--text);
  }
  .transcript .spk{color:var(--accent);font-weight:600;}
  .copy-btn{
    display:inline-flex;
    align-items:center;
    gap:6px;
    margin-top:10px;
    background:transparent;
    border:1px solid var(--border);
    color:var(--text-muted);
    font-family:var(--font-mono);
    font-size:.72rem;
    letter-spacing:.04em;
    padding:6px 12px;
    border-radius:5px;
    cursor:pointer;
    transition:border-color .15s, color .15s;
  }
  .copy-btn:hover{border-color:var(--accent-line);color:var(--accent);}
  .copy-btn:focus-visible{outline:2px solid var(--accent);outline-offset:2px;}
  .copy-btn.done{color:var(--ok);border-color:rgba(76,175,125,.4);}

  .design-note{
    font-size:.88rem;
    color:var(--text-muted);
    margin:14px 0 4px;
  }
  .design-note b{color:var(--text);}
  .highlight-key{
    font-family:var(--font-mono);
    background:var(--accent-dim);
    color:#e8c27a;
    padding:1px 6px;
    border-radius:3px;
    border:1px solid var(--accent-line);
  }

  /* ── checklist ─────────────────────────────────────────────── */
  ul.checklist{
    list-style:none;
    margin:0 0 4px;
    padding:0;
    display:flex;
    flex-direction:column;
    gap:2px;
  }
  ul.checklist li{
    display:flex;
    align-items:flex-start;
    gap:11px;
    padding:9px 10px;
    border-radius:6px;
    transition:background .12s;
  }
  ul.checklist li:hover{background:var(--panel-2);}
  ul.checklist input[type="checkbox"]{
    appearance:none;
    -webkit-appearance:none;
    width:18px;
    height:18px;
    flex:0 0 18px;
    margin-top:2px;
    border:1.5px solid var(--border);
    border-radius:4px;
    background:var(--panel);
    cursor:pointer;
    position:relative;
    transition:border-color .15s, background .15s;
  }
  ul.checklist input[type="checkbox"]:hover{border-color:var(--accent-line);}
  ul.checklist input[type="checkbox"]:focus-visible{outline:2px solid var(--accent);outline-offset:2px;}
  ul.checklist input[type="checkbox"]:checked{
    background:var(--ok);
    border-color:var(--ok);
  }
  ul.checklist input[type="checkbox"]:checked::after{
    content:"";
    position:absolute;
    left:5px;
    top:1px;
    width:5px;
    height:9px;
    border:solid #0d1712;
    border-width:0 2px 2px 0;
    transform:rotate(40deg);
  }
  ul.checklist label{
    font-size:.93rem;
    color:var(--text);
    cursor:pointer;
  }
  ul.checklist li.checked label{
    color:var(--text-faint);
    text-decoration:line-through;
    text-decoration-color:var(--text-faint);
  }
  ul.checklist code{
    font-family:var(--font-mono);
    font-size:.85em;
    background:var(--panel-2);
    padding:1px 5px;
    border-radius:3px;
    color:#cfd6e0;
  }

  .subnote{
    font-size:.85rem;
    color:var(--text-faint);
    margin:10px 2px 0;
    padding-left:2px;
    border-left:2px solid var(--border);
    padding-left:12px;
  }
  .subnote b{color:var(--text-muted);}

  /* ── kind pills used inline ───────────────────────────────── */
  .pill{
    font-family:var(--font-mono);
    font-size:.76rem;
    padding:1px 8px;
    border-radius:20px;
    border:1px solid;
    white-space:nowrap;
  }
  .pill-a{color:#e8c27a;border-color:var(--accent-line);background:var(--accent-dim);}
  .pill-s{color:#7fbf9e;border-color:rgba(76,175,125,.35);background:var(--ok-dim);}
  .pill-p{color:#d59aa0;border-color:rgba(217,99,107,.35);background:var(--danger-dim);}
  .pill-c{color:#8fb4d9;border-color:rgba(143,180,217,.35);background:rgba(143,180,217,.1);}

  hr.rule{
    border:none;
    border-top:1px solid var(--border);
    margin:52px 0;
  }

  footer{
    color:var(--text-faint);
    font-size:.82rem;
    text-align:center;
    padding-top:8px;
  }

  @media (prefers-reduced-motion: reduce){
    *{transition:none !important;}
  }
</style>

<div class="rail">
  <div class="rail-inner">
    <span class="rail-label">PROGRESSO</span>
    <div class="rail-bar"><div class="rail-fill" id="railFill"></div></div>
    <span class="rail-count" id="railCount">0 / 0</span>
  </div>
</div>

<div class="wrap">

  <header>
    <div class="eyebrow">Dossiê de Teste · Provocações</div>
    <h1>Verificação em produção das 4 kinds de provocação</h1>
    <p class="dek">Roteiro para reproduzir, na versão web, cada um dos tipos que a aba <b>🎭 Provocações</b> pode gerar hoje — <span class="pill pill-a">absence</span> <span class="pill pill-s">asymmetry</span> <span class="pill pill-p">premise</span> geradas por LLM + validador determinístico, e <span class="pill pill-c">contradiction</span>, uma ponte determinística sem LLM. <code style="font-family:var(--font-mono);color:var(--text-muted);">analogy</code> não existe — avaliada e adiada (PC202).</p>
    <div class="meta-row">
      <span class="tag">pages/Artefatos.py → 🎭 Provocações</span>
      <span class="tag">4 kinds cobertas</span>
      <span class="tag">2 reuniões necessárias</span>
    </div>
    <div class="callout">
      <b>Antes de começar —</b> as 3 kinds geradas por LLM não são determinísticas. O modelo pode não produzir exatamente o esperado, ou produzir com redação diferente — <b>isso é esperado, não é bug.</b> "Zero provocações" é, por design, um resultado válido. Se um passo não gerar o card esperado na primeira tentativa, reprocesse a mesma reunião antes de considerar falha.
    </div>
  </header>

  <section class="step" id="s0">
    <div class="step-head"><span class="step-num">00</span><h2>Pré-requisitos</h2></div>
    <p class="step-sub">Configuração de sessão — feita uma vez, vale para as duas reuniões do roteiro.</p>

    <ul class="checklist">
      <li><input type="checkbox" id="c0-1"><label for="c0-1">Login feito, com um <b>contexto/projeto ativo</b> definido — Home → selecionar ou criar um projeto de teste (ex. <code>Teste Provocações</code>)</label></li>
      <li><input type="checkbox" id="c0-2"><label for="c0-2">Provider de LLM configurado (Settings → chave de API de algum provider)</label></li>
      <li><input type="checkbox" id="c0-3"><label for="c0-3">Em <b>Pipeline → 🆕 Processar Transcrição → ⚙️ Configuração Avançada</b>, ativar <code>🕸️ Grafo de Conhecimento (KH)</code> — padrão já ligado, só conferir</label></li>
      <li><input type="checkbox" id="c0-4"><label for="c0-4">No mesmo painel, conferir que <code>🎭 Gerar Provocações</code> está ativo — <b>ligado por padrão desde o PC205</b> (era desligado por padrão antes disso)</label></li>
    </ul>
  </section>

  <hr class="rule">

  <section class="step" id="s1">
    <div class="step-head"><span class="step-num">01</span><h2>Reunião 1 — absence, asymmetry, premise</h2></div>
    <p class="step-sub">Cole em <b>Pipeline → Nova Transcrição</b>. Título sugerido: <code>Kickoff — Sistema de Gestão de Documentos</code>.</p>

    <div class="transcript">
<pre id="t1"><span class="spk">Renata   0:05</span>
Bom dia a todos. Hoje vamos definir os próximos passos do projeto de gestão de documentos.
<span class="spk">Bruno   0:12</span>
Perfeito. Já temos o escopo alinhado com o time jurídico?
<span class="spk">Renata   0:18</span>
É claro que o time de TI já validou toda a infraestrutura, não precisa nem discutir isso de novo.
<span class="spk">Bruno   0:25</span>
Ok, então podemos seguir. Sobre o Catálogo Mestre, qual vai ser a estrutura?
<span class="spk">Marina   0:33</span>
Mas e se o fornecedor atual não conseguir migrar os dados a tempo? Não vamos ter um risco de indisponibilidade durante a transição?
<span class="spk">Renata   0:41</span>
Vamos ver isso depois. Sobre o cronograma, a entrega está prevista pra março.
<span class="spk">Bruno   0:49</span>
E o orçamento aprovado cobre a licença do novo sistema?
<span class="spk">Renata   0:55</span>
Cobre sim, já está garantido pelo comitê financeiro.
<span class="spk">Bruno   1:03</span>
Ótimo. Então o Catálogo Mestre fica centralizado no Data Center da matriz — essa é a decisão final de hoje.
<span class="spk">Marina   1:10</span>
Fechado então, todo mundo de acordo.</pre>
    </div>
    <button class="copy-btn" data-target="t1">⧉ copiar transcrição</button>

    <p class="design-note"><b>O que foi desenhado pra provocar</b> (não garantido — depende do LLM):</p>
    <ul class="checklist" style="margin-bottom:18px;">
      <li style="cursor:default;"><span class="pill pill-a" style="margin-top:2px;">absence</span><label style="cursor:default;">a reunião é sobre gestão de documentos e nunca menciona plano de contingência, retenção de logs ou auditoria de acesso</label></li>
      <li style="cursor:default;"><span class="pill pill-s" style="margin-top:2px;">asymmetry</span><label style="cursor:default;">objeção da Marina (<span class="highlight-key">0:33</span>) sobre risco de indisponibilidade nunca é retomada antes do fechamento (<span class="highlight-key">1:10</span>)</label></li>
      <li style="cursor:default;"><span class="pill pill-p" style="margin-top:2px;">premise</span><label style="cursor:default;">afirmação da Renata em <span class="highlight-key">0:18</span> ("é claro que… não precisa nem discutir") segue sem contestação</label></li>
    </ul>
    <p class="subnote">Guarde a frase <b>"o Catálogo Mestre fica centralizado no Data Center da matriz"</b> — ela será revertida na Reunião 2, para testar <code>contradiction</code>.</p>

    <h3>Execução</h3>
    <ul class="checklist">
      <li><input type="checkbox" id="c1-1"><label for="c1-1">Processar com <code>🕸️ Grafo de Conhecimento</code> e <code>🎭 Gerar Provocações</code> ativos</label></li>
      <li><input type="checkbox" id="c1-2"><label for="c1-2">Aguardar o pipeline terminar — a barra de progresso deve mostrar "🎭 Gerando provocações…"</label></li>
      <li><input type="checkbox" id="c1-3"><label for="c1-3">Ir em <b>Artefatos → aba 🎭 Provocações</b></label></li>
      <li><input type="checkbox" id="c1-4"><label for="c1-4">Trocar o filtro para <b>"Todas"</b> e confirmar que os cards aparecem</label></li>
    </ul>

    <h3>Validação de cada card</h3>
    <ul class="checklist">
      <li><input type="checkbox" id="c1-5"><label for="c1-5">Tipo mostrado é um de <code>Ausente estrutural</code> / <code>Assimetria discursiva</code> / <code>Premissa não examinada</code></label></li>
      <li><input type="checkbox" id="c1-6"><label for="c1-6">Confiança aparece como <code>high</code> ou <code>medium</code> — nunca <code>low</code></label></li>
      <li><input type="checkbox" id="c1-7"><label for="c1-7">Card tem "Lastro" visível: citação(ões) com timestamp + falante, e (absence/asymmetry) lista de termos, ou (premise) marcador identificado</label></li>
      <li><input type="checkbox" id="c1-8"><label for="c1-8">As citações no Lastro batem <b>literalmente</b> com falas reais da transcrição — não paráfrase</label></li>
      <li><input type="checkbox" id="c1-9"><label for="c1-9">Botões "✅ Aceitar" e "🗑️ Descartar" aparecem (status "Nova")</label></li>
      <li><input type="checkbox" id="c1-10"><label for="c1-10">"✅ Aceitar" → toast de confirmação → card sai de "Novas" e aparece em "Aceitas"</label></li>
      <li><input type="checkbox" id="c1-11"><label for="c1-11">"🗑️ Descartar" em outro card → mesmo comportamento, aparece em "Descartadas"</label></li>
      <li><input type="checkbox" id="c1-12"><label for="c1-12">Trocar de aba e voltar → status persiste (não reverte para "Nova")</label></li>
    </ul>
    <p class="subnote"><b>Se nada foi gerado:</b> reprocesse a mesma reunião (Pipeline → reunião existente → rerun) antes de considerar falha — comportamento esperado quando o LLM não encontra evidência forte o bastante.</p>
  </section>

  <hr class="rule">

  <section class="step" id="s2">
    <div class="step-head"><span class="step-num">02</span><h2>Reunião 2 — contradiction</h2></div>
    <p class="step-sub">Mesmo projeto/contexto da Reunião 1. Título sugerido: <code>Revisão de Arquitetura — Sistema de Gestão de Documentos</code>.</p>

    <div class="transcript">
<pre id="t2"><span class="spk">Bruno   0:04</span>
Precisamos revisar uma decisão da última reunião sobre a infraestrutura.
<span class="spk">Renata   0:10</span>
Isso, revisamos com o time financeiro. O Catálogo Mestre não vai mais ficar no Data Center da matriz.
<span class="spk">Bruno   0:17</span>
E qual é a nova decisão?
<span class="spk">Renata   0:21</span>
Vamos migrar para a nuvem da SE Suíte, por questão de custo operacional. Essa decisão substitui a anterior.
<span class="spk">Marina   0:30</span>
Faz sentido, o custo de manter o Data Center próprio é bem maior mesmo.
<span class="spk">Bruno   0:36</span>
Combinado então, seguimos com a SE Suíte.</pre>
    </div>
    <button class="copy-btn" data-target="t2">⧉ copiar transcrição</button>

    <h3>Execução</h3>
    <ul class="checklist">
      <li><input type="checkbox" id="c2-1"><label for="c2-1">Processar como <b>nova transcrição, mesmo projeto</b> — não é reprocessamento da Reunião 1</label></li>
      <li><input type="checkbox" id="c2-2"><label for="c2-2"><code>🕸️ Grafo de Conhecimento</code> e <code>🎭 Gerar Provocações</code> ativos nos dois — sem o primeiro não há dado pra comparar</label></li>
      <li><input type="checkbox" id="c2-3"><label for="c2-3">Aguardar o pipeline terminar</label></li>
      <li><input type="checkbox" id="c2-4"><label for="c2-4">Artefatos → aba 🎭 Provocações → filtro "Todas"</label></li>
    </ul>

    <h3>Validação</h3>
    <ul class="checklist">
      <li><input type="checkbox" id="c2-5"><label for="c2-5">Card novo com tipo <span class="pill pill-c">Contradição no tempo</span></label></li>
      <li><input type="checkbox" id="c2-6"><label for="c2-6">O Lastro mostra "contradição entre Reunião 1 e Reunião 2" (números reais das suas reuniões) — referência às duas reuniões, não citação de transcrição</label></li>
      <li><input type="checkbox" id="c2-7"><label for="c2-7">Mostra o <code>relation_type</code> — ex. <code>superseded</code> ou <code>contradiction_direct</code></label></li>
      <li><input type="checkbox" id="c2-8"><label for="c2-8">Se houver sugestão de reescrita, aparece como "💡 Sugestão de reescrita: …"</label></li>
      <li><input type="checkbox" id="c2-9"><label for="c2-9">Card aceita/descarta normalmente, mesmo fluxo do passo anterior</label></li>
    </ul>
    <p class="subnote"><b>Se não aparecer</b>, o achado depende de duas etapas fora do validador determinístico: (1) <code>AgentKnowledgeExtractor</code> ter extraído os fatos das duas reuniões de forma comparável, (2) <code>AgentContradictionDetector</code> ter classificado com um <code>relation_type</code> aceito e severidade <code>medium+</code>. Antes de reportar bug: confira <b>Knowledge Hub → ⚠️ Contradições</b> — se a contradição aparece lá mas não em Provocações, é a ponte que falhou (bug real); se não aparece nem lá, foi a extração/comparação do LLM que não pegou (rodar de novo).</p>
  </section>

  <hr class="rule">

  <section class="step" id="s3">
    <div class="step-head"><span class="step-num">03</span><h2>Casos extras</h2></div>
    <p class="step-sub">Opcional, mas recomendado — cobre os cantos que os dois passos acima não tocam.</p>

    <ul class="checklist">
      <li><input type="checkbox" id="c3-1"><label for="c3-1">Projeto sem nenhuma reunião processada com o recurso ativo → aba mostra mensagem verde "Nenhuma provocação gerada ainda…" — não erro, não tela em branco</label></li>
      <li><input type="checkbox" id="c3-2"><label for="c3-2">Reprocessar a Reunião 1 do zero → provocações de <code>contradiction</code> já persistidas não duplicam (dedup por <code>source_contradiction_id</code>)</label></li>
      <li><input type="checkbox" id="c3-3"><label for="c3-3">Alternar entre os 4 filtros (Novas/Aceitas/Descartadas/Todas) com dados nos 3 estados — cada um mostra só o que deveria</label></li>
      <li><input type="checkbox" id="c3-4"><label for="c3-4">Card de provocação já aceita/descartada não mostra mais os botões de ação</label></li>
    </ul>
  </section>

  <hr class="rule">

  <section class="step" id="s4">
    <div class="step-head"><span class="step-num">04</span><h2>Onde reportar o que achar</h2></div>

    <ul class="checklist">
      <li style="cursor:default;"><span style="width:18px;flex:0 0 18px;text-align:center;color:var(--text-faint);">→</span><label style="cursor:default;"><b>Card não aparece onde deveria, mas o dado existe no banco</b> — ex. contradição existe em Knowledge Hub mas não em Provocações — bug real na ponte (<code>bridge_contradictions</code>/<code>save_provocations</code>)</label></li>
      <li style="cursor:default;"><span style="width:18px;flex:0 0 18px;text-align:center;color:var(--text-faint);">→</span><label style="cursor:default;"><b>Citação no Lastro não bate com a transcrição real</b> — bug crítico no validador determinístico (<code>_validate_and_rank</code>) — não deveria ser possível, é a garantia central do recurso</label></li>
      <li style="cursor:default;"><span style="width:18px;flex:0 0 18px;text-align:center;color:var(--text-faint);">→</span><label style="cursor:default;"><b>Zero provocações mesmo em texto óbvio, repetidas vezes</b> — não é necessariamente bug (LLM pode ser conservador), mas vale registrar o texto usado para eu analisar o prompt</label></li>
    </ul>
  </section>

  <footer>Process2Diagram / Vichāra — Provocações PC190·PC200·PC201·PC202</footer>

</div>

<script>
(function(){
  var STORAGE_KEY = "p2d-provocacoes-test-plan-v1";
  var boxes = Array.prototype.slice.call(document.querySelectorAll('.checklist input[type="checkbox"]'));

  function load(){
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"); }
    catch(e){ return {}; }
  }
  function save(state){
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch(e){}
  }
  function updateRail(){
    var total = boxes.length;
    var checked = boxes.filter(function(b){ return b.checked; }).length;
    var pct = total ? Math.round((checked/total)*100) : 0;
    document.getElementById("railFill").style.width = pct + "%";
    document.getElementById("railCount").textContent = checked + " / " + total;
  }

  var state = load();
  boxes.forEach(function(b){
    if (state[b.id]) b.checked = true;
    if (b.checked) b.closest("li").classList.add("checked");
    b.addEventListener("change", function(){
      var st = load();
      st[b.id] = b.checked;
      save(st);
      b.closest("li").classList.toggle("checked", b.checked);
      updateRail();
    });
  });
  updateRail();

  document.querySelectorAll(".copy-btn").forEach(function(btn){
    btn.addEventListener("click", function(){
      var pre = document.getElementById(btn.getAttribute("data-target"));
      var text = pre.innerText;
      var done = function(){
        var original = btn.textContent;
        btn.textContent = "✓ copiado";
        btn.classList.add("done");
        setTimeout(function(){
          btn.textContent = original;
          btn.classList.remove("done");
        }, 1600);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done).catch(function(){
          fallbackCopy(text); done();
        });
      } else {
        fallbackCopy(text); done();
      }
    });
  });
  function fallbackCopy(text){
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch(e){}
    document.body.removeChild(ta);
  }
})();
</script>

</html>
"""

st.components.v1.html(_guide_html, height=2600, scrolling=True)
