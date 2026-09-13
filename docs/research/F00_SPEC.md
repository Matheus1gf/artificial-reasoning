# F00 — Especificação operacional

Versão 1, 08/09/2026. Implementa a especificação pedida em F00-01 e F00-03; não afirma que o chatbot já possui as capacidades especificadas. Referências cruzadas: [auditoria](F00_AUDIT.md), [protocolo](F00_PROTOCOL.md), [hipóteses](F00_HYPOTHESES.md), [recursos](F00_RESOURCES.md), [aceite QA](F00_QA.md).

## 1. Capacidades e critérios de falha — F00-01

Uma capacidade é avaliada pela entrada, pelo artefato produzido e por um verificador que não depende de aceitar a prosa do modelo. Um acerto isolado permite afirmar somente que aquele caso foi resolvido.

| Capacidade | Definição operacional | Tarefa observável e evidência necessária | Falha mensurável |
| --- | --- | --- | --- |
| Compreensão | Converter a mensagem e o contexto relevante em intenção, entidades, restrições e pergunta preservando significado | Pares anotados mensagem/contexto → estrutura; trocar apenas entidade, negação, valor ou referência e conferir a mudança correspondente | Estrutura diverge do gabarito; contexto de outra conversa é usado; ambiguidade é preenchida silenciosamente |
| Dedução | Produzir uma conclusão que decorre das premissas e regras declaradas | Compor duas transições observadas; devolver ações e evidências; conferir cada passo independentemente | Passo não sustentado, premissa incompatível, conclusão errada ou orçamento excedido |
| Indução | Ajustar uma regra/modelo reutilizável que prevê casos não usados no ajuste | Ocultar uma relação parametrizada, fornecer experiências, avaliar previsões em novos estados contra memória e modelos simples; arquivar modelo antes/depois | Memoriza entradas; usa regra oculta do gerador; não supera referência prévia no critério registrado; trata modelos indistinguíveis como certeza |
| Analogia | Transferir relações por correspondência de papéis e estrutura, respeitando condições de aplicação | Aprender uma relação em sistema A e prever em B com nomes e atributos superficiais diferentes; incluir correspondências falsas | Transfere por palavra parecida; ignora uma condição quebrada; não identifica a origem da correspondência |
| Criação | Produzir um candidato distinto das experiências anteriores para uma meta especificada | Gerar um plano, programa ou equação ausente dos exemplos; medir diversidade de mecanismos e verificar restrições | Só reescreve um candidato; não atende à meta; apresenta novidade sem escopo ou sem artefato executável |
| Invenção | Criar um mecanismo útil cuja operação é verificada sob condições declaradas | Construir e testar solução contra referência conhecida, custo e perturbações; avaliar trabalhos anteriores antes de alegar novidade científica | Solução não funciona no teste independente; viola condições físicas; melhoria desaparece com custo equivalente; descoberta já conhecida é anunciada como inédita |
| Aprendizado | Uma experiência causa mudança persistente e mensurável no estado do sistema ou em suas capacidades | Comparar versões antes/depois, com intervenção controlada na experiência e dados futuros separados; registrar o nível abaixo | Contar mensagens como evidência de ganho geral; medir nos exemplos memorizados; omitir treino prévio; ganho sem preservar capacidades previamente aceitas |

No instrumento F00, a entrada já é estruturada: **compreensão de português não é medida**. A busca de planos usa uma regra de composição programada; ela fornece um controle para dedução limitada, não um teste conclusivo de indução, analogia, invenção ou raciocínio humano. Essas capacidades permanecem trabalho das próximas fases.

## 2. Quatro níveis de aprendizado — F00-03

| Nível | Mudança e dados que a demonstram | Métricas e desenho de avaliação | Situação inicial |
| --- | --- | --- | --- |
| L1 — Registrar experiência | Novos episódios com ID, fonte, data, contexto e possibilidade de recuperação | Taxa de persistência/recuperação, duplicação, perda após reinício; conferir correspondência com a fonte | Chat implementa mensagens e fontes em SQLite; 57 testes do chat verificam aspectos funcionais, sem provar inteligência |
| L2 — Atualizar crenças | Afirmação, conflito ou correção altera o conjunto de premissas ativas e suas dependências | Acertos após correção, conclusões obsoletas ainda usadas, revisão indevida de contextos diferentes; versões antes/depois | Chat implementa revisão limitada de triplas e invalidação; não calcula credibilidade científica calibrada |
| L3 — Aprender regras/modelos | Experiências alteram um operador, equação ou modelo capaz de prever relações não copiadas dos exemplos | Curva por número de exemplos, erro em combinações/estados novos, comparação com memória e prior fixo, identificação de alternativas compatíveis | Não demonstrado no núcleo do chat. F00 ajusta apenas uma tabela de frequência episódica de diagnóstico; sua pontuação não demonstra aprendizado de operadores gerais |
| L4 — Melhorar estratégias de aprendizagem | Experiência entre tarefas altera como obter exemplos, escolher hipóteses ou ajustar modelos | Ganho por consulta em novas famílias, custo total incluindo metatreino, comparação com estratégia fixa/aleatória e retenção de capacidades | Planejado; não há evidência experimental do chat para este nível |

L1 pode ocorrer sem L2; L2 pode seguir uma regra escrita pelo desenvolvedor sem L3; resolver uma composição com BFS não significa aprender a compor. Uma rede neural só satisfaz L3/L4 se seus dados, mudanças de parâmetros e ganhos reservados forem demonstrados no nível correspondente. Treinamento prévio, regras de biblioteca e exemplos sintéticos de outro modelo contam como experiência/prior, mesmo quando não foram produzidos neste repositório.

## 3. Critério científico e critério de engenharia

- **Entrega F00:** um avaliador reproduzível, especificação auditada, protocolo anterior aos resultados, comparações honestas e hipóteses refutáveis. O aceite depende de QA, não de uma pontuação alta.
- **Progresso de capacidade:** exige experimento posterior, mudança identificável no mecanismo, comparação justa, incerteza e teste ainda não usado no desenvolvimento.
- **Descoberta/invenção científica:** exige utilidade demonstrada, domínio de validade, análise de trabalhos anteriores e verificação independente. Nenhuma medida de F00 permite essa conclusão.
- **Ambição de longo prazo:** a comparação com cientistas excepcionais orienta o objetivo; ainda não define unidade de medida nem multiplicador que possamos anunciar.

As explicações verificáveis serão registros de premissas, operações e verificações. Uma narrativa persuasiva, uma pontuação de confiança arbitrária ou a presença de termos de física/quântica não substitui esse registro.
