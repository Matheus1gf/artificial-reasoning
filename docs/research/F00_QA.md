# F00 — Validação independente de QA

Data: 08/09/2026, America/Sao_Paulo. Escopo: F00-01 a F00-08 de [TODO.md](../../TODO.md). Base anterior: `d2c32a33171819a25ba7b896991647019cac1ffb`.

**Aceite final: PASS nos oito itens da F00.** O desenvolvedor implementou e corrigiu os artefatos; o agente QA escreveu testes independentes, revisou a especificação e reexecutou a regressão. O integrador pode marcar `[X]` nos oito itens com os vínculos de evidência abaixo.

Este aceite demonstra uma especificação verificável e uma avaliação inicial executável. Não demonstra raciocínio geral, invenção científica, treinamento de redes próprias ou independência do chatbot atual em relação ao Qwen.

## 1. Aceite por item

| Item | Verificação independente e evidência | Resultado |
| --- | --- | --- |
| F00-01 | Revisão de [F00_SPEC.md](F00_SPEC.md), seção 1: sete capacidades com definição operacional, tarefa/artefato observável e falha; compreensão de português está explicitamente fora do instrumento estruturado atual | **PASS** |
| F00-02 | [F00_AUDIT.md](F00_AUDIT.md) confrontado com código: extração `complete`, geração `chat`, teste de conexão `complete`, transportes, legado, vocabulário, gramática, pares fixos e limites auditados | **PASS** |
| F00-03 | [F00_SPEC.md](F00_SPEC.md), seção 2: dados e métricas de L1/L2/L3/L4; a regressão demonstra contratos delimitados de persistência/revisão, sem alegação de aprendizado geral de regras | **PASS** |
| F00-04 | [test_worlds.py](../../tests/research/test_worlds.py): famílias diferentes, variação real de regras, guardas, nomes, RNG, isolamento e gabaritos conferidos por enumeração independente em 162 configurações | **PASS** |
| F00-05 | [F00_PROTOCOL.md](F00_PROTOCOL.md), seção 3: sete referências e seus priors/status; teste de igualdade das entradas dos três comparadores executados; referências não aplicáveis/futuras sem pontuação inventada | **PASS** |
| F00-06 | [Protocolo JSON](../../experiments/f00/protocol.v1.json), [registro anterior](../../experiments/f00/registration.v1.json), [test_evaluation.py](../../tests/research/test_evaluation.py) e relatórios: schema, limites, denominadores, abstenção, bootstrap, falhas, CLI e hashes | **PASS** |
| F00-07 | [F00_HYPOTHESES.md](F00_HYPOTHESES.md): oito hipóteses com mecanismo, previsão, alternativa, refutação e decisão; H00-01/H00-02 limitadas ao controle inicial, seis seguintes ainda não testadas | **PASS** |
| F00-08 | [F00_RESOURCES.md](F00_RESOURCES.md) confrontado com coleta local: M4, 24 GiB, Python 3.9.6, disco/serviços como instantâneos; domínio discreto delimitado, movimento uniforme 1D eleito e lacunas/custos identificados | **PASS** |

Itens de especificação foram validados por revisão técnica de conteúdo e correspondência com o código. Testes de software verificam o instrumento F00; não substituem os experimentos de capacidades ainda previstos nas outras fases.

## 2. Execuções e resultados

Ambiente local: Python 3.9.6, macOS arm64. Comandos executados pelo QA:

```sh
python3 -m unittest discover -s tests/research -v
python3 -m unittest discover -s tests/chat -v
python3 -m compileall -q src/research scripts/evaluate_f00.py tests/research
git diff --check
```

- **35 testes de pesquisa aprovados**, após correções e retestes.
- **57 testes do chat aprovados** antes e depois da implementação F00.
- **92 testes ao todo**, sem falhas na execução final local.
- Compilação e verificação de espaços do diff aprovadas.
- Testes de CLI executam `scripts/evaluate_f00.py` a partir de outro diretório, com protocolo próprio e saída temporária; verificam JSON válido, recusa de sobrescrita e bloqueio do reservado.
- A configuração de CI inclui Python 3.9/3.12; os resultados acima são locais em Python 3.9.6, não uma alegação de execução remota da CI.

QA leu os dois relatórios oficiais e recomputou contagens diretamente de suas linhas, sem usar a função de agregação do avaliador:

| Divisão | Episódios | Execuções de comparador | Memória | Busca simbólica | Frequência |
| --- | --- | --- | --- | --- | --- |
| Desenvolvimento | 120 | 360 | 80/120 | 120/120 | 45/120 |
| Validação | 120 | 360 | 80/120 | 120/120 | 29/120 |

