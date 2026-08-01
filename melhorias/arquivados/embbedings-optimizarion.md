# FEATURE SPEC: Otimização de Armazenamento pgvector para RAG Cross-Meeting (Matryoshka Embeddings 512-dims)

## 1. Contexto e Objetivo
Para viabilizar a comercialização do Process2Diagram dentro do plano gratuito (Free Tier) do Supabase, precisamos reduzir drasticamente o consumo de armazenamento em disco da tabela de embeddings (`transcript_chunks`). 
Atualmente, utilizamos vetores de 1536 dimensões. O objetivo desta melhoria é implementar Matryoshka Embeddings de 512 dimensões usando o modelo `text-embedding-3-small` da OpenAI (e adaptar os fallbacks/migrações do banco), reduzindo o consumo de armazenamento de vetores em ~66% mantendo a precisão das buscas semânticas entre múltiplas reuniões.

## 2. Arquivos Impactados
- `modules/embeddings.py` (Lógica de geração de embeddings)
- `modules/document_store.py` (Pipeline de ingestão e CRUD de documentos)
- `core/session_state.py` (Definições padrão de providers de embedding)
- `claude_guideline/roadmap.md` (Registro da nova versão/ajuste)

## 3. Plano de Implementação Passo a Passo

### Passo 3.1: Modificação em `modules/embeddings.py`
- Alterar as chamadas da API da OpenAI (`text-embedding-3-small`) para passar explicitamente o parâmetro `dimensions=512`.
- Garantir que as funções `embed_text()`, `embed_batch()` e qualquer wrapper de busca passem a gerar e tratar vetores truncados de 512 posições.
- Adicionar uma verificação/alerta nos fallbacks (Gemini/Grok) para que, se não suportarem truncagem nativa para 512, emitam um aviso ou façam o slice manual das primeiras 512 posições (caso o modelo de fallback permita).

### Passo 3.2: Ajuste de Fallback e Tratamento de Erros
- Ajustar a validação para evitar erros de incompatibilidade caso o banco mude para `vector(512)`.
- Garantir que o pipeline permaneça *fail-open* caso ocorra falha na API de embeddings.

### Passo 3.3: Script SQL de Migração (Para execução manual via direct PostgreSQL)
Gerar uma nota de migração ou string SQL documentada para atualizar o banco de dados:
- Modificar o tipo da coluna de vetor na tabela de chunks para `vector(512)`.
- *Nota:* Se houver dados legados na tabela, eles precisarão ser expurgados ou reindexados, pois o pgvector não permite alterar o tamanho da dimensão de uma coluna contendo dados ativos diretamente sem dar Drop/Recreate na restrição ou tabela.

## 4. Diretrizes Técnicas (Alinhadas ao CLAUDE.md)
- **Não quebrar o Fail-Open:** Se o Supabase estiver fora ou inacessível, o fluxo de retorno de lista vazia ou logs silenciosos deve ser mantido.
- **Padrão de Nomes:** Manter todas as funções Python no padrão atual.
- **Validação de Amostragem:** O arquivo de testes correspondente ao pipeline de ingestão deve continuar passando sem quebras de tamanho de array.

---

### Instrução para o Claude Code:
"Claude, leia a especificação acima e o nosso CLAUDE.md. Implemente as alterações nos arquivos `modules/embeddings.py` e avalie se há reflexos imediatos no `modules/document_store.py`. Me apresente o diff das alterações antes de salvar."