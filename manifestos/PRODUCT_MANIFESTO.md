# 🕉️ Manifesto do Produto — Filosofia de Negócio (Vichara / P2D)

> **Versão:** 0.1 — **RASCUNHO, aguardando assinatura do Agente 0**
> **Data:** julho de 2026
> **Arquiteto:** Pedro Regato
> **Classificação:** Diretriz de Filosofia de Negócio — o *porquê* e o *o quê* do produto
> **Complementa:** `COLLABORATIVE_MANIFESTO.md` (quem), `ENGINEERING_MANIFESTO.md` (como), `CONTINUIDADE_ARQUITETURAL.md` (resiliência)

---

> *"Reuniões são o ativo intangível que mais impacto tangível provoca numa corporação."*
> — Pedro Regato, tese fundadora do produto

---

## 0. POR QUE ESTE MANIFESTO EXISTE

Os três manifestos vigentes respondem **como construir e operar** o produto: princípios de
engenharia, governança multi-agente, blindagem contra SPOF. Nenhum responde **o que estamos
construindo e por quê ele importa**.

O `COLLABORATIVE_MANIFESTO` se encerra com uma frase que exige este documento:

> *"A governança não é burocracia. É a estrutura que permite escalar sem perder a alma do produto."*

Este manifesto **é a alma**. Ele existe para que qualquer agente — IA ou humano — que vá tomar uma
decisão de produto (o que gerar, o que priorizar, o que persistir, como nomear, o que integrar)
tome-a a partir da tese certa, e não a partir do nome herdado do repositório.

**Diretriz canônica ao agente:** decisão de *implementação* consulta o `ENGINEERING_MANIFESTO`.
Decisão de *produto* — "isto deveria existir? deveria funcionar assim?" — consulta **este**
documento primeiro. Quando os dois se calam, escale ao Agente 0.

---

## 1. A MÁXIMA E SUAS TRÊS CONSEQUÊNCIAS

A máxima não é slogan. São três afirmações comprimidas, e as três têm consequência de código.

1. **A reunião é onde a decisão acontece.** Ata, especificação, diagrama e backlog são
   *sedimentos* — reconstruções imperfeitas, feitas de memória. A regra de negócio é *enunciada*
   na reunião; em todo o resto ela é apenas *transcrita*.
2. **É o único ativo de valor que a corporação não trata como ativo.** Sem dono, sem versão, sem
   repositório. O custo é tangível: retrabalho, requisito perdido, regra que só reaparece em
   produção, decisão sem rastro de motivação.
3. **Portanto a reunião não é uma entrada dentre outras — é a fonte.** Todo artefato é derivado
   dela.

> **Consequência para quem implementa:** qualquer design que trate a transcrição como "mais um
> input" ao lado de documentos e prints contraria a tese. A reunião é o ativo bruto; o resto do
> sistema são lentes sobre ele.

---

## 2. A TESE SOBRE O DISCURSO — E A DECISÃO DE NÃO SER NEUTRO

Duas proposições sustentam o produto:

- **Leitura foucaultiana** (*paráfrase*, não citação literal — cf. *A Microfísica do Poder*): não
  existe discurso verdadeiro; existem discursos mais ou menos poderosos.
- **George Box:** todos os modelos estão errados, mas alguns são úteis.

Box autoriza o artefato: ninguém precisa do BPMN *verdadeiro* — precisa do BPMN que faz a sala
pensar melhor. Foucault autoriza a intervenção: se o desastre nasce do discurso poderoso que calou
o discurso correto, então **sintetizar sem discriminar é escolher o lado de quem falou mais alto**.

Toda decisão certa e toda decisão desastrosa nasceram de um discurso — convergências, divergências,
imposições, escuta, silêncio. O palco é a reunião. O produto não existe para documentar melhor esse
palco; existe para **elevar o que acontece nele**.

> **Consequência para quem implementa (decisão de produto deliberada):** o produto **não é
> neutro**. Um sumarizador reproduz a assimetria da sala — quem falou mais, aparece mais. O
> sistema deve registrar a divergência atropelada, a premissa não examinada, a objeção sem
> resposta. Isto é uma escolha ética dentro do cliente, e é intencional.

---

## 3. OS ARTEFATOS SÃO ESPELHOS, NÃO ENTREGÁVEIS

