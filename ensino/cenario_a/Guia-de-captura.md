---                                                                                                                                                   
  Guia de Captura — Cenário A (do zero)                                                                                                                 
                                                                                                                                                        
  Fase 1 — Preparação (antes de abrir o Loom)                                                                                                           
                                                                                                                                                          1. Inicie o app                                                 
  streamlit run app.py                                                                                                                                  
  # → http://localhost:8501                                                                                                                                                        
  2. Prepare o ambiente visual                                                                                                                          
  - Navegador em tela cheia (F11)                                                                                                                       
  - Zoom do browser em 90% (Ctrl+- uma vez) — evita scroll dentro das abas                                                                              
  - Sidebar fechada — a maioria das cenas fica melhor sem ela                                                                                           
                                                                                                                                                          3. Faça login                                                                                                                                         
  - Entre com usuário admin no domínio p2d                                                                                                              
  - Confirme que o badge de domínio no header mostra p2d                                                                                                
                                                                  
  4. Crie o contexto no Home (se ainda não existir)                                                                                                     
  - Home → botão "Novo Contexto" → nome: Cenário A — Aprovação de Contratos · sigla: CTRA                                                               
  - Selecione esse contexto como ativo                                                                                                                                                                                                                                                                          
  ---                                                                                                                                                   
  Fase 2 — Rodando o pipeline (Cenas 1 e 2)                       
                                                                                                                                                        
  Cena 1 — Transcrição sendo colada
  - Vá para Pipeline                                                                                                                                      - Selecione modo "Nova transcrição"                             
  - Confirme que todos os agentes estão ativos (sidebar: BPMN, Ata, Requisitos, SBVR, BMM, Síntese)                                                     
  - Cole o texto de ensino/cenario_a/transcricao_cenario_a_aprovacao_contratos.txt                                                                      
  - Capture: tela com o campo preenchido + botão "Processar" visível                                                                                    
                                                                                                                                                          Cena 2 — Pipeline rodando                                                                                                                             
  - Clique "Processar"                                                                                                                                  
  - Capture: barra de progresso com agentes sendo executados (esse momento é rápido — grave em loop ou faça um gif depois no CapCut)                    
                                                                                                                                    
  ▎ Aguarde o pipeline completar antes de continuar.                                                                                                    
                                                                                                                                                          ---                                                                                                                                                   
  Fase 3 — Capturando os resultados (Cenas 3 a 6)                                                                                                       
                                                                                                                                                        
  Cena 3 — BPMN (a mais impactante do vídeo)
  - Aba BPMN no Pipeline                                                                                                                                
  - O diagrama deve mostrar 4 raias: Compras / Jurídico / Comitê Executivo / TI                                                                         
  - Se o gateway "Avaliar Valor" aparecer com os labels < R$ 500 mil / ≥ R$ 500 mil, está perfeito                                                      
  - Capture: diagrama centralizado, sem scroll, zoom "fit"                                                                                              
                                                                                                                                                        
  ▎ Se o BPMN gerado estiver mais fraco que o v2.bpmn corrigido: vá em BpmnEditor, importe o arquivo outputs/BPMN_CenarioA_AprovacaoContratos_v2.bpmn e   use essa tela no lugar.                                                                                                                                                                                                                                                                                       
  Cena 4 — Requisitos IEEE 830                                                                                                                          
  - Aba Requisitos                                                
  - Role até aparecerem 3–4 requisitos com a coluna "Origem" (citação da fala)                                                                          
  - Capture: tabela com pelo menos um requisito funcional e um não-funcional visíveis
                                                                                                                                                          Cena 5 — SBVR                                                   
  - Aba SBVR                                                                                                                                              - Deve aparecer pelo menos: termo "Contrato de Alto Valor", regra sobre threshold R$ 500 mil, regra sobre cláusula LGPD
  - Capture: termos + primeiras 2 regras na mesma tela                                                                                                  
                                                                                                                                                        
  Cena 6 — Assistente respondendo pergunta cruzada                                                                                                      
  - Vá para Assistente                                                                                                                                    - Digite exatamente:                                                                                                                                  
  Quais decisões foram tomadas sobre aprovação de contratos e quais são os responsáveis por cada action item?                                           
  - Capture: resposta completa com a lista de action items (Fernanda/15 dias, Marina/fim do mês, Rafael/sexta)
                                                                                                                                                        
  Cena 7 — ROI-TR (encerra o vídeo)                                                                                                                     
  - Vá para MeetingROI                                                                                                                                  
  - Selecione a reunião do Cenário A                                                                                                                      - Capture: dashboard com o tipo de reunião classificado e as métricas visíveis                                                                        
                                                                                                                                                          ---                                                                                                                                                   
  Fase 4 — O que reportar de volta
                                                                                                                                                          Depois de rodar o pipeline, me diga:                            
  - Quantas lanes saíram no BPMN e se o gateway apareceu                                                                                                
  - Quantos requisitos foram extraídos                                                                                                                    - Se o SBVR gerou o termo "Contrato de Alto Valor" e a regra do threshold
  - Como ficou a ata (decisões e action items corretos?)                                                                                                
                                                                                                                                                        
  Com isso eu confirmo quais cenas estão prontas para gravar e o que precisa de ajuste antes do Loom.                                                   
                                                                                                                                                        
✻ Sautéed for 1m 15s     