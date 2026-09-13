# F00 — Protocolo anterior à avaliação inicial

F00-04, F00-05 e F00-06. Protocolo executável: [protocol.v1.json](../../experiments/f00/protocol.v1.json), ID `f00-initial-v1`, escrito antes da primeira pontuação. Registros posteriores de execução e correções de infraestrutura ficam em [F00_RESULTS.md](F00_RESULTS.md); o reservado não é utilizado na F00.

## 1. Pergunta medida e fronteira do experimento

Dado um conjunto de transições exatas, um estado inicial e um estado alvo, retornar um plano de até duas ações **sustentado nas observações**, ou informar evidência insuficiente. A unidade experimental é o episódio; um comparador recebe uma cópia dos mesmos observáveis que os demais e não conserva ajuste entre episódios.

Não há prompt em português aberto, extração neural, treinamento prévio da nossa rede ou chamada ao Qwen. O gerador e as referências são instrumentos de avaliação separados do chat. Nenhuma pontuação de BFS é atribuída a uma regra que o sistema tenha aprendido sozinho.

## 2. Gerador e separação de famílias

`src/research/worlds.py`, versão `f00-worlds-1`, usa `random.Random` local derivado por SHA-256 de versão, split, semente e índice. Não usa `hash()` do processo, relógio nem o gerador global. IDs opacos de objetos, valores e ações mudam por episódio.

| Divisão | Família | Diferença estrutural | Uso permitido na F00 |
| --- | --- | --- | --- |
| development | `unary_rewrite` | Um objeto; regras de reescrita de seu estado | Desenvolvimento e controles de infraestrutura |
| validation | `guarded_rewrite` | Dois objetos; uma ação efetiva depende da combinação de valores e altera um deles | Avaliação inicial pública, explicitamente exploratória |
| reserved | `coupled_transfer` | Dois objetos; ação transfere uma quantidade, alterando ambos e conservando o total por transição | Configuração/estrutura declarada; os episódios das sementes oficiais não são gerados nem pontuados nesta etapa |

São três famílias por mecanismo, não três listas da mesma tarefa separadas apenas por sementes. Dentro de desenvolvimento/validação, o caminho principal pode requerer um operador repetido ou dois distintos; o componente distrator pode formar cadeia ou ciclo. Essas diferenças permanecem após renomear os IDs. Ainda são poucas topologias; generalizar neste espaço não demonstra generalização ampla.

QA verifica também invariantes do construtor de transferência com sementes próprias fora das listas do protocolo, sem executar comparadores nem calcular desempenho. Isso testa conservação e esquema do gerador; não abre o conjunto reservado oficial. A família em si tem especificação pública, portanto não deve ser anunciada depois como um mecanismo inteiramente desconhecido dos desenvolvedores.

Cada família contém consultas diretas, composição de dois passos e informação insuficiente, equilibradas pelo índice interno. O campo `kind` fica no avaliador, não na entrada pública. Há seis estados do mundo, quatro ações e exatamente oito observações no protocolo principal. A composição essencial nunca é apresentada como uma transição única; no caso insuficiente falta uma transição necessária e sua observação é substituída por outra verdadeira, mantendo o mesmo número de exemplos.

Os parâmetros das regras são escolhidos antes da amostragem de evidências. As não transições são no-ops na tabela completa. Os observáveis não revelam a tabela oculta; a sua completude não é uma premissa fornecida ao comparador. Uma resposta casualmente correta na tabela escondida, mas sem sustentação nas observações, continua incorreta para a tarefa especificada. O teste QA constrói duas tabelas compatíveis com os mesmos exemplos e resultados diferentes para verificar a indeterminação.

### Interface de isolamento

`WorldCase` contém `public`, `oracle` e `metadata`. Só `public_input()` chega ao comparador: `schema_version`, `objects`, `actions`, `assumptions`, `observations`, `question`. Não são passados nomes de família, sementes, índice, classe de resposta, testemunho ou tabela oculta. A cópia profunda evita compartilhamento acidental; o avaliador detecta mutação do argumento. O verificador de planos consulta evidências e, separadamente, a tabela privada; QA enumera planos por uma implementação independente.

