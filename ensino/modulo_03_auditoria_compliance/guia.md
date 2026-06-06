# Módulo 3 — Auditoria e Compliance

**Duração:** 2 horas
**Pré-requisito:** Módulo 0 concluído

---

## Objetivo

Ao final deste módulo, o participante será capaz de:
- Gerar atas formais com evidências de decisões para auditorias
- Extrair regras de negócio (SBVR) de reuniões jurídicas e de compliance
- Identificar contradições entre reuniões diferentes
- Montar um dossiê de auditoria a partir de múltiplas reuniões

---

## Contexto do Problema

### O custo da documentação ausente

Multas por descumprimento da LGPD chegam a R$ 50 milhões por infração
(Lei 13.709/2018, Art. 52). Além disso, auditorias do TCU, ANS, ANATEL
e outros órgãos reguladores exigem evidências documentadas de que processos
e controles foram implementados e seguidos.

O problema não é a falta de controles — é que os controles existem apenas
na cabeça das pessoas ou em e-mails perdidos. Quando o auditor pergunta
"como vocês garantem que contratos acima de R$ 500k passam pelo CFO?",
a resposta costuma ser: "sempre foi assim" — sem documento comprobatório.

O P2D cria um rastro documental automático de cada reunião relevante.

---

## Cenário — Comitê de Aprovação de Contratos

### Arquivo
`transcricao_03_comite_contratos.txt`

### Contexto
A empresa de saúde HospitalCorp realiza mensalmente um Comitê de Aprovação de
Contratos para revisar contratos acima de R$ 100.000. Nesta reunião, o comitê
analisa um contrato de R$ 2,3 milhões para infraestrutura de cloud, incluindo
as implicações de LGPD para o armazenamento de dados de pacientes em nuvem.

Participantes:
- **Dr. Marcelo Tavares** — CFO (presidente do comitê)
- **Renata Alves** — Diretora de Compliance / LGPD
- **Jorge Pereira** — Diretor Jurídico
- **Simone Castro** — Gerente de Compras

### O que esperar do pipeline

**Ata gerada:**
- Participantes com cargos
- Pauta: análise do contrato de cloud
- Decisões: aprovação condicional com cláusulas LGPD obrigatórias
- Action items: Jurídico deve incluir DPA até sexta-feira; TI deve assinar termo de responsabilidade

**SBVR (Vocabulário e Regras de Negócio):**

Termos esperados:
- Contrato de alto valor: contrato com valor superior a R$ 100.000
- DPA (Data Processing Agreement): acordo de processamento de dados exigido pela LGPD
- Subprocessador: fornecedor que processa dados pessoais em nome da HospitalCorp
- Comitê de Contratos: instância decisória para contratos de alto valor

Regras esperadas:
- "Todo contrato de alto valor deve ser aprovado pelo CFO"
- "Todo subprocessador de dados de saúde deve assinar um DPA antes da vigência do contrato"
- "Contratos com cláusula de compartilhamento internacional de dados requerem análise da Diretoria de Compliance"

**Requisitos gerados:**
- RR: O fornecedor deve assinar o DPA até a data de vigência do contrato
- RNF: Dados de pacientes devem ser armazenados exclusivamente em data centers brasileiros
- RF: Sistema deve permitir auditoria de logs de acesso por 5 anos

### Passo a Passo

1. **Antes de executar:** vá em Configurações e ative também o agente SBVR
2. Cole a transcrição e execute o pipeline
3. Acesse a aba **Ata** — ela pode ser exportada em PDF como evidência para auditores
4. Acesse a aba **Artefatos → SBVR** — as regras geradas servem como base para Policy Management
5. Abra o **Assistente RAG** e pergunte:
   - "Quem aprovou o contrato de cloud?"
   - "Qual é a condição para o contrato entrar em vigor?"
   - "O que o jurídico precisa fazer até quando?"

### Exercício Avançado: Análise de Contradições

Se a sua organização já tiver reuniões anteriores sobre o mesmo tema:
1. Adicione ao mesmo projeto uma reunião mais antiga onde a política era diferente
2. Abra **Artefatos → Contradições** — o sistema deve identificar regras conflitantes
3. Discuta: como o auditor trataria essa contradição? A contradição detectada é real?

### Exercício: Análise Cruzada Documento × Reunião

1. Na aba **Documentos**, faça upload da política interna de contratos da empresa
   (pode ser um documento fictício criado para o exercício)
2. Use a aba **Análise Cruzada** para comparar o documento com a reunião do comitê
3. O **Score de Alinhamento** foi alto ou baixo? O que isso significa?

### Perguntas de Discussão

1. As regras SBVR geradas seriam aceitas pelo seu departamento jurídico como linguagem formal?
2. Qual seria o custo de produzir manualmente ata + regras SBVR + rastreabilidade para cada reunião do comitê?
3. Como você usaria o Assistente para preparar um relatório de auditoria anual?
4. Uma ata gerada por IA tem validade legal? O que precisaria ser feito para torná-la um documento oficial?

---

## Consolidação do Módulo (15 min)

### Dossiê de Auditoria gerado automaticamente

Para cada reunião de comitê, o P2D produz:

```
📁 Dossiê — Reunião do Comitê de Contratos — [Data]
├── 📄 Ata formal (PDF) — participantes, decisões, action items
├── 📖 Vocabulário SBVR — definições dos termos usados
├── 📋 Regras SBVR — políticas formalizadas da reunião
├── 📝 Requisitos de conformidade — obrigações contratuais identificadas
└── 🔍 Rastro de decisão — quem decidiu o quê e quando
```

### O que levar para o trabalho

1. **Gravar comitês e reuniões de compliance** — mesmo que informais
2. **Usar SBVR como linguagem de políticas** — compartilhar com Jurídico e Compliance para validação
3. **Criar projeto por período de auditoria** — todas as reuniões relevantes no mesmo projeto para consulta pelo Assistente
