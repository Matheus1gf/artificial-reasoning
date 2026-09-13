# Resultados dos pilotos científicos

Atualizado em 12/09/2026, Python 3.9.6, computador local. Relatório atual: [pilot.v7.json](../../experiments/science/results/pilot.v7.json), com [registro de hashes v7](../../experiments/science/registration.v7.json). Duração desta execução: **4,06 s**, sem Qwen, API paga ou hardware quântico. Seus 24 hashes foram conferidos pelo QA contra o registro e os arquivos. O tempo é uma observação local e varia com a carga do computador. Os resultados anteriores, incluindo v5 (3,78 s), permanecem preservados; a retomada acrescentou a avaliação física medida e corrigiu sua integração no chat.

## Física e modelos aprendidos

Foram executadas 100 condições independentes de movimento, em cinco sementes, cada uma com 1, 16 e 128 passos. O maior desvio de posição/velocidade frente à fórmula analítica foi aproximadamente **7,2×10⁻¹⁴**. O balanço inclui trabalho externo; nenhuma conservação indevida de energia cinética é imposta.

Os ajustes recebem oito posições entre 0 e 1,4 s e predizem posições em 1,6, 1,8 e 2 s. A velocidade é uma variável não observada diretamente, estimada a partir das posições. Os resultados abaixo são médias dos erros por semente, com intervalo bootstrap exploratório entre cinco sementes:

| Desvio do ruído nas posições | RMSE médio de previsão | Intervalo bootstrap de 95% |
| --- | --- | --- |
| 0 m | 2,10×10⁻¹⁵ m | 1,81×10⁻¹⁵ a 2,40×10⁻¹⁵ m |
| 0,01 m | 0,01676 m | 0,01573 a 0,01789 m |
| 0,05 m | 0,09058 m | 0,07412 a 0,10792 m |

Com 24 observações anônimas por semente, a busca dimensional selecionou `1*q + 1*r*u + 0.5*s*u²`. Aqui os nomes não descrevem a lei: `q,r,s,u` são entradas numéricas com dimensões fornecidas. As 12 combinações de avaliação por semente não entram no ajuste. O maior RMSE foi aproximadamente **1,52×10⁻¹⁵**. Isso é redescoberta na gramática declarada, não demonstra descoberta sem conhecimentos prévios. A execução independente de dez pontos de artefatos na DSL isolada concordou com a avaliação da expressão.

O ensaio de revisão ajustou hipóteses linear/quadrática, selecionou o tempo de maior desacordo, obteve uma observação do simulador e registrou a refutação da previsão linear e o modelo revisto. O registro contém a previsão errada; ela não é apagada pelo ajuste posterior.

## Comparação neural e orçamento de exemplos

A camada neural linear com características físicas teve RMSE entre cerca de `2,5×10⁻¹¹` e `4,0×10⁻⁷` no piloto de 64 exemplos dentro da mesma faixa de condições. O modelo com características cruas ficou entre **1,12 e 1,75**. Mínimos quadrados com as mesmas características físicas foi mais preciso, com erro próximo ao limite numérico. Os produtos físicos são fornecidos; apenas os pesos da camada são aprendidos.

O suplemento usa outras cinco sementes e condições de previsão fora das faixas usadas no treino, mas ainda válidas no simulador. Cada célula abaixo é a média de RMSE nas cinco sementes; todos os tamanhos de treino e resultados estão no JSON.

| Exemplos / ruído | Rede com entradas cruas | Rede com características físicas | Mínimos quadrados físicos |
| --- | --- | --- | --- |
| 4 / sem ruído | 2,7792 | 0,4601 | 6,80×10⁻¹⁶ |
| 16 / sem ruído | 2,4616 | 0,1805 | 7,34×10⁻¹⁶ |
| 64 / sem ruído | 2,4467 | 0,0478 | 5,96×10⁻¹⁶ |
| 4 / ruído 0,05 | 2,5709 | 1,0607 | 0,7810 |
| 16 / ruído 0,05 | 2,4891 | 0,1724 | 0,1421 |
| 64 / ruído 0,05 | 2,3828 | 0,0673 | 0,0592 |

