# F00 — Avaliação inicial reproduzida

Execução em 08/09/2026 (America/Sao_Paulo), Python 3.9.6, macOS arm64. Estes são resultados dos **instrumentos de referência F00**, separados do chatbot e de qualquer núcleo neural futuro. O aceite item a item está em [F00_QA.md](F00_QA.md).

## 1. Registro anterior e artefatos

O [registro de congelamento](../../experiments/f00/registration.v1.json) foi escrito em `2026-09-09T01:51:53.168714+00:00`, antes da primeira execução oficial dos relatórios abaixo. Registra o protocolo, os hashes do código e as correções feitas durante QA antes da pontuação. O [protocolo v1](../../experiments/f00/protocol.v1.json) tem SHA-256 `b66d7a46fbd54cf4f1f2d6fa10eaa42d9df557e4504b22e76657c3732d8744d0`.

| Divisão | Resultado individual e agregados | Amostra |
| --- | --- | --- |
| Desenvolvimento | [development-initial.v1.json](../../experiments/f00/results/development-initial.v1.json) | 10 sementes × 12 episódios × 3 comparadores |
| Validação | [validation-initial.v1.json](../../experiments/f00/results/validation-initial.v1.json) | 10 sementes × 12 episódios × 3 comparadores |

As 720 execuções de comparador correspondem a 240 episódios, com 40 episódios de cada tipo por divisão. Não houve chamada ao Qwen, serviço externo, leitura de conversas nem pontuação do conjunto reservado. Os testes de unidade da família de transferência usaram sementes QA fora do protocolo e verificaram apenas o construtor, sem desempenho de comparadores.

Comandos usados, na raiz:

```sh
python3 scripts/evaluate_f00.py --split development --output experiments/f00/results/development-initial.v1.json
python3 scripts/evaluate_f00.py --split validation --output experiments/f00/results/validation-initial.v1.json
python3 -m unittest discover -s tests/research -q
python3 -m unittest discover -s tests/chat -q
```

Para repetir, escolher novos nomes de saída; o programa não sobrescreve evidências. Na execução de desenvolvimento foram aprovados 35 testes de pesquisa independentes escritos pelo QA e 57 regressões do chat. O relatório QA registra a verificação final, incluindo eventuais testes acrescentados depois desta execução.

## 2. Resultados observados

| Comparador | Desenvolvimento: acertos /120 | Validação: acertos /120 | Intervalo 95% de validação por sementes | Planos sem apoio em validação |
| --- | --- | --- | --- | --- |
| Memória sem inferência | 80 (66,67%) | 80 (66,67%) | [66,67%;66,67%] | 0 em 40 planos |
| Busca simbólica programada | 120 (100%) | 120 (100%) | [100%;100%] | 0 em 80 planos |
| Frequência por ação, sem estado atual | 45 (37,50%) | 29 (24,17%) | [18,33%;30,00%] | 58 em 70 planos |

Em validação, a memória acertou as 40 consultas diretas e reconheceu os 40 casos insuficientes; não resolveu as 40 composições. A busca resolveu as 80 tarefas respondíveis e reconheceu os 40 casos insuficientes. A referência de frequência acertou 12 consultas diretas e 17 casos insuficientes; não resolveu composições.

Os intervalos degenerados da memória e da busca refletem comportamento idêntico entre as dez sementes e classes balanceadas do gerador. Não são garantia de 66,67% ou 100% em perguntas reais, em outro gerador ou em qualquer distribuição externa. O intervalo da frequência é um resumo descritivo deste piloto, com somente dez grupos.

A diferença pareada de busca−memória foi **33,33 pontos percentuais**, atribuível ao operador de composição que nós programamos. Isso confirma o funcionamento do controle de engenharia; não demonstra que o núcleo aprendeu uma regra nova. O fraco desempenho de uma frequência que ignora o estado não permite concluir superioridade geral sobre métodos estatísticos ou neurais.

Não houve saída inválida ou orçamento esgotado nas execuções oficiais. Em validação, as contagens de operações foram 847 (memória), 1.600 (busca) e 1.283 (frequência). Os tempos totais dentro dos comparadores foram aproximadamente 0,0005 s, 0,0064 s e 0,0067 s, respectivamente. Medem apenas execução dessas funções pequenas, não geração, QA ou tempo de pesquisa; as divisões foram executadas em processos simultâneos, portanto não usar essas durações como comparação precisa de desempenho computacional.

## 3. Decisões do registro de hipóteses

- **H00-01:** controle de encadeamento aprovado no escopo definido. Manter BFS como referência programada e memória como controle de consulta. Próximas alegações de aprendizado precisarão de um aprendiz que altere operadores/modelos, de novos estados e de reserva apropriada.
- **H00-02:** referência sem estado mostrou perda de informação e respostas sem sustentação nesta tarefa. Manter como diagnóstico fraco; antes de alegar ganho sobre estatística, incluir uma referência que condicione no estado e tenha capacidade/orçamento adequados.
- **H01-01, H04-01, H05-01, H06-01, H08-01, H09-01:** ainda não testadas. Não houve implementação de separação semântica do chat, aprendizado neural próprio, física, quântica ou consolidação de pesos na F00.

O protocolo reservado permanece sem pontuação. A infraestrutura agora permite começar F01 com um controle inicial explícito, mas seu desempenho atual não comprova independência do chatbot em relação ao Qwen.

## 4. Correções durante QA

1. O gerador inicial variava principalmente nomes. Antes da pontuação oficial, foram introduzidos operadores repetidos/distintos e cadeias/ciclos distratores, com teste de assinaturas que ignora nomes. A pequena quantidade de estruturas continua declarada como limitação.
2. O avaliador inicial lançava exceção com `status=[]` e podia abortar com retornos não dicionários. QA reproduziu o problema; o desenvolvedor corrigiu validação, contabilização de erros e serialização de NaN/objetos incompatíveis. Casos malformados agora são falhas medidas, sem desaparecer do denominador.
3. Revisão documental distinguiu testes do construtor com sementes QA de abertura do conjunto reservado oficial; corrigiu também espaçamento e referências.

Essas correções de engenharia não foram escolhidas a partir de respostas do reservado. O registro anterior à pontuação inclui os hashes da versão corrigida; o relatório de QA contém comandos, testes e aceite independente.
