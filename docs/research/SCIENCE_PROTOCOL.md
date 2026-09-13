# Laboratório científico — F06, F08 e F10

Implementação limitada e experimentos próprios, em 09/09/2026. A conclusão de tarefas de engenharia será decidida pelo QA; estes experimentos não demonstram invenções científicas inéditas, cognição humana ou vantagem quântica.

## Contrato utilizado pelo núcleo

`src.science.resolve(request)` recebe um objeto com `domain`, `operation` e `parameters`. Retorna `status`, `sentences` aprovadas, `values`, `units`, `premises`, `verification` e `limitations`. Não utiliza Qwen, rede ou dados pessoais. O processador próprio do chat transforma uma entrada JSON neste pedido; o núcleo deve preservar tanto o estado epistemológico quanto o resultado numérico.

```json
{"domain":"physics","operation":"simulate","parameters":{"x":0,"v":2,"dt":1,"a":0,"units":{"x":"m","v":"m/s","dt":"s","a":"m/s^2"}}}
```

`verification.passed` confirma as verificações da operação, não a verdade universal de um modelo. Por exemplo, os cálculos da verossimilhança podem estar corretos e a frequência quântica continuar desconhecida: nesse caso `status=unknown` e `parameter_identified=false`.

| Domínio/operação | Entrada principal | Resultado |
| --- | --- | --- |
| `physics/simulate` | `x,v,dt,a,steps,mass,units` | Posição, velocidade, energia, trabalho externo e erro contra referência |
| `physics/fit` | `observations:[{t,x}],degree,noise_sigma` | Parâmetros inferidos, resíduos, identificabilidade e compatibilidade |
| `physics/experiment` | Observações anteriores e nova observação | Previsão anterior, eventual refutação, ajuste revisto |
| `physics/simulated_experiment` | Observações, parâmetros do executor `environment`, tempos candidatos | Seleção por desacordo, execução e revisão; os parâmetros do executor não entram no ajuste |
| `physics/measured_transfer` | Nenhum parâmetro; protocolo TUM fixo | Comparação com trajetória medida, erro simulação/realidade e bloqueio de promoção quando inadequado |
| `physics/symbolic` | Medições anônimas, dimensões e orçamento | Expressão selecionada, coeficientes, candidatos e artefato conferido em processo isolado |
| `physics/dimensions` | AST de unidades: `add/subtract/multiply/divide` | Expoentes de comprimento, tempo e massa, ou rejeição |
| `quantum/evolve` | Estado complexo, `omega,duration` | Evolução Rx e probabilidades de Born |
| `quantum/measure` | Estado, `shots,seed` | Contagens de preparações independentes |
| `quantum/fit` | Tempos, contagens e frequências candidatas | Verossimilhança, candidatos plausíveis e ambiguidade |
| `quantum/measurement_choice` | Frequências e tempos disponíveis | Tempo com maior desacordo entre previsões |
| `quantum/cost` | Qubits e repetições | Amplitudes, tamanho ideal e tempo observado |
| `quantum/contextual_study` | Nenhum parâmetro adicional | Reanálise registrada de estatísticas humanas agregadas publicadas |
| `discovery/calibration` | Nenhum parâmetro adicional | Estudo fixo de dados reais NIST e limitações |
| `discovery/prior_art` | `query` | Busca no catálogo versionado de fontes primárias; ausência não prova novidade |

Números não finitos, unidades incompatíveis, matrizes inválidas e orçamentos fora dos limites são rejeitados. As APIs de ajuste não executam texto de programa. A expressão final pode ser compilada para a DSL aritmética limitada de `src/cognition/sandbox.py`, conferida em outro processo e comparada com a avaliação da árvore de expressão. Isso verifica execução, não fornece uma nova observação física.

## F06 — Escopo físico

Uma partícula pontual em uma dimensão, com aceleração externa constante e ausência de colisões e arrasto. A integração usa velocidade no ponto médio; uma fórmula fechada independente confere posição e velocidade. Balanço de energia usa `ΔK = trabalho externo`; não exige conservação da energia cinética quando há aceleração externa. A referência didática é a [cinemática 1D do MIT](https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/mit8_01scs22_chapter4.pdf).

