# SKILL: Glossário HTML Interativo

Use este guia para criar um glossário no mesmo modelo do `pedro-lab/metodologia/glossario.html`.
O arquivo final deve ser um único `.html` autocontido, sem dependências externas além do Google Fonts.

---

## Resultado esperado

Um glossário com:
- Header escuro com título, subtítulo e contador de verbetes
- Barra de busca sticky com contagem em tempo real
- Barra de filtros por categoria logo abaixo da busca
- Layout de duas colunas: índice alfabético lateral (sticky) + conteúdo
- Verbetes com coluna esquerda (termo, nome em inglês, tag de categoria) e coluna direita (definição, exemplo, links "Ver também")
- Letras do alfabeto como seções, com heading tipográfico grande e decorativo
- Todo o conteúdo renderizado dinamicamente via JS a partir de um array `ENTRIES`

---

## Fontes

```
Libre Baskerville — serif, para corpo e headings
IBM Plex Mono    — monospace, para labels, tags, código e UI
```

Import obrigatório no `<head>`:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
@import url('https://fonts.googleapis.com/css2?family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&family=IBM+Plex+Mono:wght@300;400&display=swap');
```

---

## Paleta de cores (CSS variables)

```css
:root {
  /* Superfícies — tema claro, papel envelhecido */
  --bg:     #f8f5ef;   /* fundo geral */
  --s1:     #ffffff;   /* superfície primária (sidebar, cards) */
  --s2:     #f0ece2;   /* superfície secundária (hover, inputs) */
  --s3:     #e4ded2;   /* superfície terciária (letter heading) */
  --border: #d4cec0;   /* bordas */
  --ink:    #1e1a12;   /* texto principal e header */
  --muted:  #8a8070;   /* texto secundário */
  --dim:    #b8b0a0;   /* texto muito apagado */

  /* Categorias — uma cor por tag */
  --ai:   #7a4a10;     /* âmbar escuro */
  --dev:  #1a4a7a;     /* azul escuro */
  --met:  #2a6a3a;     /* verde escuro */
  --ux:   #6a1a5a;     /* violeta escuro */
  --gen:  #3a3030;     /* quase preto */

  /* Tipografia */
  --serif: 'Libre Baskerville', Georgia, serif;
  --mono:  'IBM Plex Mono', monospace;
}
```

**Regra das tags:** cada tag tem três variantes de cor derivadas da mesma cor base:
- Fundo: `rgba(R,G,B, .1)`
- Texto: a cor base (`--ai`, `--dev`, etc.)
- Borda: `rgba(R,G,B, .2)`

---

## Estrutura HTML

```
<header>           ← fundo escuro (var(--ink)), padding 52px 64px
<div.search-bar>   ← sticky top:0, z-index:100
<div.filters>      ← barra de filtros
<div.layout>       ← grid 200px 1fr
  <nav>            ← índice alfabético, sticky
  <div.content>    ← verbetes renderizados pelo JS
```

### Header

```html
<header>
  <div class="h-label">NOME-DO-PROJETO · seção</div>
  <h1><span>Glossário</span> de Termos</h1>
  <div class="h-sub">Descrição em uma linha do que este glossário cobre.</div>
  <div class="h-stats">
    <span id="total-count">— verbetes</span>
    <span>N categorias</span>
    <span>versão X.Y</span>
  </div>
</header>
```

Detalhe decorativo obrigatório: a letra inicial do título em tamanho gigante, quase invisível, no canto inferior direito do header:

```css
header::after {
  content: 'G';           /* primeira letra do título */
  position: absolute;
  right: 40px; bottom: -80px;
  font-family: var(--serif);
  font-size: 320px;
  font-weight: 700; font-style: italic;
  color: rgba(255,255,255,.03);
  pointer-events: none;
  line-height: 1;
}
```

### Barra de busca

```html
<div class="search-bar">
  <input class="search-input" id="search" type="text"
    placeholder="Buscar termo..." oninput="buscar()">
  <span class="search-count" id="result-count"></span>
</div>
```

CSS: `position: sticky; top: 0; z-index: 100; background: var(--s1);`

### Barra de filtros

```html
<div class="filters">
  <button class="filter-btn fb-all active" onclick="filtrar('all', this)">Todos</button>
  <!-- um botão por categoria -->
  <button class="filter-btn fb-SLUG" onclick="filtrar('SLUG', this)">Emoji Nome</button>
</div>
```

Botão ativo: `color: #fff; border-color: transparent; background: var(--COR-DA-CATEGORIA);`

### Índice lateral (nav)

Gerado pelo JS — não escrever manualmente. O JS popula com letras A–Z, marcando `.has-entries` apenas nas que têm verbetes. Clique faz scroll suave para a seção.

CSS crítico:
```css
nav {
  position: sticky;
  top: 97px;              /* altura da search-bar + filters */
  height: calc(100vh - 97px);
  overflow-y: auto;
  border-right: 1px solid var(--border);
}
```

