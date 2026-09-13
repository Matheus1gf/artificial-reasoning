# Raciocínio Artificial

Laboratório conversacional de **compreensão, memória, raciocínio e aprendizado próprios**. A questão é processada pelo núcleo antes de qualquer modelo de linguagem. O núcleo produz um pacote verificável com conclusões, premissas, cálculos, hipóteses e limites. Um Qwen opcional pode organizar os trechos aprovados; não fornece fatos nem decide a conclusão do chat.

A implementação trabalha com português controlado e tarefas estruturadas de lógica, planejamento, cálculo, física e sistemas quânticos pequenos. Há aprendizes numéricos próprios e experimentos de generalização delimitados. **Não é ainda um chatbot de conhecimento geral equivalente ao ChatGPT, nem uma IA com descoberta científica autônoma comprovada.** Fora de sua cobertura, identifica a informação que falta em vez de completar a resposta com conhecimento do redator.

O repositório contém a aplicação conversacional, seus módulos de pesquisa e os recursos necessários para execução, treinamento e validação. O [TODO principal](TODO.md) registra o estado real de cada requisito, com aceite independente em [F01_F11_QA.md](docs/research/F01_F11_QA.md).

O [plano para o objetivo completo](docs/OBJECTIVE_PLAN.md) separa entregas de engenharia, capacidades demonstradas e contribuições científicas. O TODO detalha F13–F21 para dados, compreensão aprendida, descoberta de regras, investigação, invenção e aprendizagem contínua. Essas fases permanecem abertas; o número de itens concluídos não mede proximidade a inteligência geral.

## Executar sem Qwen

Requer Python 3.9 ou superior. O chat, os módulos de pesquisa e suas suítes usam a biblioteca padrão. Não há pacotes obrigatórios para instalar nem necessidade de baixar um modelo de linguagem.

```sh
python3 main.py
```