O orçamento fixo de 800 épocas deixa erro de otimização em algumas redes. Não há justificativa para substituir o comparador tradicional por essa rede onde ele resolve melhor a tarefa. Em uma condição intermediária com ruído a rede teve média menor, mas cinco sementes e essa única média não demonstram superioridade geral. As duas entradas realmente fora do domínio do simulador foram rejeitadas. A transferência foi avaliada posteriormente em trajetória medida e rejeitada no protocolo abaixo; os resultados sintéticos não sustentam aplicação a movimentos reais mais amplos.

## Experimentos quânticos

Foram estudadas quatro frequências em cinco sementes, com três tempos de treino e **1.000 preparações por tempo**: são 3.000 resultados de medição por ajuste, não apenas três exemplos binários. O RMSE médio das probabilidades previstas em novos tempos foi **0,01307**, com intervalo bootstrap exploratório **0,00779 a 0,01793**. Frequências alternativas continuam registradas quando as observações não as distinguem.

No ensaio contextual sintético, o modelo quântico e a cadeia clássica contextual têm dois parâmetros e avaliam os mesmos 441 candidatos. As previsões e a perda de teste coincidem até arredondamento numérico. Esse empate é esperado pela equivalência matemática deliberada do controle. O resultado **não sustenta vantagem cognitiva quântica**. Uma análise de dados humanos publicados foi executada separadamente, como descrito a seguir.

A sonda com 25 configurações em que a ordem deveria ser irrelevante encontrou **quatro decisões sensíveis à ordem** ao transformar probabilidade contextual em decisão binária. O controle clássico equivalente apresenta o mesmo problema; uma conjunção simbólica não muda com a ordem. Essa falha limita esse mecanismo específico e motiva mantê-lo fora do verificador lógico. Não permite concluir que toda abordagem de cognição quântica falhe.

O custo foi medido para 1 a 8 qubits: de 2 a 256 amplitudes, 32 a 4.096 bytes de conteúdo ideal complex128. Objetos Python têm sobrecarga adicional. Os testes são pequenos e não demonstram viabilidade de simulações quânticas grandes. A decisão registrada é manter simulação clássica, sem aquisição de hardware quântico.

## Reanálise de estatísticas humanas publicadas