### Verbete (entry)

Layout: grid de duas colunas `220px 1fr`.

```
.entry-left                    .entry-right
  .entry-term  (term pt-BR)      .entry-def   (definição com <strong>)
  .entry-en    (term em inglês)  .entry-example (bloco com ::before 'Exemplo:')
  .entry-tag   (tag colorida)    .entry-related (links clicáveis 'Ver também')
```

O `::before` do exemplo:
```css
.entry-example::before {
  content: 'Exemplo: ';
  font-family: var(--mono); font-size: 9.5px;
  letter-spacing: .1em; text-transform: uppercase;
  color: var(--dim); display: block; margin-bottom: 4px;
}
```

---

## Estrutura de dados — array ENTRIES

Cada verbete é um objeto JS com estes campos:

```js
{
  term:    "Nome do Termo",           // string — em português, como aparece no verbete
  en:      "English Name",           // string — nome em inglês/original
  tag:     "dev",                    // string — slug da categoria (ver lista abaixo)
  def:     "Definição com <strong>palavra-chave</strong> destacada.", // HTML permitido
  example: "Frase concreta de uso real.",  // string — opcional, sem HTML
  related: ["Termo A", "Termo B"]    // array de strings — opcional, links cruzados
}
```

### Tags disponíveis (padrão pedro-lab)

| slug  | label           | cor       |
|-------|-----------------|-----------|
| `ai`  | AI & LLM        | `--ai`    |
| `dev` | Desenvolvimento | `--dev`   |
| `met` | Metodologia     | `--met`   |
| `ux`  | UX & Interface  | `--ux`    |
| `gen` | Geral           | `--gen`   |

Para adaptar a outro projeto: mude os slugs, labels e cores em `tagLabel()`, `tagClass()` e nos CSS vars.

### Convenção de definição

- Sempre destacar em `<strong>` a frase-núcleo que define o termo
- Máximo dois `<strong>` por definição
- O exemplo deve ser sempre do contexto real do projeto — não genérico
- `related` deve apontar para termos que **existem no mesmo glossário**

---

## Lógica JavaScript — 4 funções

### `render(entries)`
Recebe o array filtrado, agrupa por letra inicial, cria seções `.letter-section` com heading e verbetes, e reconstrói o índice lateral. Deve limpar o conteúdo anterior antes de renderizar.

### `buscar()`
Lê o valor do input e o filtro ativo. Filtra `ENTRIES` por `term`, `def`, `example` e `related` (todos em lowercase). Chama `render()` com o resultado.

### `filtrar(tag, btn)`
Atualiza `activeFilter`, remove `.active` de todos os botões, adiciona no clicado. Chama `buscar()`.

### `searchTerm(term)`
Preenche o input com o termo, reseta o filtro para 'all', chama `buscar()`, faz scroll para a search-bar. Usada pelos links "Ver também".

### Init
```js
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('total-count').textContent = ENTRIES.length + ' verbetes';
  render(ENTRIES);
});
```

---

## Responsivo

Em telas ≤ 720px:
- `nav` some (`display: none`)
- `.layout` vira coluna única
- `.entry` vira coluna única
- Padding do header e content reduz para 18–20px
- `.search-bar` e `.filters` reduzem padding para 12–18px

```css
@media (max-width: 720px) {
  header, .content { padding-left: 18px; padding-right: 18px; }
  .search-bar, .filters { padding-left: 18px; padding-right: 18px; }
  .layout { grid-template-columns: 1fr; }
  nav { display: none; }
  .entry { grid-template-columns: 1fr; gap: 8px; }
}
```

---

## Como adaptar para outro projeto

1. **Categorias diferentes** — altere os slugs em `tagLabel()`, atualize as CSS vars e as classes `.fb-*` e `.tag-*`
2. **Idioma diferente** — troque `'Buscar termo...'`, `'Ver também:'`, `'Exemplo:'` e o label do nav
3. **Tema escuro** — inverta: `--bg: #0e0d0b`, `--ink: #f8f5ef`, ajuste as cores de superfície
4. **Mais campos no verbete** — adicione ao objeto ENTRIES e renderize no template HTML dentro de `render()`
5. **Título diferente** — mude o `content` do `header::after` para a inicial do novo título

---

## Checklist antes de entregar

- [ ] Fontes carregando (testar offline — se não carregar, Georgia/Courier New como fallback já estão declarados)
- [ ] `header::after` com a letra inicial correta do título
- [ ] `nav` sticky com `top` igual à altura real de `.search-bar` + `.filters` somados
- [ ] Todos os `related` apontam para termos que existem no `ENTRIES`
- [ ] `total-count` atualizado no `DOMContentLoaded`
- [ ] Busca funciona em `term`, `def`, `example` e `related`
- [ ] Filtro de categoria + busca combinados funcionam simultaneamente
- [ ] Responsivo testado em viewport estreito
- [ ] Arquivo é autocontido (um único `.html`, sem arquivos externos além do Google Fonts)
