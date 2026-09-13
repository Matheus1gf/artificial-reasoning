# Cobertura dos itens científicos para revisão de QA

Esta tabela é o registro do desenvolvedor; o integrador só marca o TODO após o aceite independente. “Implementado no escopo” é uma entrega delimitada, não confirmação de uma hipótese científica geral. Evidências: [contratos](SCIENCE_PROTOCOL.md), [resultados](SCIENCE_RESULTS.md), [dossiê observado](SCIENCE_DISCOVERY.md) e [fontes](../../experiments/science/corpus/prior-art.v1.json).

**Aceite do agente QA independente em 09/09/2026:** 34 testes científicos aprovados, após correções e reteste; aceitos F06-01 a F06-07, F08-01 a F08-08 e F10-01 a F10-04 no escopo declarado. Esse é o estado histórico anterior à retomada. Em 12/09, o QA aprovou F06-08 e 40 testes científicos; os estados restantes constam abaixo. A verificação final do fluxo completo do chat pertence ao QA da integração geral.

| Item | Entrega e critério verificável | Limite / estado proposto |
| --- | --- | --- |
| F06-01 | Simulador 1D com estado, ação temporal, massa, aceleração e unidades | Implementado para a primeira família |
| F06-02 | AST dimensional, domínio explícito, energia incluindo trabalho externo | Implementado; não aborda atrito/colisões |
| F06-03 | Integração por ponto médio versus solução analítica, 300 execuções e sensibilidade a passos | Implementado e erro registrado |
| F06-04 | Ajuste de posições com velocidade parcialmente observada, ruído e previsão em tempos não usados | Implementado no modelo polinomial delimitado |
| F06-05 | Busca de somas/produtos, dimensões, paridade opcional e complexidade; dados anônimos e gramática declarada | Implementado sem alegar descoberta universal |
| F06-06 | Duas camadas neurais comparáveis, restrição física explícita, QR, curvas de 4 a 64 exemplos, ruído e limites | Implementado; resultado favorece método tradicional em várias condições |
| F06-07 | Escolher teste por desacordo, executar simulação, registrar refutação, revisar ajuste e persistir resultado do experimento | Implementado na API e relatórios; integração do registro no chat a conferir pelo QA global |
| F06-08 | [Trajetória real TUM, protocolo anterior à pontuação, 24 segmentos, comparadores e portão executável](SCIENCE_MOTION_TRANSFER.md); registro/relatório v7 com 24 hashes | **Aprovado pelo QA em 12/09:** modelo rejeitado frente à realidade; transferência positiva e expansão continuam bloqueadas |
| F08-01 | Equações explícitas de estado, evolução, projeção, observável e classe aprendida | Implementado; nenhuma hipótese de cérebro quântico |
| F08-02 | Estados complexos, operadores, observáveis, evolução e contagens de medição | Implementado em sistemas pequenos |
| F08-03 | Norma, Born, unitariedade, Hermiticidade, referências analíticas e erro numérico | Implementado para sistemas fechados puros |
| F08-04 | Ajuste de frequência, candidatos alternativos, teste de tempo informativo e predição fora dos tempos de treino | Implementado dentro da classe Rx fornecida |
| F08-05 | Ensaio sintético e reanálise de duas experiências humanas publicadas; controle clássico equivalente, 2 parâmetros e 441 candidatos por modelo | Implementado com resultado negativo no modelo restrito; dados agregados não equivalem a nova coleta/replicação humana independente |
| F08-06 | Sonda lógica separada mede sensibilidade indevida à ordem; decisão de não usá-la como implicação | Implementado como resultado negativo delimitado, sem conclusão sobre toda a cognição quântica |
| F08-07 | Medição de custo 1–8 qubits e distinção tamanho ideal/sobrecarga Python | Implementado para o piloto; extrapolação grande não validada |
| F08-08 | Registro de decisão sobre hardware e requisitos para reabrir a hipótese | Concluído como decisão experimental de não integrar por ausência de vantagem demonstrada |
| F10-01 | Problema observado NIST com comparadores e utilidade definida previamente | Implementado; uma condição de utilidade falhou e permanece registrada |
| F10-02 | Corpus versionado real, hashes, procedência, condições, política de uso e campos desconhecidos explícitos | Implementado para ingestão numérica; interpretação metrológica não aprovada |
| F10-03 | Consultas primárias registradas e busca executável no catálogo pelo núcleo | Implementado no alcance declarado; não é revisão sistemática |
| F10-04 | Aprendiz recebe linhas anônimas; relações publicadas e coeficientes ficam fora do ajuste | Implementado para redescoberta controlada, sem teste científico secreto |
| F10-05 | Requisitos de promoção a problemas abertos e condições de refutação documentados | **Pendente:** não foi promovido a um problema aberto antes de satisfazer os requisitos |
| F10-06 | Dossiê com dados, hipótese, método, expressão, comparações, limitações e reprodução | **Aprovado pelo QA em 12/09:** [parecer por agente de IA](SCIENTIFIC_REVIEW_AI.md) autorizado, achados tratados; sem equivalência a revisão humana |
| F10-07 | Reprodução numérica contra coeficientes NIST, resultado negativo preservado | **Parcial:** mesmos dados; faltam medições/dados independentes para replicação científica |

Os pendentes exigem evidência adicional real. Eles não serão marcados com X por gerar um relatório ou por um agente declarar que o modelo está correto. O desenvolvimento e o QA não utilizaram nenhuma conversa pessoal como conjunto científico.
