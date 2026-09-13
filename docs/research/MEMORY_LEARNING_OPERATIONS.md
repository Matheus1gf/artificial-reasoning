# Memória, aprendizado contínuo e operação do laboratório

Implementação de F03, F09 e engenharia transversal F11, em 08/09/2026. O aceite de cada requisito é independente e está em [F01_F11_QA.md](F01_F11_QA.md). Os limites abaixo fazem parte da capacidade entregue.

## Dois bancos, responsabilidades explícitas

O histórico e as triplas anteriores continuam no banco `memory.sqlite3`. O `ChatEngine` cria, no mesmo diretório, `memory.cognition.sqlite3`, administrado por [ExperienceStore](../../src/cognition/store.py). Nenhuma migração da memória tipada altera as tabelas antigas. Experimentos e testes usam diretórios temporários próprios; não leem conversas pessoais.

O esquema 2 contém registros tipados, dependências, eventos de revisão e versões de modelos. Há tipos para entidade, atributo, relação com vários argumentos, evento, estado, regra, equação, ação, objetivo, procedimento, modelo, experimento e episódios. Cada registro guarda origem, fontes, escopo, data, versão, predecessora e tempo de validade opcional. Restrições de domínio ficam no conteúdo tipado de regras, modelos e experimentos; não são inferidas de uma confiança numérica.

`conversation`, `user` e `laboratory` têm significados distintos. A primeira memória só é recuperável na conversa correspondente; a segunda acompanha o proprietário entre conversas; a terceira representa dados de laboratório compartilháveis. A aplicação HTTP atual é **local e pessoal**, com o proprietário `local`. Os testes de separação entre proprietários na biblioteca não constituem autenticação de vários usuários. O legado compartilhava conhecimentos entre conversas e mantém essa semântica; dados novos não devem ser promovidos a um escopo mais amplo por uma mensagem ingerida.

`import_claims(snapshot)` permite importar uma fotografia das triplas antigas, de forma idempotente, com referências `M#` e origem preservada. Isso é um adaptador inicial explícito; repetir importações não é um mecanismo de sincronização de correções. O chat registra novos episódios e relações na memória tipada, e invalida suas consequências quando uma premissa `M#` é retirada ou entra em conflito.

## Evidência, recuperação e revisão

Uma afirmação do usuário permanece `asserted`; hipótese gerada permanece `hypothesis`, ou pode ser retirada/em disputa. Atribuir uma pontuação alta não a torna `verified`. O estado verificado só pode ser gravado pelo caminho interno de observação, experimento ou dedução com fontes. Não existe endpoint público para uma mensagem declarar que verificou a si mesma.

As dimensões de incerteza são separadas: qualidade de extração, credibilidade de fonte, probabilidade de evento e validade de derivação. `null` significa não estimado. Não se deve interpretar esses campos como probabilidades calibradas quando nenhum procedimento de calibração os produziu.

A recuperação combina tipos, objetivos, padrões estruturais com variáveis compartilhadas e um vocabulário declarado de predicados equivalentes. Texto auxilia a seleção. Não há embeddings treinados nesta memória, nem compreensão semântica geral. A correspondência de uma ação com um objetivo não prova que suas pré-condições sejam satisfeitas.

Corrigir uma premissa cria uma versão nova e retira transitivamente as consequências antigas. Conflitos só são comparados no mesmo contexto lógico e período. A retirada alcança registros que representam regras e planos e também versões de pesos dependentes dos dados de treino **ou da avaliação que autorizou sua adoção**. Revisão e seus efeitos usam uma transação; operações aninhadas usam savepoints.

## O que acontece a cada interação

O processador classifica a mensagem antes de qualquer redator. O chat registra a experiência e atualiza o contexto e as afirmações que conseguiu extrair. Perguntas, preferências, hipóteses e correções não se tornam automaticamente novos fatos verificados. Conteúdo produzido pelo organizador não retorna como fonte de aprendizado.