Isso é uma separação de interfaces para código confiável dentro do mesmo processo Python. Não protege contra código malicioso lendo memória, fonte ou arquivos. Sementes e implementação estão versionadas; a reserva é uma disciplina experimental, não segredo criptográfico. Um teste competitivo posterior precisa custodiante externo e novas famílias privadas.

## 3. Referências de comparação — F00-05

| ID | Situação F00 | Prior/treinamento e mesma informação de teste |
| --- | --- | --- |
| `memory_only` | Executável e medida | Consulta uma transição exatamente observada; não encadeia. Sem treino prévio; mesmos oito exemplos e mesma pergunta |
| `symbolic_search` | Executável e medida | BFS programada sobre transições observadas, estados totalmente observáveis, determinismo e composição fornecidos. Não aprende novos operadores; mesmos oito exemplos |
| `empirical_frequency` | Executável e medida | Ajusta contagens por ação para estado seguinte; ignora estado atual. É referência estatística **fraca e diagnóstica**, não representa o melhor método estatístico. Desempate canônico arbitrário; ajuste recomeça em cada episódio |
| `current_chat_rules` | Registrada; não comparável no benchmark de ações | Motor atual usa triplas universais e hipóteses linguísticas, sem adaptador estado/ação. Os 57 testes funcionais são evidência de contratos próprios; não atribuir scorezero nem fingir a mesma tarefa |
| `qwen_only` | Registrada; não executada | Tem treinamento prévio externo não reproduzido aqui. Protocolo futuro: somente JSON público, sem histórico/memórias, temperatura, pesos, quantização, versão, número de tentativas e orçamento de tokens fixados antes da comparação |
| `own_core_without_qwen` | Registrada; ainda não implementada | Avaliação independente depende de F01 e mecanismos seguintes; proibir qualquer acesso ao Qwen, inclusive para interpretar entrada |
| `own_core_with_qwen` | Registrada; ainda não implementada | Mesma entrada/evidência do núcleo; comparar primeiro o pacote semântico e depois a fidelidade da redação. Não usar texto do Qwen para criar a resposta que supostamente antecede o redator |

Toda referência futura recebe exatamente os mesmos objetos JSON públicos; adaptação de formato não pode acrescentar leis, exemplos, gabaritos ou explicações. Comparações entre Qwen e um núcleo treinado localmente terão duas leituras separadas: capacidade total de cada sistema e benefício incremental do núcleo com os demais recursos controlados. Milhões de exemplos prévios não se tornam “zero exemplos” por estarem nos pesos.

## 4. Métricas, orçamento e incerteza — F00-06

Protocolo v1: dez sementes independentes por divisão, doze episódios por semente (quatro de cada tipo), **120 episódios e 360 execuções de comparador** por divisão. Oito observações por episódio, quatro ações, horizonte de duas ações; nenhum dado de conversa pessoal. As sementes exatas estão no JSON; nenhuma repetição será descartada por desempenho desfavorável.

| Campo | Definição |
| --- | --- |
| `supported_task_success_rate` — primária | Acertos / todos os episódios: plano sustentado que atinge meta quando há evidência; status `insufficient` quando a evidência não determina o plano |
| `answer_coverage` | Episódios respondidos com plano / total. Deve acompanhar o acerto para não premiar abstenção indiscriminada |
| `unsupported_answers` e taxa | Plano apresentado sem cadeia de observações que o sustente; denominador da taxa são respostas com plano. Sem respostas, taxa=null |
| `correct_abstention_rate` | Casos insuficientes reconhecidos / total de casos insuficientes; não confundir `budget_exhausted` com desconhecimento |
| `by_kind` | Contagem e acertos por consulta direta, composição e insuficiência; revela um ganho concentrado em apenas uma classe |
| `invalid_outputs` | Formato, status ou contagem de operações inválidos; exceções do comparador também são falhas contabilizadas, nunca amostras removidas |
| `budget_exhaustions` | Teto determinístico de 128 operações lógicas, ou duração acima de 1 segundo por caso. Casos acima do orçamento não contam como acerto |
| Custo | Operações do algoritmo e tempo por caso, total por comparador, ambiente e hashes de código/protocolo. Operações são contabilizações específicas de cada método, não FLOPs equivalentes |

