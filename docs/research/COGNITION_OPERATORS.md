# Compreensão própria, operadores aprendidos e invenção verificável

Implementação retomada em 12/09/2026. Os requisitos F02-06, F05 e F07 são avaliados no domínio abaixo. O aceite de cada item pertence ao QA em [F01_F11_QA.md](F01_F11_QA.md).

## Fluxo implementado

`process_message → ProblemSpec → CognitiveCore → operator_runtime → AnswerPackage → renderizador` é executado no chat real. O Qwen não interpreta as observações nem escolhe um operador ou programa. O modo pesquisa não faz chamadas a modelos gerais. O mesmo contrato serve à saída determinística e à organização de sentenças já aprovadas.

O operador inicial é uma transformação numérica `y = a*x + b`, com `a` inteiro em `[-3,3]`, `b` inteiro em `[-5,5]`, entrada em `[-20,20]` e observações limitadas a `|y| ≤ 100`. A família de 77 hipóteses foi fornecida pelo projeto. Os coeficientes que sobrevivem à verificação são selecionados pelos exemplos; eles não estão associados a nomes de objetos ou a respostas prontas. Modelos fora dessa família podem ser rejeitados ou parecer compatíveis com poucos exemplos. A aplicação continua **condicional à hipótese de família afim estacionária**.

Uma rede própria de transição usa um neurônio linear, inicialização pseudoaleatória, erro quadrático e descida de gradiente em lote. Seus parâmetros são treinados com as observações do pedido. A rede pode ordenar uma proposta de coeficientes, mas um verificador independente confere cada coeficiente contra todas as observações e examina a família finita antes de resolver a ambiguidade. A confiança da rede não aprova uma conclusão. O piloto não encontrou ganho operacional com essa proposta: o chat usa `use_neural=false` por padrão; `true` mantém o experimento disponível. Essa decisão evita apresentar uma rede redundante como origem da validade.

## Usar pelo chat

Envie as mensagens JSON em uma mesma conversa. O processador aceita esses contratos sem Qwen:

```json
{"task":"learn_operator","name":"incrementar","examples":[{"x":0,"y":1}]}
```

Um exemplo pode deixar várias alternativas. O pacote informa a quantidade de candidatos e uma entrada sugerida para distingui-los. Envie a nova observação:

```json
{"task":"learn_operator","name":"incrementar","examples":[{"x":1,"y":2}],"use_neural":true}
```

O histórico de exemplos é reutilizado. A versão anterior é retirada, uma nova versão recebe os dados acumulados e seus dependentes são invalidados. Repetir exatamente o mesmo par não conta como confirmação independente.

```json
{"task":"learn_operator","name":"dobrar","examples":[{"x":0,"y":0},{"x":1,"y":2}]}
```

```json
{"task":"apply_operator","name":"incrementar","x":4}
```

```json
{"task":"invent","initial":1,"target":6,"operators":["incrementar","dobrar"],"max_steps":6,"max_operations":2048,"alternative_initials":[0,2]}
```

A meta é mensurável: alcançar `target`, com erro absoluto até `1e-9`, partindo de `initial`. Recursos são os operadores aprendidos acessíveis; restrições são seus domínios, horizonte e orçamento. O pacote guarda a sequência, expressão composta, programa DSL, previsões, execuções e referências das versões. As variações `alternative_initials` são hipóteses sob outras premissas: nunca contam como atendimento da meta original.

```json
{"task":"test_operator","name":"incrementar","examples":[{"x":2,"y":4}]}
```

Esse exemplo contradiz `x+1`. O núcleo compara previsão e observação informada, registra a falha, refaz o ajuste e retira a versão e os programas dependentes. Os três exemplos não cabem em uma única função afim: o resultado passa a desconhecido. Reapresentar apenas os dois exemplos antigos não apaga a contraprova; a memória de falha participa do novo ajuste. A contraprova permanece uma premissa informada pelo usuário, não uma medição física certificada pelo sistema.

## Transformações e verificação de invenções

