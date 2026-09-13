# Resultados de compreensão, aprendizagem de operadores e invenção

Pilotos locais retomados em 12/09/2026. São experimentos de software e aprendizagem em tarefas escalares sintéticas. Não constituem avaliação de inteligência geral, novidade científica ou raciocínio humano.

## Artefatos e método

A execução após a correção conversacional usa [operators-pilot.v5](../../experiments/cognition/operators-pilot.v5/): [protocolo](../../experiments/cognition/operators-pilot.v5/protocol.json), [registro e hashes](../../experiments/cognition/operators-pilot.v5/registration.json) e [resultados completos](../../experiments/cognition/operators-pilot.v5/results.json), com reprodução v6. O registro passou a abranger 20 dependências, incluindo discurso, extração, memória e verificação de hipóteses. O comando reproduzível é `python3 scripts/evaluate_operators.py --output-dir DIRETORIO_NOVO`.

As versões v4 e anteriores permanecem históricas. A reprodução v5/v6 conserva os resultados numéricos e as nove verificações do fluxo; não constitui novo experimento cego. A correção de linguagem natural possui um [piloto conversacional separado](../../experiments/conversation/conceptual-pilot.v1/results.json): seus diálogos conhecidos não ampliam as alegações de generalização dos modelos numéricos.

O protocolo e o registro são escritos antes dos ajustes. `operators-pilot.v1` preserva a primeira avaliação; `v2` reproduz correções de retomada e sondas de fronteira. A análise `v3` acrescenta, **depois de observar v1**, um comparador de mínimos quadrados com a mesma base quadrática da rede. A emenda está explícita no protocolo. `v4` reproduz uma correção semântica adicional: zero candidatos significa família refutada/desconhecimento, não ambiguidade resolvível com mais um exemplo. Esses resultados são uma reprodução e ampliação de um piloto já observado, não um novo teste cego. Nenhum conjunto reservado da F00 foi pontuado.

Foram executadas 360 condições: oito funções em três famílias, três sementes, cinco quantidades de exemplos (`1,2,4,8,16`) e três níveis de ruído (`σ ∈ {0; 0,1; 0,5}`). Cada condição treina dois modelos próprios, graus 1 e 2: **720 ajustes**, sem pré-treinamento ou metatreinamento. Entradas de adaptação são inteiros distintos em `[-8,8]`; as 16 entradas de avaliação são meios-inteiros de `-7,5` a `7,5`, portanto não aparecem nos exemplos. As sementes reutilizam o mesmo esquema experimental: não são 720 populações independentes.

Os comparadores recebem as mesmas observações: memória exata, vizinho mais próximo, mínimos quadrados afins, mínimos quadrados quadráticos, família afim finita e os dois neurônios. A memória exata abstém-se quando não possui a entrada. O ajuste quadrático clássico abstém-se se faltam observações independentes para identificar os três coeficientes. MSE de um método que abstém não é tratado como zero; cobertura é relatada separadamente. Pesos, sementes, dados, curvas completas de 300 épocas, tempo de ajuste e quantidade de parâmetros constam de cada condição.

Neste piloto, “transferência entre famílias” significa testar a reutilização da mesma representação e do mesmo procedimento de ajuste em estruturas diferentes. **Cada tarefa inicializa e treina pesos novos; não há transferência de pesos entre tarefas, metatreinamento ou representação aprendida compartilhada.** O reuso efetivo entre problemas no chat ocorre por modelos e programas versionados, com premissas rastreáveis; deve ser distinguido desse estudo da representação.

## Aprendizagem com poucos exemplos e transferência

| Condição | Neurônio afim: MSE médio | Mínimos quadrados afins: MSE médio | Interpretação |
| --- | ---: | ---: | --- |
| Família afim, 2 exemplos, sem ruído | 1,31555 | 0 | Com algumas amostras mal condicionadas, 300 épocas não bastam; a média não deve ser escondida pela mediana próxima de zero |
| Família afim, 16 exemplos, sem ruído | 1,01 × 10⁻²⁶ | 0 | Aprende os coeficientes; nenhum ganho sobre solução clássica |
| Família afim, 16 exemplos, σ=0,5 | 0,0436994 | 0,0436994 | Mesmo erro prático; nenhuma vantagem neural detectada |
| Família quadrática, 16 exemplos, sem ruído | 371,569 | 371,569 | Representação afim falha em estrutura nova |
| Família por partes, 16 exemplos, sem ruído | 13,4493 | 13,4493 | Generalizar além da família requer outras hipóteses |

O neurônio com `x²` fornecido reduz o MSE quadrático, com 16 exemplos sem ruído, para aproximadamente `8,90 × 10⁻⁵`. O comparador quadrático clássico, com a mesma base, atinge `1,29 × 10⁻²⁹`; com ruído `σ=0,5`, seus erros são, respectivamente, `0,0596471` e `0,0583068`. Isso demonstra o efeito de uma representação adequada **fornecida pelo projeto**, não a descoberta autônoma de uma abstração ou superioridade da rede. O arquivo completo inclui todos os erros e as abstenções por posto insuficiente. Com apenas dois exemplos, o neurônio quadrático pode produzir uma curva, mas os coeficientes são indeterminados; emitir uma previsão não remove essa incerteza.