Foram transcritas as duas últimas colunas da tabela 1 de [Wang e Busemeyer, 2013](https://jbusemey.pages.iu.edu/quantum/QuestOrdEff.pdf), relativas às experiências de laboratório dos autores. A reconstrução inteira, conferida com os tamanhos de grupos e arredondamentos publicados, produz 224 respostas por experiência, 448 no total. Isso não significa novas pessoas recrutadas, nem confirma que os participantes das duas experiências sejam distintos entre si.

| Experiência do catálogo | Perda média por resposta nas partições de avaliação | Maior resíduo de probabilidade no ajuste completo | Diagnóstico do modelo restrito |
| --- | --- | --- | --- |
| `lab_racial_hostility` | 1,37220 | 0,28108 | Rejeitado pelo limiar prévio de 0,10 |
| `lab_affirmative_action` | 1,17511 | 0,17998 | Rejeitado pelo limiar prévio de 0,10 |

As perdas dos controles clássico e quântico coincidem numericamente; a maior diferença absoluta entre perdas totais foi inferior a `6×10⁻¹⁴`. Ambos receberam as mesmas metades de respostas para ajuste e avaliação, com o mesmo orçamento. As cinco repartições dos agregados apenas verificam sensibilidade à partição; não são novas réplicas científicas.

O resultado rejeita a adequação deste pequeno modelo 2D nos critérios do piloto. Ele não refuta todos os modelos quânticos de cognição, inclusive os de dimensão maior do artigo, nem estabelece uma descrição biológica da mente. A implementação de F08-05 agora possui um experimento com dados humanos publicados, resultado negativo e controle clássico comparável; não uma promessa de superioridade.

## Dados observados e resultado negativo da calibração

Em 24 pares de ajuste e 12 de avaliação do corpus NIST, a busca escolheu uma expressão com um termo devido à penalização de complexidade. Os resultados foram:

| Comparador | RMSE em unidades nativas não especificadas |
| --- | --- |
| Média dos dados de ajuste | 373,76702 |
| Expressão selecionada | 0,99255 |
| Regressão afim por mínimos quadrados | 0,97942 |

A expressão supera a média, mas **falha no requisito prévio de igualar mínimos quadrados em até 10⁻⁸**. A diferença é 0,013135 e consta em `discovery.failures`. Não foi alterado o critério ou a penalização depois da observação do resultado. O estudo aponta uma perda associada à preferência pela expressão mais simples; não é uma melhoria do método publicado.

No ensaio separado com todos os 36 pares, a implementação QR reproduziu os coeficientes certificados com erros absolutos de **1,24×10⁻¹⁴** e **4,44×10⁻¹⁵**. Isso confere cálculo em dados observados; não constitui uma nova medição independente. O [dossiê](SCIENCE_DISCOVERY.md) mantém o uso metrológico sem aprovação por falta de unidades e incerteza instrumental documentadas. O campo `open_problem_gate` permanece fechado: o critério de utilidade falhou e faltam dados independentes adequados. Uma revisão por agente de IA não fornece essas evidências empíricas.

## Correções de QA e histórico dos relatórios

- O QA identificou que `units=[]` era aceito devido à conversão implícita para `{}`. A entrada agora é rejeitada.
- O QA identificou que o adaptador retornava `answered` para um ajuste quântico ambíguo. Agora retorna `unknown`, preservando a distinção entre verificar a conta e identificar um parâmetro.
- O caminho integrado de ajuste físico tinha um erro de formatação, embora a função de ajuste isolada passasse. Os campos foram corrigidos e o dispatcher rejeita resultados não finitos. Domínios não textuais também são rejeitados antes da seleção do serviço.
- O desenvolvedor identificou que o primeiro relatório não registrava a falha de equivalência à regressão afim. O relatório foi corrigido para registrar o resultado negativo; o modelo e o critério não foram ajustados para conseguir aprovação.
- A verificação de artefatos em processo isolado, o ciclo de escolha de experimento, validações de procedência e o suplemento de orçamentos foram acrescentados antes da versão final do piloto.

[pilot.v1.json](../../experiments/science/results/pilot.v1.json), [pilot.v2.json](../../experiments/science/results/pilot.v2.json), [pilot.v3.json](../../experiments/science/results/pilot.v3.json) e [pilot.v4.json](../../experiments/science/results/pilot.v4.json) permanecem históricos. **O v1 não deve ser usado para afirmar que todos os critérios passaram**, pois omitia a falha de comparação NIST. A versão v5 inclui as correções e as estatísticas humanas, com hashes correspondentes ao registro anterior à execução. O agente QA independente aprovou os 34 testes científicos, inclusive os contratos integrados, procedência, dados humanos e preservação do resultado negativo NIST. Os testes de software e o aceite dos itens são separados destes resultados de pesquisa.

## Atualização de transferência física — 12/09/2026

O [piloto v6](../../experiments/science/results/pilot.v6.json), precedido pelo [registro v6](../../experiments/science/registration.v6.json), acrescenta a trajetória real TUM e preserva as versões anteriores. Seus 24 hashes coincidem. Em 24 segmentos (80 poses 3D futuras, equivalentes a 240 coordenadas escalares), aceleração constante teve RMSE escalar de 0,141737 m contra 0,099956 m por persistência; o portão rejeitou a transferência. O erro numérico do integrador foi menor que 2×10⁻¹⁵ m. A [documentação específica](SCIENCE_MOTION_TRANSFER.md) detalha procedência, incerteza, protocolo, negativos e limites. O aceite independente de F06-08 foi concedido em 12/09, após a correção de integração e o reteste no v7.

O QA da trajetória detectou no v6 que uma avaliação concluída com rejeição física recebia a mesma sinalização de uma falha de execução; isso ocultava a conclusão negativa no chat. O dispatcher foi corrigido para separar `verification.passed` de `physical_transfer_promoted`, anexar fontes primárias e unidades. O [registro v7](../../experiments/science/registration.v7.json) precede o [relatório v7](../../experiments/science/results/pilot.v7.json), preservando v6 como histórico. Os critérios e os dados não foram ajustados.

O QA aprovou **40 testes científicos** na retomada, incluindo seis casos de transferência física. A [matriz geral](F01_F11_QA.md) registra o aceite de software; a hipótese de transferência continua rejeitada.