Abra [o chat local](http://127.0.0.1:8765). O **modo de pesquisa está ligado por padrão**, inclusive ao carregar configurações antigas que não continham essa opção: nenhuma chamada a modelos gerais é permitida e o Ollama não é iniciado por esse modo. `app.py`, `launcher.py` e `run_frontend.py` também iniciam o novo servidor. No Windows, use `python` se esse for o nome do interpretador.

```sh
# Terminal; digite /sair para encerrar
python3 main.py --cli

# Experimento separado das conversas pessoais
python3 main.py --port 8766 --data-dir ./data/chat-experimento
```

## Conversar e testar

| Mensagem | O que o núcleo pode verificar |
| --- | --- |
| `Todo cristal emite luz. Neral é um cristal.` | Registra premissas e aplica uma regra universal ao indivíduo, com fontes |
| `O que você sabe sobre Neral?` | Recupera conhecimento pertinente à entidade perguntada |
| `Corrigindo: todo cristal não emite luz.` | Revisa a premissa e retira consequências que perderam apoio |
| `Calcule 2 m + 30 cm` | Converte unidades e retorna 2,3 m |
| `Calcule 2 m + 3 s` | Reconhece incompatibilidade dimensional |
| `O que é um buraco de minhoca?`, sem premissas pertinentes | Explicita desconhecimento sobre esse conceito; não responde com o exemplo de buraco negro |

Referências como “isso” dependem do contexto desta conversa; múltiplos referentes geram esclarecimento. A gramática e os dados de avaliação delimitam a cobertura de linguagem. Aprender um fato não instala conhecimento geral sobre todos os assuntos relacionados.

Para testar geração de hipóteses em linguagem natural, envie na mesma conversa:

1. `Neral é um dispositivo que armazena energia.`
2. `Considerando que Vetra é o inverso de Neral, o que Vetra faria?`

O núcleo propõe **Vetra libera energia**, explicita a transformação e indica como investigá-la. Essa relação foi assumida somente nesta pergunta: não vira uma afirmação permanente. Para ensinar uma relação permanente, use `Vetra é o oposto de Neral.`; depois pergunte `O que é Vetra?`. `Vetra não é o oposto de Neral.` introduz uma contradição; `Corrigindo: Vetra não é o oposto de Neral.` revisa a relação e retira as hipóteses dependentes.

Para testar composição com uma meta, envie `Plorin converte luz em calor. Xaret converte calor em movimento.` e depois `Crie uma solução para transformar luz em movimento.`. O núcleo busca a cadeia **luz → calor → movimento**, identifica os componentes e confere as conexões. Essa proposta é nova em relação às duas premissas isoladas; o teste simbólico não demonstra eficiência, compatibilidade material ou viabilidade física.

Oposição e analogia produzem **hipóteses**, distintas de deduções lógicas. Os operadores e parte do vocabulário são programados; relações ensinadas, como `O oposto de filtrar é transportar.`, podem fornecer uma transformação que não estava no vocabulário inicial. Isso não significa aprendizado irrestrito de conceitos ou invenção científica autônoma. O [parecer sobre o raciocínio conversacional](docs/research/CONVERSATIONAL_REASONING_REVIEW.md) explicita esse alcance.

O laboratório também aceita pedidos JSON no campo de mensagem, por exemplo:

```json
{"domain":"physics","operation":"simulate","parameters":{"x":0,"v":2,"a":1,"dt":1.5}}
```

Esse caso usa movimento unidimensional com aceleração constante, nas unidades SI declaradas, e compara a integração com uma referência analítica. Consulte os [contratos científicos e exemplos](docs/research/SCIENCE_PROTOCOL.md) para ajustes de parâmetros, regressão simbólica, medições quânticas e busca de referências. Os operadores cognitivos recebem tarefas estruturadas como `deduce`, `plan`, `induce`, `abduce`, `analogy`, `causal`, `counterfactual` e `invent`; seus formatos e limites constam do [guia de operadores e invenção](docs/research/COGNITION_OPERATORS.md).

Para experimentar aprendizado de um mecanismo e composição, envie estas mensagens **na mesma conversa**, uma por vez:

```json
{"task":"learn_operator","name":"mecanismo_a","examples":[{"x":0,"y":1},{"x":1,"y":3}]}
```

```json
{"task":"apply_operator","name":"mecanismo_a","x":3}
```

```json
{"task":"invent","initial":0,"target":7,"operators":["mecanismo_a"],"max_steps":3}
```

O mecanismo é aprendido dentro de uma família afim explicitamente fornecida ao algoritmo. A sequência `0 → 1 → 3 → 7` pode ser composta e conferida em um programa numérico isolado. Os exemplos são premissas informadas pelo usuário; verificar a composição não confirma que o mecanismo exista no mundo físico. Para enviar uma observação que desafia a previsão e revisar suas consequências:

```json
{"task":"test_operator","name":"mecanismo_a","examples":[{"x":2,"y":8}]}
```

Esses valores conflitam com o modelo anterior. O resultado deve registrar a contraprova e retirar o apoio aos procedimentos dependentes. O [aceite independente de QA](docs/research/F01_F11_QA.md) indica o estado testado dessa integração.

**Ver evidências, verificações e limites** expande o pacote da resposta. A memória lateral mostra fontes, revisões e experiências. “Respondido” significa que o núcleo concluiu a operação dentro das premissas declaradas; não transforma uma afirmação do usuário em verdade científica.

## Papel do Qwen

O modo de pesquisa bloqueia o provedor em todas as etapas. Para experimentar um organizador, configure um modelo já disponível e desligue explicitamente essa opção em **Configurações**. A interpretação da mensagem e a inferência continuam no núcleo próprio.

O modelo recebe somente uma cópia dos trechos aprovados, com identificadores. Sua saída permitida é uma permutação desses identificadores: não pode acrescentar texto, excluir trechos, trocar números ou remover negações. Saída inválida, falha de conexão ou indisponibilidade levam à renderização determinística. Não há revisão pelo próprio Qwen usada como prova de fidelidade.

Essa restrição preserva o conteúdo e reduz a liberdade de estilo. Redação livre permanece fora do contrato enquanto não houver verificação semântica adequada. O streaming mostra progresso separado e só publica conteúdo depois da verificação e persistência.

| Organizador | Requisito | Dados recebidos |
| --- | --- | --- |
| Determinístico | Apenas Python | Nenhuma chamada a modelo |
| Ollama | Servidor e modelo instalado, com saída JSON | Trechos aprovados; mantém processamento local se o endereço for local |
| API compatível configurada | Credencial no ambiente, quando necessária | Trechos aprovados podem conter dados da conversa; o serviço pode cobrar |

`AR_PROVIDER`, `AR_MODEL` e `AR_BASE_URL` continuam disponíveis para configuração na inicialização. Essas variáveis não desligam o modo de pesquisa. O organizador opcional usa um servidor e modelo já disponíveis, configurados pela interface. Nenhum download de modelo é necessário para testar esta implementação.

## O que significa aprender

Cada envio válido vira uma experiência classificada. O contexto e o conhecimento extraído podem ser atualizados imediatamente. A origem, o escopo e a incerteza permanecem explícitos; hipóteses geradas e repetições de uma alegação não viram confirmação independente.

Treinar pesos é outra etapa: um controlador seleciona observações verificadas, exige uma política explícita, separa treino/validação/retenção, mede ganho e esquecimento e só então promove a versão candidata. Há reversão de versão e invalidação dos pesos quando suas fontes são retiradas. A conversa não pode conceder a si mesma autorização de treinamento ou alterar critérios de avaliação.

O [piloto de aprendizado contínuo](docs/research/MEMORY_LEARNING_OPERATIONS.md) compara repetição de experiências, preservação de módulos e aprendizado apenas da tarefa nova. A regressão modular desse piloto é distinta das redes treinadas na frente cognitiva e física. Registrar uma mensagem não significa atualizar uma rede neural a cada turno. Os [resultados de aprendizagem e invenção](docs/research/COGNITION_RESULTS.md) mostram as comparações, as falhas de generalização e por que as propostas neurais continuam opcionais.

## Organização e dados

```text
src/chat/                 Histórico, interface, HTTP e adaptadores opcionais
src/cognition/contracts.py   ProblemSpec e AnswerPackage imutáveis
src/cognition/processor.py   Compreensão própria antes da redação
src/cognition/engine.py      Núcleo que resolve e verifica o problema
src/cognition/reasoning.py   Operadores lógicos e busca limitada
src/cognition/store.py       Memória tipada, fontes, revisões e versões
src/cognition/learning.py    Avaliação e promoção controlada de aprendizes
src/cognition/neural.py      Rede própria de intenção, com proposta auditável
src/cognition/operators.py   Aprendizado de transições e composição de programas
src/cognition/operator_runtime.py  Integração dos operadores à conversa e às fontes
src/cognition/sandbox.py     Execução isolada de uma DSL numérica limitada
src/science/                Física, quântica e descoberta numérica
src/research/               Referências e protocolo inicial F00 congelados
experiments/                Configurações, corpus, registros e resultados
scripts/                    Treinamento, avaliação e administração do núcleo
tests/                      Regressões do chat, cognição, ciência e pesquisa
docs/                       Operação, arquitetura e evidências de validação
```

Os arquivos de `experiments/` incluem pesos carregados pelo núcleo, dados com origem verificada, protocolos usados pelos avaliadores e resultados que sustentam a documentação. Os registros anteriores permitem reproduzir e comparar experimentos, inclusive os que tiveram resultado negativo. Seus bytes são preservados pelo Git para não invalidar checksums ao trabalhar no Windows.

O histórico antigo fica em `memory.sqlite3`; o sidecar `memory.cognition.sqlite3` armazena as novas experiências e modelos. O servidor escuta somente em `127.0.0.1`. É um laboratório pessoal, sem contas ou autenticação multiusuário. Backups, exportação, restauração, escopos e os limites da exclusão estão documentados em [Memória, aprendizado e operação](docs/research/MEMORY_LEARNING_OPERATIONS.md). Para copiar a pasta inteira de dados, pare o servidor primeiro; o backup oferecido na interface cobre experiências e modelos, com escopo explícito.

## Testes e experimentos

Testes de software, avaliação de modelos e pesquisa científica têm resultados separados:

```sh
python3 -m unittest discover -s tests/chat -v
python3 -m unittest discover -s tests/cognition -v
python3 -m unittest discover -s tests/science -v
python3 -m unittest discover -s tests/research -v
```

A CI configura Python 3.9 e 3.12 no Linux e no Windows, com UTF-8 habilitado. Testes dos provedores usam respostas controladas para verificar contratos; não medem a capacidade geral do Qwen. Consulte [validação atual](docs/CHATBOT_VALIDATION.md) e a [matriz de QA](docs/research/F01_F11_QA.md) para resultados reproduzidos e requisitos ainda parciais.

```sh
# F00: avaliação inicial; o conjunto científico reservado não é pontuado
python3 scripts/evaluate_f00.py --split validation --output .runtime/f00-validation-novo.json

# Registrar fontes antes de rodar o piloto científico
python3 scripts/evaluate_science.py --register --output .runtime/science-registration-novo.json
python3 scripts/evaluate_science.py --output .runtime/science-pilot-novo.json

# Aprendizado contínuo: relatório e registro em diretório novo
python3 scripts/evaluate_learning.py --output .runtime/learning-pilot-novo
```

Os comandos recusam sobrescrever resultados. Experimentos usam sementes, registram limitações e preservam resultados negativos. Os [resultados científicos](docs/research/SCIENCE_RESULTS.md) incluem comparações em que o modelo clássico é equivalente ou melhor. Não foi demonstrada vantagem geral quântica, descoberta de uma lei nova ou inovação científica superior à humana.
