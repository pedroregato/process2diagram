# pages/Orientacoes_CacheSemantico.py
# ─────────────────────────────────────────────────────────────────────────────
# Guia do Cache LLM ("Cache Semântico") — Ajuda
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
<title>Guia do Cache LLM</title>
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
  .arch .bad { color: #f87171; }

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

  /* ── Comparison table ── */
  table.cmp { width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 0.88rem; }
  table.cmp th, table.cmp td { padding: 10px 14px; border-bottom: 1px solid #1e3a5f; text-align: left; }
  table.cmp th { color: var(--amber); font-weight: 600; }
  table.cmp td { color: var(--text); }
  table.cmp td.sub { color: var(--sub); }
</style>
</head>
<body>

<!-- ── Hero ── -->
<div class="hero">
  <h1>🗄️ <span>Cache LLM</span> — o que é e como o P2D usa</h1>
  <p>Por que reprocessar a mesma reunião não deveria custar duas vezes, o mecanismo real por trás disso, e a decisão de engenharia (PC185) de não usar similaridade de embedding.</p>
</div>

<!-- ── TOC ── -->
<div class="toc">
  <h3>Neste guia</h3>
  <a data-target="s1" href="javascript:void(0)">1. O conceito: cache semântico de LLM</a>
  <a data-target="s2" href="javascript:void(0)">2. O que o P2D implementa de verdade</a>
  <a data-target="s3" href="javascript:void(0)">3. Como funciona na arquitetura</a>
  <a data-target="s4" href="javascript:void(0)">4. Segurança entre sessões (PII)</a>
  <a data-target="s5" href="javascript:void(0)">5. Por que não fuzzy matching por embedding? (PC185)</a>
  <a data-target="s6" href="javascript:void(0)">6. Onde ver as estatísticas</a>
  <a data-target="s7" href="javascript:void(0)">7. Perguntas frequentes</a>
</div>

<!-- ── 1. Conceito ── -->
<div class="section" id="s1">
  <h2>1. O conceito: cache semântico de LLM</h2>
  <p>Toda chamada a um provider de LLM (DeepSeek, Claude, OpenAI...) tem custo em tokens e latência. Um <strong>cache de respostas LLM</strong> guarda o resultado de uma chamada anterior para reaproveitá-lo quando a mesma pergunta aparecer de novo — evitando pagar (em dinheiro e em tempo) pela mesma resposta duas vezes.</p>
  <p>Existem duas famílias de implementação, com garantias bem diferentes:</p>

  <table class="cmp">
    <tr><th></th><th>Cache exato (hash)</th><th>Cache semântico (embedding)</th></tr>
    <tr><td><strong>Critério de match</strong></td><td>Prompt idêntico byte-a-byte (ou normalizado) → mesmo hash</td><td>Prompt <em>similar o suficiente</em> por distância vetorial (ex: cosine ≥ 0.98)</td></tr>
    <tr><td><strong>Custo por chamada</strong></td><td>Nenhum — cálculo de hash é local, instantâneo</td><td>1 chamada de embedding extra em <em>toda</em> consulta ao cache (hit ou miss)</td></tr>
    <tr><td><strong>Risco de falso positivo</strong></td><td class="sub">Praticamente zero — só reaproveita quando a entrada é (quase) idêntica</td><td class="sub">Real — dois prompts diferentes podem ficar "parecidos o suficiente" e devolver a resposta errada</td></tr>
    <tr><td><strong>Cobre reformulação de texto</strong></td><td class="sub">Não — qualquer mudança de conteúdo é um miss</td><td class="sub">Sim — essa é a vantagem principal</td></tr>
  </table>

  <div class="tip"><strong>Por que a distinção importa aqui:</strong> o nome "cache semântico" é frequentemente usado (inclusive no módulo interno do P2D, por herança de nome) para qualquer cache de LLM — mesmo quando a implementação real é por hash exato, não por similaridade. Este guia é explícito sobre qual dos dois o P2D usa hoje. Ver seção 5 para a decisão de não adotar o segundo.</div>
</div>

<hr>

<!-- ── 2. O que o P2D implementa ── -->
<div class="section" id="s2">
  <h2>2. O que o P2D implementa de verdade</h2>
  <p>O Process2Diagram usa <strong>cache exato por hash SHA-256</strong> — não embedding. O módulo é <code>services/semantic_cache.py</code> (tabela Supabase <code>llm_cache</code>), plugado dentro de <code>BaseAgent._call_llm()</code>, o ponto único por onde <em>todo</em> agente do pipeline chama um LLM.</p>

  <div class="card-grid">
    <div class="card">
      <div class="icon">🔑</div>
      <h4>Chave: hash de 4 partes</h4>
      <p><code>SHA256(provedor | modelo | system_prompt | user_prompt_sanitizado)</code>. Trocar de provider, modelo ou qualquer parte do texto muda o hash.</p>
    </div>
    <div class="card">
      <div class="icon">🧹</div>
      <h4>Normalização de whitespace (PC185)</h4>
      <p>Espaços/tabs/quebras de linha extras são colapsados antes do hash — reenviar a mesma transcrição com formatação levemente diferente ainda é um hit. Conteúdo real diferente nunca é.</p>
    </div>
    <div class="card">
      <div class="icon">🌐</div>
      <h4>Global, todos os agentes</h4>
      <p>Não é exclusivo de BPMN ou ata — Minutes, Requirements, SBVR, BMM, Synthesizer, Quality... qualquer chamada via <code>_call_llm()</code> passa pelo cache automaticamente.</p>
    </div>
    <div class="card">
      <div class="icon">🔒</div>
      <h4>PII-safe por design</h4>
      <p>O que é cacheado é a resposta <em>pré-desanitização</em> (com tokens <code>@CPF_001</code> no lugar de dados reais) — nunca dados pessoais em texto puro. Detalhes na seção 4.</p>
    </div>
  </div>

  <p>Duas exceções deliberadas onde o cache é <strong>ignorado</strong> mesmo em caso de hit:</p>
  <ul class="steps">
    <li>
      <div class="step-num">🏆</div>
      <div class="step-body">
        <strong>Torneio de BPMN (<code>n_bpmn_runs &gt; 1</code>)</strong>
        <span>Cada tentativa do torneio de validação precisa de uma geração independente — reaproveitar a mesma resposta cacheada 3x anularia a diversidade que o torneio existe para comparar. Flag <code>_lg_skip_cache=True</code>.</span>
      </div>
    </li>
    <li>
      <div class="step-num">🔁</div>
      <div class="step-body">
        <strong>Rerun manual de um agente</strong>
        <span>Quando você clica em "reprocessar" um agente específico na Central de Artefatos, a intenção é gerar de novo — o cache é pulado de propósito, senão o botão não faria nada.</span>
      </div>
    </li>
  </ul>
</div>

<hr>

<!-- ── 3. Arquitetura ── -->
<div class="section" id="s3">
  <h2>3. Como funciona na arquitetura</h2>
  <p>Toda chamada de qualquer agente do pipeline segue o mesmo caminho, dentro de <code>BaseAgent._call_llm()</code>:</p>

  <div class="arch">
<span class="hl">Agente (BPMN, Ata, Requisitos, SBVR...)</span>
              │
              │  build_prompt(hub) → system + user
              ▼
   <span class="dim">Sanitização PII (Tier 1 + Tier 2)</span>
              │
              ▼
   <span class="hl">hash = SHA256(provider | model | system | user_sanitizado)</span>
   <span class="dim">(whitespace normalizado antes do hash — PC185)</span>
              │
              ▼
      ┌───────────────┐
      │  <span class="ok">llm_cache</span>      │  ── consulta por hash ──►
      └───────┬───────┘
              │
      ┌───────┴────────┐
      │                │
  <span class="ok">HIT</span>              <span class="bad">MISS</span>
      │                │
      │                ▼
      │      chamada real ao provider
      │      (DeepSeek/Claude/OpenAI/...)
      │                │
      │                ▼
      │      grava resposta crua no <span class="ok">llm_cache</span>
      │      (nunca se vazia — evita "envenenar"
      │       o cache com falha transitória)
      │                │
      └───────┬────────┘
              ▼
   <span class="hl">desanitize(resposta, token_map da SESSÃO ATUAL)</span>
              │
              ▼
        Resposta ao agente
  </div>

  <div class="tip"><strong>Custo real de um hit:</strong> zero chamadas de rede ao provider — só uma leitura no Supabase. Não é "uma fração do preço do LLM", é ausência completa da chamada.</div>
</div>

<hr>

<!-- ── 4. Segurança entre sessões ── -->
<div class="section" id="s4">
  <h2>4. Segurança entre sessões (PII)</h2>
  <p>Um cache compartilhado entre reuniões/sessões levanta uma pergunta óbvia: como garantir que dados pessoais de uma reunião não vazem para outra através de uma entrada de cache compartilhada?</p>
  <ul class="steps">
    <li>
      <div class="step-num">1</div>
      <div class="step-body">
        <strong>O que entra no cache é sempre a versão sanitizada</strong>
        <span>CPF, CNPJ, e-mail, telefone, valores monetários e nomes de pessoas são substituídos por tokens (<code>@CPF_001</code>, <code>[PESSOA:XX]</code>) antes de qualquer chamada — inclusive antes do hash e antes de gravar no cache.</span>
      </div>
    </li>
    <li>
      <div class="step-num">2</div>
      <div class="step-body">
        <strong>A restauração usa o mapa da sessão atual, não da sessão que gerou o hit</strong>
        <span><code>desanitize(resposta_cacheada, token_map_da_sessão_atual)</code> — mesmo que duas reuniões diferentes produzam o mesmo hash (texto estruturalmente idêntico, PII diferente), cada uma recupera os próprios dados reais, nunca os da outra.</span>
      </div>
    </li>
  </ul>
  <p>Cobertura completa desse mecanismo (Tier 1 estruturado + Tier 2 nomes, LGPD, auditoria) está em <strong>Início → 🔒 Segurança de Dados</strong>.</p>
</div>

<hr>

<!-- ── 5. Por que não embedding ── -->
<div class="section" id="s5">
  <h2>5. Por que não fuzzy matching por embedding? (PC185)</h2>
  <p>Em 2026-07-15, uma proposta técnica (<code>melhorias/cache-semantico.md</code>) sugeriu evoluir para um cache por similaridade de embedding (pgvector, threshold de similaridade, 2 camadas — roteamento e geração de artefato), inspirada num padrão de mercado (Redis Enterprise semantic cache). A avaliação contra o código real do P2D chegou a duas conclusões:</p>

  <h3>O que já existia cobria a motivação principal</h3>
  <p>O cache por hash exato descrito neste guia já roda exatamente onde a proposta sugeria — só que com uma garantia <em>mais forte</em> (exatidão) do que a proposta assumia. A lacuna real (reenvio de transcrição com formatação levemente diferente) foi fechada com a normalização de whitespace, sem custo de embedding.</p>

  <h3>O custo/risco do embedding não se pagava</h3>
  <div class="card-grid">
    <div class="card">
      <div class="icon">💸</div>
      <h4>Tax em toda chamada</h4>
      <p>Checar o cache por similaridade exige 1 chamada de embedding <em>mesmo quando o resultado é miss</em> — custo e latência adicionados a 100% das gerações, não só às que teriam hit.</p>
    </div>
    <div class="card">
      <div class="icon">⚠️</div>
      <h4>Falso positivo em artefato de negócio</h4>
      <p>Para BPMN e ata, um hit "parecido o suficiente" (ex: threshold 0.985) entregaria o diagrama ou a ata de uma transcrição <em>diferente</em> ao usuário — sem volume real do P2D para calibrar esse número com segurança.</p>
    </div>
  </div>
  <div class="warn"><strong>Sem ganho demonstrado:</strong> não havia (e não há, até a data deste guia) nenhum relato de "reprocessar transcrição quase-idêntica" como problema real de produção — a motivação da proposta era hipotética, não um sintoma observado.</div>

  <p>Decisão registrada com o usuário via pergunta direta entre 4 opções (normalização barata / scaffold de embedding desligado / arquivar sem código / outro) — a normalização foi a escolhida. A proposta original está preservada em <code>melhorias/arquivados/cache-semantico.md</code>, com a avaliação completa documentada no topo do arquivo, caso o padrão de uso mude no futuro e valha reabrir a discussão.</p>
</div>

<hr>

<!-- ── 6. Onde ver estatísticas ── -->
<div class="section" id="s6">
  <h2>6. Onde ver as estatísticas</h2>
  <p>A aba <strong>💾 Cache LLM</strong> em <strong>Qualidade ROI-TR</strong> mostra o estado real do cache:</p>
  <ul class="steps">
    <li>
      <div class="step-num">📊</div>
      <div class="step-body">
        <strong>Entradas, hits totais, tokens economizados e economia estimada (USD)</strong>
        <span>Agregado geral e detalhado por agente.</span>
      </div>
    </li>
    <li>
      <div class="step-num">🗑️</div>
      <div class="step-body">
        <strong>Limpeza seletiva (admin/master)</strong>
        <span>Invalidar o cache de um agente específico ou de todos — útil após mudar um skill/prompt de forma que respostas antigas fiquem obsoletas.</span>
      </div>
    </li>
  </ul>
  <p>Pelo Assistente (chat), a mesma informação está disponível via ferramenta <code>get_cache_stats</code>, e a limpeza via <code>clear_llm_cache()</code> (admin).</p>
</div>

<hr>

<!-- ── 7. FAQ ── -->
<div class="section" id="s7">
  <h2>7. Perguntas frequentes</h2>

  <h3>O cache funciona entre projetos/contextos diferentes?</h3>
  <p>Sim — a chave do cache não inclui projeto/contexto, só provedor+modelo+prompt. Isso é intencional: a segurança não vem de isolar por projeto, vem da sanitização de PII (seção 4) — o texto sanitizado de duas reuniões diferentes só produz o mesmo hash se for estruturalmente idêntico, e mesmo nesse caso cada sessão restaura os próprios dados reais.</p>

  <h3>Um hit de cache conta como uma chamada "real" na telemetria?</h3>
  <p>Não. <code>TelemetryRecord.from_cache</code> marca a chamada como servida pelo cache; ela não entra nas médias de latência/erro de chamadas reais ao provider, mas incrementa <code>hub.meta.cache_hits</code> e <code>tokens_saved</code>.</p>

  <h3>Trocar de provider ou modelo invalida o cache?</h3>
  <p>Não invalida entradas existentes (elas continuam lá, associadas ao provider/modelo antigo), mas uma chamada nova com provider/modelo diferente nunca vai dar hit nelas — o hash muda. Efetivamente, o cache "esquece" o provider antigo por conta própria à medida que o TTL expira.</p>

  <h3>Por que o cache existe mesmo (não é sempre melhor gerar de novo)?</h3>
  <p>Não para qualidade — para custo e latência em reprocessamento. Reabrir a mesma reunião no Pipeline (Modo B) sem mudar nada, ou rodar o pipeline duas vezes por engano, não deveria pagar o preço total do LLM de novo. Onde a resposta precisa ser genuinamente nova (torneio de BPMN, rerun manual), o cache é pulado de propósito — ver seção 2.</p>

  <h3>Isso vira "Cache Semântico" de verdade (embedding) no futuro?</h3>
  <p>Possível, se o padrão de uso mostrar que vale o custo/risco (seção 5). Não está planejado hoje.</p>
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