Se o produto fosse gerar documentos, o valor terminaria no arquivo. Não termina. O valor está no
que o artefato **torna visível** para quem estava na sala e não viu.

| Artefato | O que ele torna visível |
|---|---|
| Diagrama de processo (BPMN) | Que o fluxo "consensual" tem duas versões incompatíveis na cabeça dos participantes |
| Vocabulário / SBVR | Que a concordância era homonímia — "cliente" significa três coisas na mesma mesa |
| Regras de negócio | Que a exceção citada de passagem invalida a regra aprovada |
| Motivação / BMM | Que a decisão tática não serve ao objetivo declarado |
| Requisitos | Que o combinado não é construível como está |
| Relatório executivo | Que o que chega à liderança não é o que foi debatido |

A reunião tem três naturezas — **estratégica, tática, operacional** — e o artefato pertinente varia
entre elas. Um BPMN raramente serve a um comitê estratégico.

> **Consequência para quem implementa:** **não implementar gating de artefatos por tipo de
> reunião.** Todos os artefatos permanecem disponíveis; o interlocutor humano escolhe qual espelho
> levantar naquele momento. Classificação, se existir, é sinal de ordenação e sugestão — **nunca
> um portão** que decide o que pode ser gerado.

---

## 4. AS DUAS MEMÓRIAS — E A HIERARQUIA QUE JÁ EXISTE NO CÓDIGO

Há **duas memórias**, de naturezas opostas. Confundi-las custa caro.

| | Memória do **contexto** | Memória do **domínio** |
|---|---|---|
| Conteúdo | Todos os artefatos de todas as reuniões | Apenas os **Ativos de Negócio** (promovidos) |
| Formação | **Automática**, por persistência | **Deliberada**, por promoção humana |
| Curadoria | Nenhuma — exaustiva | Total — escassa |
| Alcance | O silo | A corporação |
| Analogia | O que o contexto *viveu* | O que a corporação *aprendeu* |

**A hierarquia não é abstração nova — é o data model atual, com o nome certo:**

| Conceito de produto | Entidade no código | Observação |
|---|---|---|
| **Domínio** (a corporação. Ex.: FGV) | `tenant_id` | `list_all_business_assets_for_domain(tenant_id)` |
| **Contexto** (um silo: SDEA, Projeto Aurora) | `contexts` / `project_id` | O termo `projeto` é herança; o produto diz **contexto** |
| **Artefato** | linha de artefato, escopo do contexto | Persiste automaticamente |
| **Ativo de Negócio** | artefato promovido | Atravessa a fronteira do contexto |

A promoção **não cria memória — estende o alcance** de uma memória que já existia. É o mecanismo
pelo qual o vocabulário estabelecido no SDEA chega ao Projeto Aurora sem que ninguém precise
redescobri-lo.

> **Consequências para quem implementa:**
> - **Persistir é o default; promover é o ato excepcional.** Nunca condicionar persistência a
>   aceitação ou aprovação — descartar artefato não aceito **destrói a memória do contexto**, que é
>   o ativo que o produto existe para constituir.
> - **Nunca vazar artefato não promovido de um contexto para outro.** A fronteira do contexto é a
>   regra; a promoção é a exceção deliberada. Vazamento aqui não é bug de qualidade — é quebra de
>   confidencialidade entre silos (alinhado ao `ENGINEERING_MANIFESTO §5.3`, segregação por tenant).
> - Toda leitura de contexto de entrada resolve `artefatos DO contexto ∪ Ativos de Negócio DO
>   domínio` — nada além.

---

## 5. VICHARA — O ASSISTENTE, A FACULDADE, E A REGRA DO LASTRO

**Vichāra** (विचार, sânscrito): investigação discriminativa — o exame que separa o que se sustenta
do que apenas parece. Nomeia uma **faculdade**, não uma transformação. Por isso é o nome do
**assistente** — e não "process2diagram", que nomeia uma saída (o diagrama) e comete um erro de
categoria ao batizar uma lente como se fosse o objeto.

### 5.1 Convenção de nomenclatura (não violar)

**Nome humanizante é privilégio de quem conversa.** Como um nome indígena descreve seu portador
("Sol do Amanhecer"), *Vichāra* descreve o assistente pelo que ele faz. Ele é a única superfície
que dialoga com um humano.