A família afim finita tem cobertura total e erro zero nas funções afins limpas após dois exemplos distintos. Com ruído, restringir coeficientes inteiros pode proteger algumas previsões e levar a abstenções em outras: em 16 exemplos afins com `σ=0,5`, cobertura é 50%, embora o erro dos casos respondidos seja zero. Em funções por partes com apenas dois exemplos, a família errada pode parecer identificada e falhar na avaliação. Por isso o chat sempre qualifica a previsão pela família declarada e aceita contraprovas.

## Seleção ativa e ablações

Foram executados 693 casos de consulta: 77 funções afins × três sementes × três estratégias. Todas recebem um exemplo inicial e orçamento de uma nova consulta. Seleção ativa, aleatória e menor entrada absoluta reduziram o conjunto de candidatos em média em `3,74026`, chegando a um candidato. **Não houve vantagem de seleção ativa neste domínio.** Duas retas distintas que coincidem no primeiro ponto já se distinguem em qualquer outro ponto; uma política sofisticada não ganha informação adicional nessa família limpa. A regra permanece disponível como política opcional e auditável; não é apresentada como estratégia aprendida superior.

| Condição de invenção | Metas aprovadas | O que mudou |
| --- | ---: | --- |
| Núcleo completo | 6/6 | Memória, rede propositora, composição e execução independente |
| Sem rede | 6/6 | Mesmas observações, gramática e verificação; nenhum ganho da proposta neural |
| Sem memória | 0/6 | Descarta a primeira observação recebida e conserva só a última; perde identificação dos operadores |
| Sem busca de composições | 0/6 | Avalia apenas zero ou uma ação em metas que exigem várias |

Essas duas últimas ablações demonstram necessidades operacionais de manter evidência e compor ações. Não demonstram que esta arquitetura de memória ou busca seja superior a todas as alternativas. Os alvos não foram usados no ajuste de operadores; as composições são novas para os exemplos de transição, dentro da gramática conhecida.

Em seis programas propositalmente corrompidos, a aprovação sem execução aceitaria 6/6 resultados errados; a execução independente rejeita 6/6. Isso é **injeção controlada de falhas**, não estimativa da taxa natural de alucinação. A rede opcional é confrontada com o mesmo verificador de observações; o QA também injeta propostas neurais erradas para conferir rejeição.

## Fluxo real de conversa, invenção e contraprovas

O piloto executa nove mensagens por `ChatEngine.reply`, em SQLite temporário e modo pesquisa:

1. Um exemplo gera alternativas para o operador; o núcleo pede informação discriminante.
2. A nova transição atualiza o modelo e identifica `x+1` dentro da família fornecida.
3. Dois exemplos identificam `2*x`.
4. Uma meta nova produz programa, expressão abstrata e DSL executados, com hipóteses de estados iniciais alternativos separadas.
5. Outra meta reutiliza a estrutura de procedimento anterior e verifica o novo contexto.
6. Repetir a invenção não a marca como novidade: assinaturas são estáveis entre inteiros e floats.
7. Uma contraprova retira o modelo e invalida procedimentos dependentes.
8. Reapresentar somente os exemplos antigos preserva a falha acumulada.
9. O operador refutado impede nova invenção aprovada.

As nove verificações do workflow passaram, incluindo ausência de chamadas a modelos gerais. O QA avalia separadamente escopo entre conversas, limites, injeções, falhas de persistência, cancelamento, retomada e fontes retiradas. As sondas de extremos e o replay da abstração verificam a implementação do artefato; não são novas observações independentes do mundo.

## Compreensão: resultado preservado e decisão

A [reprodução do MLP](../../experiments/cognition/intent-reproduction.v2/intent-results.v1.json) repete exatamente os resultados anteriores:

| Semente | Treino, 150 casos | Validação, 50 casos | Avaliação, 50 casos |
| --- | ---: | ---: | ---: |
| 17 | 100% | 40% | 58% |
| 29 | 100% | 46% | 62% |
| 47 | 100% | 44% | 68% |

A rede própria aprende o corpus, mas generaliza de forma insuficiente para controlar a compreensão aberta. Seu checkpoint continua disponível e inspecionável, com `adopted=False`. A reprodução da semente 17 gerou um arquivo de pesos byte a byte idêntico ao anterior. O protocolo v1 histórico não foi reescrito para fingir que essa decisão foi tomada antes dos resultados. O novo registro documenta a reprodução de dados já conhecidos e os hashes de arquitetura, treinamento, corpus e integração.

## Decisões proporcionais à evidência

- Manter memória de observações, versões, falhas e procedimentos; reavaliar fontes ao retomar mensagens interrompidas.
- Manter composição com orçamento, expressão abstrata e execução independente. São necessários para as metas testadas e para rejeitar artefatos inválidos.
- Manter o neurônio de transição como experimento explícito. A chamada comum do chat usa a busca finita sem a rede redundante; `use_neural=true` permite estudar propostas aprendidas.
- Manter propostas do classificador de intenção sem autoridade sobre fatos, contexto ou resposta.
- Não afirmar aprendizagem automática de representação, transferência para português aberto, invenção científica ou vantagem quântica a partir destes resultados.
- Usar as falhas em famílias não afins como requisito de novos experimentos, mantendo cortes novos antes de qualquer promoção futura de modelos.

Os números descrevem domínios, observações e orçamentos declarados. O fechamento de um requisito experimental pode registrar uma hipótese desfavorável; não transforma esse resultado em uma capacidade geral adquirida.