Treinamento é um processo separado. [consolidate_model](../../src/cognition/learning.py) recebe uma política explícita da aplicação: consentimento para os dados selecionados, protocolo, ganho mínimo, erro máximo e esquecimento tolerado. O texto de uma conversa não altera essa política, nem as permissões ou o código do verificador.

O controlador seleciona observações/experimentos verificados com procedência. Dados de treino, validação e retenção precisam ser disjuntos por identificador **e conteúdo numérico**; renomear uma amostra ou trocar `1` por `1.0` não permite vazamento. O treinador recebe apenas cópias das amostras de treino. A aplicação executa a avaliação, registra o resultado e só ativa o candidato se os critérios de ganho e retenção passarem. Uma versão rejeitada fica registrada como tentativa, sem substituir a versão ativa.

Essa função aceita aprendizes numéricos do próprio projeto. Seu piloto usa regressão linear modular; a presença do controlador não é evidência de treino neural. Os experimentos de redes próprias possuem dados, pesos e avaliação separados na frente cognitiva/científica.

## Piloto reproduzível de estabilidade

Protocolo: [protocol.v1.json](../../experiments/learning/protocol.v1.json). Registro anterior ao ajuste e relatório: [pilot.v3](../../experiments/learning/results/pilot.v3/report.json). Execução:

```sh
python3 scripts/evaluate_learning.py --output /tmp/ar-learning-pilot-novo
```

O diretório de saída precisa ser novo. O script registra configuração e hashes antes de treinar, usa SQLite temporário e preserva falhas em relatórios. Não usa Qwen, rede, conversas pessoais nem o conjunto científico reservado F00.

Foram executadas cinco sementes em três condições, com quatro exemplos de treino por tarefa. Identificação de tarefa e hipótese linear são fornecidas; coeficientes são aprendidos das observações. Validação e retenção usam valores não apresentados ao aprendiz.

| Condição | Nova tarefa | Capacidade anterior | Decisão observada |
| --- | --- | --- | --- |
| Treinar apenas a nova tarefa, zerando a anterior | Erro quadrático médio zero | Esquecimento acima do limite | Rejeitada nas 5 sementes |
| Repetir experiências das duas tarefas | Erro quadrático médio zero | Erro quadrático médio zero | Adotada nas 5 sementes |
| Preservar o módulo anterior e ajustar o novo | Erro quadrático médio zero | Erro quadrático médio zero | Adotada nas 5 sementes |

Nas 15 execuções, a reversão recuperou os pesos anteriores, a restauração recuperou registros e modelo ativo, a retirada desativou o modelo dependente e a exclusão explícita removeu suas versões de pesos. Um caso adicional mudou o coeficiente gerador de `2` para `-3`: observações obsoletas foram explicitamente retiradas, a versão dependente foi desativada e um candidato atualizado passou na avaliação do novo contexto. A informação de que o domínio mudou foi fornecida; detecção autônoma de mudança não foi demonstrada.

Tempo local de v2: aproximadamente 0,36 s. A execução v3 da retomada levou aproximadamente 0,76 s e registrou os hashes dos fontes atuais antes do ajuste; os cinco critérios voltaram a passar. Não é uma estimativa de custo de treinamento geral. O relatório v1 foi preservado: seu critério de restauração comparava também a hora de exportação e produziu uma falha no avaliador. Em v2, o critério compara os registros persistidos e os modelos, mantendo os timestamps da memória e desconsiderando apenas o instante em que cada exportação foi solicitada.

## Exclusão e reversão

`retract` retira apoio e desativa versões dependentes; mantém histórico para auditoria. `forget` remove conteúdo do registro e seus dependentes e apaga os pesos das versões afetadas. Isso não demonstra remoção seletiva de conhecimento de uma rede mantendo os demais pesos: a estratégia é descartar a versão afetada e retreinar com fontes permitidas. Reverter para uma versão com fonte retirada é proibido.