Todos os demais agentes são maquinaria e recebem **nome funcional** (`AgentProvocations`,
`AgentBPMN`, `AgentMinutes`...). Nenhum tem persona, voz ou primeira pessoa.

> **Diretriz ao agente:** não proponha nomes próprios para agentes de pipeline. Um assistente,
> muitas faculdades. Um artefato gerado assincronamente pode ser **atribuído a Vichara na UI** sem
> que o agente que o produziu tenha nome — é a mesma faculdade em outra superfície.

### 5.2 A discriminação e a regra do lastro

A faculdade discriminativa de Vichara se manifesta em dois registros complementares:

- **Divergências pendentes:** o que ficou *aberto e visível* — objeção nunca respondida, termo
  ainda ambíguo, premissa não testada, decisão tomada com regra irresolvida. Objeto de primeira
  classe, atravessa reuniões.
- **Provocações:** o que ficou *fechado sem ter sido visto* — o ausente estrutural, a contradição
  no tempo, a analogia estrutural que ninguém enxergou.

Ambos obedecem à **regra do lastro**, que é a ética central do produto e não um detalhe de prompt:

> **O sistema não cria conteúdo. Ele aponta para o que já está no material e ninguém olhou.** Toda
> observação carrega evidência verificável: citação + timestamp, ID de Ativo de Negócio, ou
> afirmação de ausência checável. **Sem lastro, não sai.** Isto é validado em código, não confiado
> ao modelo.

A doutrina, na forma que orienta o modelo:

> *O rishi não compôs o mantra — ele o viu. O que já estava lá foi percebido por quem tinha o olho
> para percebê-lo. Você não cria a provocação. Você a vê no material, e a mostra a quem não viu. Se
> não está lá, não existe.*

> **Consequência para quem implementa:** **toda regra de segurança do agente existe em código; o
> prompt é otimização, nunca garantia.** Vale para o lastro, para o limite de volume, para a lista
> negra de tom, para o allowlist de tipos. Se a regra só vive no prompt, ela não existe.

### 5.3 A cautela contra a convergência

Convergência prematura é um mecanismo clássico de decisão desastrosa: a sala converge porque o
discurso mais poderoso calou os outros, e o consenso aparente é o sintoma da falha, não da saúde.

> **Diretriz ao agente:** o produto **não otimiza convergência como valor máximo**. Um sistema que
> só acelera consenso vira uma máquina de *groupthink* com aparência de rigor. A divergência
> pendente tem o mesmo status da convergência. A pauta da próxima reunião prioriza o que ficou
> *aberto e importa*, não o que já convergiu.

---

## 6. O CICLO — DE PONTO A TRAJETÓRIA

Enquanto a reunião for evento isolado, o ativo é um ponto. O produto se completa quando a saída de
uma reunião vira a entrada da próxima.

```
  REUNIÃO (ativo bruto)
     │
     ├─ projeção ────► artefatos (espelhos; o humano escolhe; TODOS persistem no contexto)
     ├─ discriminação► divergências pendentes + provocações (com lastro)
     ├─ configuração► pauta da próxima reunião (prioriza o irresolvido)
     └─ promoção ────► Ativo de Negócio (atravessa a fronteira → memória do domínio)
```

Dois saltos distintos, que não devem ser confundidos:

- **Salto de tempo:** reunião isolada → trajetória (a memória do contexto acumula, automática).
- **Salto de escopo:** contexto → domínio (a promoção, deliberada).

A pauta é o dispositivo de poder mais óbvio da reunião: quem a define determina o que pode ser
dito, em que ordem, com quanto tempo. Produzi-la a partir do que ficou irresolvido é a intervenção
mais barata e mais determinante que o produto pode fazer.

> **Diretriz ao agente:** a intervenção **assíncrona** (entre reuniões) precede a intervenção **em
> tempo real** no roadmap. Entre reuniões, o sistema tem o transcript completo, a memória do
> contexto, os Ativos de Negócio, tempo, e o direito de errar sem plateia — o humano filtra antes
> de levar à mesa. Não antecipar a intervenção ao vivo antes de os alicerces amadurecerem.

---

## 7. A FRONTEIRA COMPETITIVA É A TESE, NÃO A INTEGRAÇÃO

