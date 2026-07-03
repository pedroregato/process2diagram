# Roteiro de Respostas — Reunião com Fernando Engelmann (CTO) e Fernando Camargo (CPO), SoftExpert

**Objetivo da reunião:** apresentar o Process2Diagram, gerar interesse em uma parceria (integração, licenciamento ou co-venda com o SE Suite), sem expor arquitetura técnica proprietária. Qualquer aprofundamento técnico real só ocorre após NDA assinado.

**Antes de começar:** se possível, envie o NDA (documento em anexo) já na confirmação do horário, com uma frase simples: *"Vou levar alguns detalhes técnicos da solução — te mando um NDA simples de 1 página só para deixarmos isso formalizado antes, tudo bem?"*

---

## Estrutura sugerida da conversa (15-20 min)

1. Contexto e dor de mercado (slides 1-2) — 3 min
2. Demonstração de valor / outputs reais (slides 3-4, prompt-box) — 5 min
3. Visão de arquitetura em alto nível (slide 5 — **pare aqui** se não houver NDA) — 3 min
4. Diferencial vs. abordagens de resumo (Fathom etc.) — 2 min
5. Proposta de conversa: qual formato de parceria interessa a eles — 5 min

---

## Perguntas prováveis e respostas sugeridas

### "Como funciona por trás dos panos? Qual a stack?"
**Responder (nível seguro):** "É uma pipeline multiagente: cada agente é especializado em um artefato — BPMN, ata, requisitos, SBVR, BMM, DMN — e eles rodam em paralelo com fallback entre 8 provedores de LLM diferentes, o que nos dá resiliência e controle de custo. A parte de como cada agente é orientado e como fazemos a validação automática de qualidade é onde está nosso diferencial, então prefiro entrar nesse nível de detalhe com um NDA em vigor."

### "Vocês usam RAG? Como é o pipeline de ingestão?"
**Responder:** "Sim, há uma camada de grafo de conhecimento e RAG que acumula contexto entre reuniões — é o que permite o assistente responder coisas como 'como esse requisito evoluiu entre reuniões'. A arquitetura de ingestão específica é parte do que protegemos como segredo comercial."

### "Como vocês garantem qualidade do BPMN gerado? Isso não é sabidamente difícil com LLM?"
**Responder (pode ser mais aberto aqui — é diferencial de produto, não de implementação):** "Exatamente, é o principal desafio do mercado. Temos um sistema de validação determinística — sem LLM — que audita cada diagrama contra as regras formais da notação BPMN 2.0 antes de entregar, com métricas de qualidade visíveis na interface. Isso é uma das razões pelas quais conseguimos formalismo de verdade, não só 'BPMN aproximado'." *(Isso é posicionamento de valor, não a heurística em si — está OK compartilhar neste nível.)*

### "Isso é só um wrapper de prompt engineering em cima de um modelo, certo?"
**Responder:** "Prompt é uma parte pequena do sistema. A maior parte do trabalho é orquestração determinística — validação, auto-correção, controle de qualidade por agente — que não depende do modelo generativo estar 'inspirado'. É isso que torna o output confiável o suficiente para virar artefato de governança, e não um resumo bonito."

### "Vocês têm código proprietário registrado? Patente?"
**Responder:** "Software não é patenteável no Brasil, então a proteção é por direito autoral (registro no INPI) combinado com segredo comercial para a lógica de orquestração e os prompts. [Se já tiver registrado:] Já temos o registro em andamento/concluído no INPI."

### "Qual o modelo de negócio hoje? Quantos clientes?"
**Responder com o que for real e confortável de compartilhar** — números de tração são normalmente OK de compartilhar em nível agregado (ex: "X clientes em piloto", "modelo SaaS por reunião processada") sem abrir contratos específicos.

### "Podemos ver o código / repositório?"
**Responder:** "Prefiro manter o código fechado nesta fase — mas posso fazer uma demonstração ao vivo do produto funcionando, o que acho que é mais relevante para avaliar o valor do que o código em si."

### "Vocês pensariam em ser adquiridos / eu poderia contratar você?"
**Responder:** "Estou aberto a conversar sobre os formatos que fizerem sentido para os dois lados — hoje meu foco é em [licenciamento/parceria de integração/o que fizer sentido para você]. Podemos explorar isso com mais detalhe se houver interesse real dos dois lados."

---

## Sinais de alerta para redirecionar educadamente

Se a conversa migrar para pedidos específicos de:
- Ver o código-fonte ou repositório
- Detalhar o conteúdo exato dos prompts de sistema
- Explicar a heurística exata de auto-repair / validação
- Compartilhar a arquitetura de dados (schemas, tabelas)

→ Resposta padrão: **"Essa é a camada que protegemos como segredo comercial — posso aprofundar assim que tivermos o NDA assinado e uma conversa mais estruturada sobre o formato de parceria."**

Isso não fecha a porta — comunica profissionalismo e proteção de IP, o que joga a favor da sua credibilidade numa negociação com uma empresa que também protege a própria PI.

---

## Depois da reunião

- Envie um resumo por escrito (email) do que foi discutido e dos próximos passos combinados — cria registro e evita ambiguidade sobre o que foi ou não compartilhado.
- Não envie nenhum material adicional (deck técnico, exemplos de prompt, documentação de arquitetura) sem o NDA assinado primeiro.