Backup, exportações já baixadas, relatórios científicos e histórico do banco antigo são arquivos distintos. Excluir um registro do sidecar não apaga essas cópias. A resposta da operação declara a necessidade de tratar backups e eventual retreinamento; o operador precisa identificar e remover as cópias pertinentes. Não há promessa de apagamento seguro de setores do disco ou de sistemas externos.

## Backup, migração e ferramentas locais

A migração 1 → 2 cria um backup SQLite consistente antes de alterar o esquema. Backup usa a API online do SQLite e `integrity_check`; restauração exige destino novo, valida versão/integridade e abre a origem em modo somente leitura. O teste de restauração faz parte da suíte independente. Bancos desconhecidos, incluindo o banco de chat, são recusados pelo migrador do sidecar.

```sh
python3 scripts/manage_cognition.py --database /caminho/memory.cognition.sqlite3 backup /caminho/backup-novo.sqlite3
python3 scripts/manage_cognition.py --database /caminho/backup-novo.sqlite3 restore /caminho/restaurado-novo.sqlite3
python3 scripts/manage_cognition.py --database /caminho/memory.cognition.sqlite3 export /caminho/exportacao-nova.json
python3 scripts/manage_cognition.py --database /caminho/memory.cognition.sqlite3 forget E-identificador
```

A interface oferece exportação de histórico/conhecimentos/experiências e backup de experiências/modelos. O escopo de cada ação aparece na interface. O backup do sidecar contém pesos; a exportação JSON de experiências não é um substituto para ele.

## Execução, cancelamento e isolamento

Compreensão, resolução, simulação e organização textual ficam fora das transações de escrita do histórico. As transações persistem o início do envio e, depois, a resposta pronta. O identificador do envio permite repetir uma tentativa, inclusive concorrente, sem criar outra resposta. Uma interrupção conserva o problema estruturado original para retomada.

O servidor admite até oito envios em execução/espera; o núcleo serializa seu processamento. `POST /api/chat/cancel` solicita cancelamento cooperativo por identificador. A execução observa esse sinal entre etapas; uma chamada síncrona de provedor pode terminar somente ao responder ou atingir seu timeout. Progresso NDJSON é separado do conteúdo: somente uma resposta verificada e persistida chega ao fluxo de texto.

[execute_program](../../src/cognition/sandbox.py) executa uma linguagem numérica limitada em processo separado. São permitidas operações de pilha, variáveis numéricas e repetições com orçamento. Não há execução de Python fornecido pelo usuário, `eval`, importação, acesso a arquivos ou rede no idioma aceito. O processo tem timeout, limite de passos e pilha, tamanho de entrada e números finitos. Linux usa também limite de espaço de endereçamento; macOS usa os limites explícitos do idioma e do processo, sem alegar a mesma garantia de limite de memória virtual. Programas Python arbitrários não são suportados por esse isolamento.

O pacote registra tempos de compreensão, memória, raciocínio/verificação e redação, operações, chamadas ao modelo e hash do conteúdo aprovado. Os experimentos reportam consumo máximo de memória do processo, cuja unidade depende da plataforma. São medições locais; a aplicação não estima custos monetários de provedores sem informações de cobrança.

## Responsabilidades e próximos critérios

| Frente | Responsável nesta implementação | Revisão requerida antes de ampliar afirmações |
| --- | --- | --- |
| Contratos, linguagem própria, operadores, redes e invenção | Agente desenvolvedor de IA | Engenheiro de ML e especialista em lógica; generalização fora do corpus controlado |
| Memória, consolidação, isolamento, API e interface | Agente coordenador/desenvolvedor | Engenharia de dados, sistemas e privacidade antes de múltiplos usuários |
| Física, quântica e descoberta numérica | Agente desenvolvedor científico | Físico e estatístico independentes; dados e experimentos externos |
| Testes adversos, regressões e aceite item a item | Agente QA independente | QA verifica software; não substitui parecer científico humano |
| Parecer científico, comparadores, incerteza e novidade | Agente especialista independente `scientific_reviewer` | Revisão por IA autorizada e realizada; independência de função, sem credenciais humanas ou replicação empírica externa |