As referências embutidas verificam o limite de operações no laço principal. A duração é medida com relógio monotônico e verificada **após o retorno**; isso não é interrupção preventiva de código arbitrário. A v1 não aceita plugins de comparadores por CLI. Isolamento em subprocesso e limites de memória para motores não confiáveis pertencem à engenharia futura. Contagem informada de operações não é instrumento suficiente para comparar uma GPU com busca simbólica.

Reportar média por semente e intervalo percentil de 95% com 1.000 reamostragens das **sementes**, usando gerador local fixo. Casos da mesma semente são agrupados; não tratá-los como repetições inteiramente independentes. Reportar também diferença pareada `symbolic_search − memory_only` com as mesmas sementes. Dez grupos formam um piloto; intervalo estreito ou degenerado em tarefas fáceis não prova exatidão fora do gerador. Este experimento não foi dimensionado por análise de poder para declarar descoberta científica.

### Regras de decisão fixadas antes dos resultados

1. **Aceite de infraestrutura:** todos os testes de contratos, isolamento, reprodutibilidade, gabarito independente e métricas devem passar; as regressões do chat também. Uma pontuação elevada não substitui QA.
2. **Controle positivo:** a busca deve resolver planos observados dentro do horizonte; a memória deve acertar consultas diretas e não ser creditada por composições que não realiza. Desvio aciona investigação de instrumento/algoritmo, não ajuste no reservado.
3. **Controle de insuficiência:** dois mundos compatíveis com os mesmos exemplos podem discordar sobre uma transição oculta. Uma resposta específica sem apoio é penalizada mesmo se coincide com o mundo sorteado.
4. **Comparação inicial:** publicar todos os resultados válidos e falhas das três referências. A diferença esperada de BFS/memória é evidência de encadeamento programado, não de aprendizado L3/L4.
5. **Alegação futura:** registrar previamente hipótese, comparador adequado, efeito mínimo relevante, orçamento, número de novas famílias/sementes e critério de decisão. Exigir ganho reservado com incerteza suficiente e limites de respostas sem apoio; o efeito mínimo será definido para essa tarefa, não escolhido após observar os resultados.
6. **Reserva:** `run_evaluation` e a CLI recusam o split reservado na F00. Liberá-lo exigirá nova versão e registro datado de decisão antes de qualquer execução. Depois de consultado, um conjunto deixa de ser reservado para ajustes posteriores; criar nova reserva. Alterações a partir da validação pública são exploratórias e precisam constar do histórico.

## 5. Reprodução

Na raiz, com Python 3.9 ou superior e nenhuma dependência adicional:

```sh
python3 -m unittest discover -s tests/research -v
python3 -m unittest discover -s tests/chat -q
python3 scripts/evaluate_f00.py --split validation --output /tmp/f00-validation-reproduction.json
python3 scripts/evaluate_f00.py --split development --output /tmp/f00-development-reproduction.json
```

Escolha caminhos ainda inexistentes: a CLI recusa sobrescrever relatórios. Sem `--output`, o JSON completo vai para stdout. `--protocol` permite reproduzir outro arquivo versionado; o relatório registra SHA-256 do conteúdo recebido, portanto uma alteração não é a mesma experiência. Os hashes do gerador, comparadores, avaliador e CLI, ambiente, observáveis por hash, IDs e resultados individuais acompanham cada execução. Tempos variam; estados, planos e métricas sem tempo são determinísticos.

Qwen, Ollama, redes externas, bancos do chat e conjuntos de pássaros são desnecessários. O campo de chamadas de rede/modelo é zero por construção do caminho auditado; QA bloqueia os pontos de rede nos testes. Não é um monitor global de tráfego da máquina.
