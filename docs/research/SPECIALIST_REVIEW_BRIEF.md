# Briefing para revisão especializada

Briefing usado para orientar a revisão especializada. Em 12/09/2026, o usuário autorizou a criação de um agente especialista independente dos autores. O agente `scientific_reviewer` recebeu os materiais e os critérios abaixo; seu parecer deve ser identificado como revisão por IA. Este briefing não é o parecer e não representa agendamento ou envio a pessoas externas.

**Revisão realizada:** o [parecer científico independente por IA](SCIENTIFIC_REVIEW_AI.md) registra os recálculos, fontes verificadas, achados, ações e conclusões de utilidade e novidade. O QA confere as correções antes de marcar os requisitos correspondentes.

## Materiais para o avaliador

- [Protocolo e pressupostos científicos](SCIENCE_PROTOCOL.md), [resultados completos](SCIENCE_RESULTS.md) e [dossiê NIST](SCIENCE_DISCOVERY.md).
- [Estado científico por requisito](SCIENCE_STATUS.md), [matriz de testes independentes de software](F01_F11_QA.md) e dados/registro em `experiments/science/`.
- [Arquitetura própria](../CHATBOT_ARCHITECTURE.md), memória, aprendizado e [estimativas de esforço](MEMORY_LEARNING_OPERATIONS.md).
- Corpus, arquitetura, pesos e métricas de compreensão em `experiments/cognition/`.
- [Transferência para trajetória medida](SCIENCE_MOTION_TRANSFER.md), incluindo fonte TUM, protocolo temporal, comparadores e resultado negativo.

## Perguntas e competências necessárias

| Especialidade | Questões a responder | Entregável esperado |
| --- | --- | --- |
| Física experimental/metrologia | O domínio 1D e as incertezas são adequados aos dados? O comparador de transferência usa condições equivalentes? Há viés de seleção? | Parecer com condições de validade, contraprova sugerida e dados adicionais necessários |
| Mecânica quântica/modelagem cognitiva | Evolução, medição e hipóteses estão corretamente definidos? O controle clássico tem capacidade/orçamento apropriados? O recorte contextual permite as conclusões negativas relatadas? | Reprodução de pelo menos um caso positivo e um negativo; correções de interpretação |
| Estatística/ML | Treino e avaliação estão separados? O orçamento total de experiência é declarado? O ganho persiste entre sementes e famílias? Há justificativa para adotar componentes neurais? | Auditoria de vazamento, comparadores e incerteza, sem tratar treino perfeito como generalização |
| Lógica/verificação | As provas, condições causais e planos verificam o que dizem verificar? Uma hipótese pode chegar ao texto como certeza? | Caso adverso e resultado de execução independente |
| Especialista no problema de descoberta | A proposta tem utilidade frente a trabalhos anteriores? A busca de novidade tem alcance suficiente? Qual observação a refutaria? | Parecer de novidade/utilidade e protocolo de replicação independente |

## Procedimento proposto

O avaliador declara participação no projeto/conflitos e as limitações de sua revisão. O agente escolhido nesta execução não participou da implementação e recebeu a tarefa sem herdar o histórico dos desenvolvedores. Isso proporciona separação de autoria, mas não independência de plataforma ou modelo de IA. Para novidade e utilidade, o mascaramento da origem é desejável quando viável; a revisão com acesso ao repositório não pode ser descrita como cega. Resultados completos, inclusive falhas, devem ficar acessíveis antes do parecer final.

Cada parecer deve identificar sua versão de dados/código, pressupostos aceitos/rejeitados e o que foi reproduzido. Falhas voltam ao desenvolvedor e ao QA; mudanças de protocolo geram versão nova, sem apagar resultados anteriores. Nenhum checklist marcado substitui medição independente. Tempo estimado inicial de parecer: 4–8 horas por especialidade e pacote pequeno, sujeito à disponibilidade e ao escopo acordado.

O escopo autorizado é a revisão por agente de IA dos artefatos do projeto e das fontes públicas. Nenhum histórico pessoal foi incluído. Revisão humana por pares e replicação empírica externa continuam sendo evidências distintas, que este parecer não substitui.