| Quantidade | Domínio do simulador | Unidade |
| --- | --- | --- |
| Posição inicial | −10 a 10 | m |
| Velocidade inicial | −3 a 3 | m/s |
| Aceleração | −2 a 2 | m/s² |
| Intervalo | 0,1 a 2 | s |
| Massa | 10⁻⁶ a 10⁶ | kg |
| Passos de integração | 1 a 10.000 | inteiro |

Esses limites se aplicam às condições iniciais; a posição final pode sair do intervalo da posição inicial. O ajuste recebe posições e tempos entre 0 e 2 s, inferindo velocidade não observada diretamente e, no modelo quadrático, aceleração. Requer matriz com posto completo e observações suficientes. Ruído declarado é uma escala de erro nas posições, não confiança na fonte nem prova probabilística do modelo.

O aprendiz de equações enumera produtos de até quatro variáveis com grau total até três e somas de até três termos. Coeficientes são estimados por QR com escalonamento e reortogonalização; termos dimensionalmente incompatíveis são removidos quando as dimensões são fornecidas. Simetrias de troca de sinal podem ser declaradas como `symmetries:[{"variables":["q"],"parity":"even"}]`: somente monômios que preservem a paridade são admitidos. Uma simetria fornecida é uma hipótese a justificar, não uma descoberta da rede. O aprendiz recebe somente linhas anônimas; a implementação do simulador não é consultada. A gramática, unidades, tolerância e penalização de complexidade são conhecimentos prévios declarados. A proposta é um estudo pequeno de regressão simbólica, não uma reprodução completa do [AI Feynman](https://arxiv.org/abs/1905.11481).

A comparação neural treina uma camada linear com pesos aleatórios próprios. Um modelo usa variáveis cruas; o outro recebe características físicas `v·t` e `a·t²/2`, que impõem deslocamento nulo em `t=0`. Esse conhecimento foi fornecido. O comparador tradicional ajusta as mesmas características por mínimos quadrados. A distinção entre conhecimento físico fornecido e aprendido segue a questão discutida em [Physics-informed machine learning](https://www.nature.com/articles/s42254-021-00314-5); este código não implementa uma rede profunda de equações diferenciais.

O [suplemento registrado](../../experiments/science/supplement.v1.json) mede 4, 8, 16, 32 e 64 exemplos, com e sem ruído, em cinco novas sementes. Avalia condições de velocidade, aceleração e tempo não usadas no treino, ainda dentro do domínio do simulador. Entradas realmente fora desse domínio devem ser rejeitadas. O orçamento de 800 épocas é fixo e pode deixar erro de otimização; nenhum tamanho de amostra é anunciado como suficiente universalmente.

**Limites ainda presentes:** apenas uma família Newtoniana, sem sistemas caóticos, colisões, atrito ou incerteza de estrutura completa. A [avaliação TUM de transferência](SCIENCE_MOTION_TRANSFER.md), registrada e executada em 12/09/2026, confronta o modelo com trajetória física medida e rejeita sua promoção. Dados de calibração de ozônio pertencem a outro problema e não são usados como evidência dessa transferência. Problemas maiores continuam bloqueados.

## F08 — Equações e operações quânticas

- Estado puro: vetor complexo `ψ`, com `Σ|ψᵢ|²=1`. Valores que não satisfaçam a norma são rejeitados, não corrigidos silenciosamente.
- Evolução fechada: `ψ′=Uψ`, com teste independente de `U†U=I`. O exemplo de dois níveis usa `U=exp(−iωtX/2)`, correspondente ao Hamiltoniano declarado `H=ℏωX/2`.
- Medição: `p(i)=|ψᵢ|²`, pela regra de Born. As contagens simulam preparações independentes; não são múltiplas leituras sem nova preparação de um único estado.
- Observável: matriz Hermitiana `A`; valor esperado `ψ†Aψ`. A implementação rejeita um observável não Hermitiano.
- Inferência: dentro da classe Rx fornecida, escolher `ω` por verossimilhança binomial dos tempos e contagens observados. Mais de um candidato compatível mantém a ambiguidade.
- Medição ativa: escolher o tempo que maximiza a variância das probabilidades previstas pelos candidatos. É uma heurística explícita, não prova de optimalidade global.

Estados e operadores seguem as definições de [informação quântica da IBM](https://qiskit.qotlabs.org/learning/courses/basics-of-quantum-information/single-systems/quantum-information). São admitidos vetores de 1 a 8 qubits; a verificação cúbica de matrizes densas é limitada a 5 qubits e a evolução Rx a 1 qubit. O custo ideal de `2ⁿ` amplitudes em complex128 é `16·2ⁿ` bytes, além da sobrecarga dos objetos Python; esse crescimento é compatível com a documentação do [Qiskit Aer](https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.StatevectorSimulator.html). Nenhuma dessas bibliotecas é uma dependência de execução.

O ensaio contextual usa duas perguntas A/B, estado no plano real com ângulo `θ` e separação de bases `φ`. A probabilidade conjunta é o produto entre a projeção inicial e a projeção após a primeira resposta. O controle clássico é uma cadeia de transições condicionada à ordem, parametrizada pelos mesmos dois ângulos; é matematicamente equivalente nesse recorte. Ambos recebem as mesmas contagens e avaliam 441 pares de parâmetros: uma grade de 21 × 21 pontos, com θ e φ limitados a [0, π/2]. Essa faixa e a discretização são restrições do modelo avaliado; não constituem otimização de todos os modelos quânticos 2D nem de ângulos contínuos. Esse controle verifica se o formalismo, isoladamente, oferece algo além das probabilidades contextuais que um modelo clássico pode representar.

Os dados do primeiro ensaio contextual são **sintéticos**. Esse ensaio não valida um modelo do comportamento de pessoas. A [referência de Yearsley e Busemeyer](https://jbusemey.pages.iu.edu/quantum/YearselyBusemeyerJMP.pdf) trata modelos matemáticos de decisão; não fundamenta afirmar que o cérebro seja um computador quântico. A sonda de decisões cuja ordem deveria ser irrelevante é separada da qualidade do ajuste; uma boa descrição de efeitos de ordem não autoriza trocar implicação lógica por uma probabilidade contextual.

Uma segunda análise, separada e [registrada antes da pontuação](../../experiments/science/human-context.protocol.v1.json), utiliza estatísticas agregadas de duas experiências humanas publicadas pelos próprios autores em [Wang e Busemeyer, 2013](https://jbusemey.pages.iu.edu/quantum/QuestOrdEff.pdf), tabela 1, página 700. Os quatro grupos somam 448 respostas. Contagens são reconstruídas somente quando há um único inteiro compatível com cada proporção arredondada e tamanho amostral. A tabela foi conferida visualmente. São dados publicados reanalisados, sem coleta de pessoas pelo projeto ou reprodução do artigo completo.

O ensaio humano usa os mesmos dois parâmetros, 441 candidatos e partições de respostas para ambos os modelos. Cinco repartições dos mesmos agregados não equivalem a cinco réplicas humanas independentes. O diagnóstico previamente fixado rejeita nosso modelo restrito quando o maior resíduo de probabilidade supera 0,10; não é um teste estatístico populacional. O modelo 2D aqui implementado é mais restrito que o formalismo geral discutido no artigo. Resultados estão separados por origem e não autorizam inferências sobre indivíduos ou populações demográficas.

**Decisão de hardware:** não integrar hardware quântico nesta etapa. Não foi identificado um algoritmo com vantagem demonstrada no problema estudado. Preparação, ruído, número de medições, leitura, filas e custo teriam de ser contabilizados antes de reabrir essa decisão. Não houve compra nem uso de serviço pago.

## Protocolo, versões e reprodução

O [protocolo v1](../../experiments/science/protocol.v1.json) foi gravado antes do primeiro relatório. As sementes reservadas desta frente não são executadas; nenhum teste reservado da F00 é acessado. O [registro v1](../../experiments/science/registration.v1.json) preserva os hashes anteriores ao primeiro piloto. Alterações de QA geram novo registro e relatório, preservando o anterior.

```bash
python3 scripts/evaluate_science.py --register --output .runtime/science-registration-new.json
python3 scripts/evaluate_science.py --output .runtime/science-evaluation-new.json
python3 -m unittest discover -s tests/science -v
```

O caminho de saída deve ser novo. O comando não substitui resultados existentes. O relatório registra hashes, ambiente, tempos, resultados negativos e ausência de chamadas a modelos gerais. O inventário e protocolo F00 permanecem históricos e congelados.