| Transformação | Artefato efetivamente produzido | Limite |
| --- | --- | --- |
| Composição e busca | Sequência de operadores aprendidos, encontrada por busca em largura | Horizonte até 10; orçamento até 10.000 operações; 1–8 operadores |
| Abstração | Programa alternativo da função composta `A*x+B`, executado separadamente | Mesmas hipóteses e domínio intermediário do plano original; não é novo mecanismo |
| Analogia estrutural | Ordem de ações de procedimento armazenado aplicada a outro estado e alvo | Recalcula e verifica os operadores atuais; nomes isoladamente não provam equivalência |
| Variação de premissa | Reexecução explícita com até três estados iniciais alternativos | Hipótese exploratória, nunca aprovação do problema original |

Assinaturas de mecanismos usam coeficientes normalizados, incluindo equivalência entre inteiros, floats e zero com sinal. A abstração e o programa longo recebem a mesma assinatura: não contam como duas invenções. O relatório separa ações, instruções, operações de busca, mecanismos distintos, duplicatas, novidade para a memória, utilidade e viabilidade. Soluções conhecidas na memória são comparadas novamente; a busca continua procurando uma sequência mais curta que uma transferência anterior.

O programa usa apenas a DSL aritmética finita do [sandbox](../../src/cognition/sandbox.py). A execução isolada é independente da avaliação de funções usada na busca. Verifica a meta, a abstração e sondas em `-20,-2,0,2,20`; sondas cujo percurso sai do domínio são registradas como excluídas, sem inventar um teste aprovado. Cada execução permite até 1.000 passos. Essas sondas verificam compilação e condições do artefato. Elas não medem o mundo real nem confirmam, sozinhas, extrapolações do modelo aprendido.

## Origem, versões, escopo e interrupções

- Exemplos fornecidos pelo usuário permanecem premissas. O modelo é `kind=model`, `status=asserted`, `evidence=deduction`, com `epistemic_status=conditional_model_fitted_to_user_observations`. Não usa `register_model` para ativar pesos globais e não atribui `verified` a texto recebido.
- Cada versão aponta para episódios e testes de origem. Escopo da aprendizagem é a conversa. Operadores com o mesmo nome em conversas distintas não se misturam.
- Contraprovas dependem da mensagem do teste, não da versão refutada. Isso preserva resultados negativos após a retirada da versão antiga. Procedimentos dependem das versões exatas usadas para construí-los.
- O ajuste e as execuções acontecem fora da transação SQLite. Efeitos e pacote final são persistidos em uma transação curta no sidecar, identificada pelo episódio de origem. Uma interrupção entre o efeito e o checkpoint do chat não cria outra versão no reenvio.
- O chat guarda o pacote semântico antes da redação. Retomadas conferem fontes `E-` e `M#`, incluindo premissas de deduções. Um pacote cujas fontes foram retiradas vira desconhecido; não volta a afirmar uma conclusão obsoleta.

## Rede própria de compreensão

O MLP em [neural.py](../../src/cognition/neural.py) transforma n-gramas de caracteres, projetados por hashing em 128 entradas, em 16 unidades `tanh` e dez intenções com `softmax`. Não contém pesos de Qwen. Treino: 150 exemplos anotados pelo projeto, 45 épocas, taxa inicial 0,12, sementes 17/29/47. Validação e avaliação usam templates e entidades diferentes; há 50 exemplos em cada corte. O corpus adicional de contexto testa referências, negação, erros de digitação, unidades e mudança de assunto.

O protocolo v1 propunha habilitar interpretações não cobertas acima de certos limiares de probabilidade. Os resultados não sustentaram essa promoção: 100% de acurácia no treino, 40–46% na validação e 58–68% na avaliação. A decisão posterior é `adopted=False` mesmo se a rede apresentar probabilidade 1. A proposta continua inspecionável no ProblemSpec e na tarefa `classify`, sem alterar fatos, negações ou intenção da gramática. O protocolo histórico foi preservado; a reprodução v2 registra a decisão e hashes dos fontes.

## Reprodução

Em diretórios novos, preservando os resultados anteriores:

```sh
python3 scripts/train_cognition.py --output-dir /tmp/ar-intent-reproduction
python3 scripts/evaluate_operators.py --output-dir /tmp/ar-operators-reproduction
python3 -m unittest discover -s tests/cognition -v
```

Os scripts salvam protocolo e hashes antes de ajustar os modelos. A avaliação F00 reservada não é utilizada. Consulte [COGNITION_RESULTS.md](COGNITION_RESULTS.md) para resultados, comparações, emendas e decisões.