### Estimativa preliminar após os pilotos

O piloto de estabilidade levou cerca de 0,36 s, o científico completo cerca de 3,8 s e o primeiro treino de intenção 1,7 s por execução na semente 17. Isso dimensiona somente essas cargas pequenas. O principal custo previsto do próximo ciclo é formular tarefas, anotar dados, investigar falhas e revisar pressupostos. As faixas abaixo são **estimativas de planejamento em horas de trabalho**, não tempos de CPU, trabalho já realizado, orçamento contratado ou promessa de prazo. Pressupõem uma pessoa qualificada, o código atual disponível e um ciclo de implementação/revisão; imprevistos de dados podem exigir reestimativa.

| Próximo incremento delimitado | Estimativa de trabalho | Hipótese e critério para reestimar |
| --- | --- | --- |
| F01/F11: endurecer operação e ampliar regressões do protocolo atual | 24–40 h | Sem novos provedores nem multiusuário; medir após primeiro ciclo de falhas |
| F02: anotar mais 1.000 enunciados e integrar avaliação de cobertura | 52–106 h | 2–4 min por anotação = 33–67 h; segunda revisão de 10% = 3–7 h; engenharia 16–32 h. Medir os primeiros 100 antes de continuar |
| F03/F09: três novos cenários de revisão/retirada/mudança de contexto | 8–16 h | Reutilizar controlador existente; reestimar se exigir remoção seletiva de informação dentro de pesos |
| F04/F05/F07: três famílias novas de operadores com falhas e comparadores | 32–64 h | Operadores e verificadores pequenos, sem generalização irrestrita; medir a primeira família antes das demais |
| F06: integrar uma trajetória medida e executar transferência | 8–16 h após aquisição | Pressupõe dados com interpretação/uso permitidos; prazo de aquisição não estimado enquanto a fonte não estiver qualificada |
| F08: uma classe nova de ruído/contexto com controle clássico | 16–32 h, mais 4–8 h de revisão especializada | Simulação pequena em CPU; qualquer necessidade de hardware exige novo protocolo e orçamento |
| F10: ampliar busca/dossiê de uma proposta delimitada | 16–40 h, mais 4–8 h de parecer especializado | Não inclui coleta física nem agendamento do avaliador; novidade científica permanece em aberto |

Treinamento maior exige um ensaio de escala antes de estimar CPU, RAM ou compra de hardware. Não extrapolamos linearmente o tempo do MLP pequeno para modelos de linguagem. As faixas se sobrepõem em competências e não formam um prazo total do projeto.

A revisão especializada seguiu o [briefing verificável](SPECIALIST_REVIEW_BRIEF.md) e foi realizada pelo agente independente `scientific_reviewer`. O [parecer científico por IA](SCIENTIFIC_REVIEW_AI.md) verificou pressupostos, fontes, contas físicas e quânticas, comparadores e resultados cognitivos; avaliou explicitamente utilidade e novidade. Os achados documentais foram tratados e encaminhados ao QA. Nenhum parecer humano externo foi obtido. **F10-05 e F10-07 permanecem abertos** por ausência, respectivamente, de competência demonstrada para promover uma proposta a problema aberto e de replicação científica com dados ou medições independentes pertinentes.

### Revisão por agente autorizada na retomada

Em 12/09/2026, o usuário solicitou um agente especialista independente para revisar o dossiê. A revisão foi concluída em função separada da autoria e da validação de software. Seu parecer é favorável à qualidade do dossiê no escopo declarado, incluindo os resultados negativos; não encontrou demonstração de novidade científica ou superioridade neural/quântica. A participação efetiva do especialista por IA atende ao escopo de revisão autorizado para F10-06/F11-08, sujeito ao aceite independente de QA. Revisão humana por pares e nova medição continuam sendo evidências distintas.