Acertos incluem reconhecer corretamente evidência insuficiente. Em validação, a busca responde 80 casos e se abstém corretamente em 40; a memória responde 40, se abstém corretamente em 40 e deixa de resolver 40 composições. A referência de frequência emite 58 planos sem apoio dentre 70 respostas. Os relatórios oficiais não tiveram saídas inválidas nem estouro de orçamento.

Totais, hashes do protocolo e quatro arquivos de código foram conferidos contra os arquivos efetivos. O registro anterior à pontuação e o manifesto vinculam os artefatos; são registros versionados de procedimento, não garantia de custódia independente. Fontes e resultados estão em [F00_RESULTS.md](F00_RESULTS.md).

## 3. Cobertura que sustenta o aceite

- **Gabarito independente:** enumeração dos planos de comprimento zero, um e dois — 21 possibilidades por caso — em 162 configurações de desenvolvimento/validação, com sementes QA, índices e orçamentos de 4, 8 e 16 exemplos. A implementação de QA não chama a BFS para obter a resposta.
- **Diversidade e contexto:** assinaturas de grafos invariantes a renomeação detectam variação de regras; transições de validação demonstram dependência do estado do outro objeto. IDs não se repetem nos mundos QA verificados.
- **Reprodução:** igualdade entre subprocessos com `PYTHONHASHSEED=1`, `234` e `random`; o gerador preserva o RNG global.
- **Incerteza:** dois mundos determinísticos compatíveis com as mesmas observações podem discordar sobre o resultado oculto. Acertar casualmente o oracle não basta sem sustentação observável.
- **Isolamento:** o público não carrega sementes, família, tipo, índice, gabarito ou tabela oculta. Cópias profundas são independentes; os três comparadores recebem a mesma evidência e sua mutação é detectada.
- **Execução offline:** avaliação realizada com `socket.socket` bloqueado por teste; nenhum provedor é inicializado. A suíte HTTP do chat utiliza somente seu servidor local temporário e respostas simuladas de modelo.
- **Saídas adversas:** `None`, listas, status não hashable, campos extras, operações inválidas, NaN e exceções são falhas contabilizadas, preservando denominador e serialização JSON.
- **Métricas e orçamento:** sucesso apoiado, abstenção correta, resposta disponível perdida e orçamento esgotado são distintos. Excesso de operações ou tempo pós-retorno impede acerto. Bootstrap valida valores finitos e reprodução por semente.
- **Protocolo/CLI:** limites/tipos inválidos, sementes repetidas dentro/entre divisões, família incorreta, campos faltantes/extras e versão incompatível são detectados. Arquivo de evidência existente é preservado.

## 4. Proteção da avaliação reservada

As sementes oficiais reservadas do protocolo não foram usadas para gerar episódios, ajustar comparadores ou medir capacidades. `run_evaluation` e a CLI recusam a divisão `reserved`, e isso é testado antes de qualquer geração.

O ramo exclusivo do construtor `coupled_transfer` foi testado com sementes QA **23017, 91307 e 401287**, ausentes do protocolo científico. Em 18 construções, QA verificou valores inteiros não negativos, conservação da soma por transição, efeito sobre dois objetos, correspondência observações/oracle e cópia isolada. Esse teste não executa comparadores, calcula scores ou treina modelos. A especificação pública da família também não deve ser tratada, no futuro, como estrutura desconhecida dos desenvolvedores.

Os testes utilizam diretórios temporários. Não houve leitura da memória pessoal, inicialização de Qwen/Ollama ou alteração do comportamento do chat.

## 5. Defeitos, devolução ao desenvolvedor e reteste

| ID | Problema reproduzido | Correção pelo desenvolvedor | Evidência de reteste |
| --- | --- | --- | --- |
| QA-01 | Gerador inicial mantinha as mesmas quatro arestas efetivas; renomeação e distratores não demonstravam regras variáveis | Operador repetido/distinto e distratores em cadeia/ciclo introduzidos antes da pontuação oficial | Testes de assinaturas invariantes e guardas contextuais aprovados |
| QA-02 | `score_result(case, {'status': [], 'plan': [], 'operations': 0})` lançava `TypeError`; retornos não dicionários interrompiam o runner e NaN comprometia JSON | Validação de tipo, contabilização de erros, operações medidas separadamente e normalização para JSON | Testes de saídas malformadas, resultados inválidos, exceções e limites aprovados |
| QA-03 | Texto confundia ausência de avaliação reservada com ausência de testes do construtor; espaçamentos imprecisos | Sementes oficiais/QA distinguidas, revisão editorial e decisões atualizadas após os resultados | Revisão final de protocolo, hipóteses, recursos e resultados aprovada |

Nenhum defeito impeditivo permanece aberto na F00. A validade do aceite se limita à especificação, ao código e ao protocolo registrados. Compreensão própria, aprendizagem, redação fiel, física e quântica exigem experimentos e verificações das próximas fases; a pontuação da BFS não antecipa essas conclusões.