Existem produtos adjacentes que também levam transcrição a artefatos com agentes especializados e
integração a ALM (Jira, Azure DevOps). A diferença **não** é a lista de integrações — integração se
constrói e se copia. A diferença é a tese: para eles a reunião é **insumo**, ao lado de prints e
documentos, e o destino é o backlog. Para nós a reunião é **o ativo**, e o destino é a qualidade da
deliberação.

> **Diretriz ao agente:** integrações (Jira, Camunda, Bizagi, exportações) são consequência
> legítima e vendável, mas são a camada mais rasa e a mais copiável. Não as trate como o núcleo, e
> não deixe que decisões de integração deformem o modelo conceitual das seções 1–6.

*(Nota comercial: nada aqui contradiz o `COLLABORATIVE_MANIFESTO §6`. O VETO a provedores premium
governa o **LLM de runtime** que processa reuniões — decisão de custo. Este manifesto governa a
**tese de produto**. São camadas distintas.)*

---

## 8. HEURÍSTICAS DE DECISÃO — CHECKLIST PARA O AGENTE

Antes de propor qualquer coisa que seja decisão de produto neste repositório:

- [ ] Estou tratando a reunião como **o ativo**, ou como mais um input?
- [ ] Estou privilegiando indevidamente o BPMN por causa do nome do repositório?
- [ ] Estou removendo do humano uma escolha que é dele (qual espelho levantar)?
- [ ] Estou implementando **gating** de artefato por tipo de reunião? (Não fazer.)
- [ ] Estou condicionando **persistência** a aceitação/promoção? (Persistir é o default.)
- [ ] Estou vazando artefato não promovido para fora do seu **contexto**?
- [ ] Estou otimizando convergência sem preservar a **divergência**?
- [ ] O que proponho produz conteúdo **sem lastro** verificável no material?
- [ ] Alguma regra de segurança do agente vive **só no prompt**, e não em código?
- [ ] Estou dando **nome próprio/persona** a um agente de pipeline?
- [ ] Estou confundindo **domínio** (`tenant_id`, a corporação) com **contexto** (`contexts`, o silo)?
- [ ] Estou usando `projeto` onde o termo de produto é **contexto**?
- [ ] Isto antecipa a intervenção **ao vivo** antes dos alicerces?

---

## 9. NOMENCLATURA EM TRANSIÇÃO E RELAÇÃO COM OS DEMAIS MANIFESTOS

**O código ainda é P2D / process2diagram (v5.15).** *Vichara* é a tese, a alma e o nome que vem. A
renomeação global (`p2d` → Vichara; `project_id` → `context_id`) é uma refatoração de risco e
**não deve ser executada sem inventário prévio e sem arbitragem do Agente 0** — exatamente como a
`README §Regras de Versionamento` e a `Regra de Ouro de Edição` exigem. Até lá, o agente trata o
nome do repositório como etiqueta histórica e **esta tese** como fonte de verdade sobre escopo.

| Camada | Manifesto | Pergunta que responde |
|---|---|---|
| **Alma** | **Este documento** | O que estamos construindo e por quê |
| Quem | `COLLABORATIVE_MANIFESTO` | Quem decide, quem executa, quem paga |
| Como | `ENGINEERING_MANIFESTO` | Como construir com rigor e segurança |
| Resiliência | `CONTINUIDADE_ARQUITETURAL` | Como não parar quando um ponto falha |

Este manifesto é **aditivo**: não altera nem remove nenhuma regra dos demais. Onde toca o modelo de
dados (domínio/contexto), ele **nomeia** o que já existe (`tenant_id` / `contexts`), não o
substitui.

---

## 10. ASSINATURA

| Papel | Função | Assinatura | Data |
|---|---|---|---|
| Agente 0 | Arquiteto | _[pendente — este documento aguarda ratificação]_ | — |

> **Estado:** RASCUNHO v0.1. Ao ratificar, o Agente 0 deve: (1) assinar acima; (2) bumpar para
> v1.0; (3) registrar o PC correspondente em `memory/project_state.md`; (4) adicionar este arquivo
> à ordem de leitura obrigatória do `README.md` e à tabela de memória do `ENGINEERING_MANIFESTO §8`.

---

> *"O problema nunca foi documentar melhor as reuniões. Era fazer reuniões melhores.
> Documentação é o meio."*
> 
> 