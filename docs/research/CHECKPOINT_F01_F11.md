# Checkpoint de pausa — F01 a F11

**Pausado por solicitação do usuário em 08/09/2026 às 23:49 (America/Sao_Paulo).** Não retomar automaticamente. Agentes interrompidos e servidor temporário de testes da porta 8766 encerrado. Código e evidências permanecem no workspace, sem commit nesta execução.

## Estado confirmado

A matriz de QA contém **59 PASS, 18 ainda sem aceite final e 5 parciais**, nos 82 requisitos de F01–F11. O TODO foi sincronizado exclusivamente com os PASS. Somando os oito itens F00 anteriores, são **67 de 90 itens marcados com X**. Isso descreve conclusão dos requisitos no escopo declarado, não um percentual de inteligência ou de avanço científico geral.

| Fase | Itens com aceite / total |
| --- | --- |
| F01 | 7 / 7 |
| F02 | 6 / 7 |
| F03 | 7 / 7 |
| F04 | 8 / 8 |
| F05 | 0 / 8 |
| F06 | 7 / 8 |
| F07 | 0 / 7 |
| F08 | 8 / 8 |
| F09 | 7 / 7 |
| F10 | 4 / 7 |
| F11 | 5 / 8 |

## Ponto exato de retomada

1. **F02-06:** o MLP próprio está treinado e seu checkpoint foi integrado ao processador como proposta experimental (`adopted=False`). Falta o QA concluir a validação dessa integração e sua documentação/aceite. Corpus e métricas já têm testes específicos: 150 exemplos de treino; 50 casos com templates/entidades separados; três sementes com 58%, 62% e 68% na avaliação não vista, contra 100% no treino. Não promover o classificador a autoridade semântica com esse resultado.
2. **F05-01 a F05-08:** continuar operadores aprendidos, avaliações de poucos exemplos/ruído/transferência/seleção ativa/ablações e relatório. `src/cognition/operators.py` foi criado imediatamente antes da pausa: possui rede de transição, ajuste, escolha de exemplo, síntese e programa DSL, mas **não possui aceite QA nem integração final comprovada**. Não marcar esses itens pelo simples fato de o arquivo existir.
3. **F07-01 a F07-07:** integrar invenção com operadores aprendidos ao núcleo e à memória; medir geração, diversidade, utilidade, custo, contraexemplos, revisão e reutilização de falhas. No instante da pausa, `invent` ainda usa o planejamento estruturado existente; isso não conclui todos os requisitos de invenção.
4. **F11-04:** `telemetry.py` tem três testes aprovados e `ChatEngine` já inclui `reasoning.resources`. Falta o QA validar a integração e registrar aceite final.
5. **F11-06:** CI inclui as quatro suítes, e há scripts/relatórios separados. Concluir reprodução e revisão final após finalizar os módulos cognitivos/invenção, sem confundir teste de software com resultado de modelo ou descoberta científica.
6. **F06-08:** a busca por trajetória física pública e medida foi iniciada e interrompida na pausa. Nenhum dataset de transferência foi aprovado pelo QA. Exige posição/tempo, unidades, condições e incerteza suficientes; não usar dados sintéticos nem NIST de outro domínio como substituto.
7. **F10-05/06/07:** permanecem sem problema aberto validado, sem parecer externo de novidade/utilidade e sem replicação com novos dados/medições independentes.
8. **F11-08:** responsáveis, competências, estimativas preliminares e briefing de revisão foram preparados. O QA manteve PARCIAL porque nenhum revisor externo foi efetivamente envolvido. O briefing não é parecer obtido nem contato enviado.

## Arquivos e evidências para continuar

- [TODO principal](../../TODO.md) e [matriz de QA independente](F01_F11_QA.md).
- [Arquitetura](../CHATBOT_ARCHITECTURE.md), [validação atual](../CHATBOT_VALIDATION.md), README e roadmap atualizados para núcleo próprio antes do Qwen.
- [Memória/aprendizado/operação](MEMORY_LEARNING_OPERATIONS.md), [briefing de especialista](SPECIALIST_REVIEW_BRIEF.md), `src/cognition/store.py`, `learning.py`, `sandbox.py` e `telemetry.py`.
- Rede/corpus/protocolo/checkpoint em `experiments/cognition/`; script `scripts/train_cognition.py`; fontes `neural.py`, `datasets.py`, `processor.py` e novo `operators.py`.
- Ciência: [relatório v5](../../experiments/science/results/pilot.v5.json), [registro v5](../../experiments/science/registration.v5.json), [estado por item](SCIENCE_STATUS.md). QA aprovou 34 testes científicos e conferiu 20 hashes. Mudanças em fontes cobertas, inclusive sandbox, exigem novo registro/relatório sem apagar o anterior.
- Aprendizado contínuo: `experiments/learning/results/pilot.v2/` reproduziu 15 condições e cinco decisões. Seu registro corresponde àquela versão dos fontes; alterações posteriores do Store exigem nova execução/registro antes de anunciar correspondência com o código final. `pilot.v1` preserva a falha histórica do avaliador de restauração.

## Últimas verificações registradas

- Snapshot integrado de cognição: 86 testes aprovados antes dos novos testes de corpus/telemetria; depois houve três testes de cada um desses módulos. **Não somar isso como uma nova execução completa sobre a árvore final.**
- Chat/HTTP: 60 testes aprovados no ciclo de QA registrado.
- Ciência: 34 testes aprovados. F00: 35 regressões aprovadas, reservado oficial sem pontuação.
- Root retomou `test_store.py`: 25 testes aprovados após correção de booleano versus número em variáveis repetidas.
- Browser real em dados temporários: cálculo 2m+30cm; desconhecimento específico ao trocar para buraco de minhoca; correção de dedução sobre cobre; simulação com x=0,v=2,a=1,dt=1.5 retornou4.125m e3.5m/s; evidências e modo pesquisa funcionando. QA independente verificou HTTP/assets; a superfície gráfica estava disponível somente ao integrador.
- A árvore final, com `operators.py` recém-criado, **ainda não passou por rodada completa de QA**. Nenhuma verificação adicional foi iniciada após o pedido de pausa.

## Como retomar com os agentes

- Desenvolvedor IA: `/root/f00_developer` — F02-06, F05 e F07, mais integração final de telemetria.
- QA independente: `/root/f00_qa` — testes, defeitos enviados ao autor, retestes e matriz individual.
- Desenvolvedor científico: `/root/science_developer` — prospecção interrompida de trajetória medida F06-08; demais itens científicos já aprovados conforme matriz.
- Integrador: manter TODO/documentação coerentes; só adicionar X quando houver PASS explícito do QA.

Retomar agentes existentes se disponíveis, ou recriar papéis a partir deste checkpoint. Não assumir que processos/background sobreviveram. O preview foi encerrado; para abri-lo novamente sem acessar conversas pessoais:

```sh
python3 main.py --data-dir /tmp/ar-f01-f11-preview-20260908 --port 8766
```

O diretório temporário contém apenas dados de teste desta execução e pode ser limpo pelo sistema operacional. As fontes e relatórios estão no repositório. Não utilizar o conjunto reservado da F00, não baixar Qwen para pesquisa e não iniciar comunicação externa com especialistas sem autorização específica.

## Retomada posterior — 12/09/2026 às 22:07

O usuário autorizou continuar. Este documento permanece como fotografia da pausa; o estado corrente passa a ser o TODO e a matriz de QA. Os agentes anteriores não estavam ativos e foram recriados nos papéis `/root/cognition_developer`, `/root/qa_specialist` e `/root/science_specialist`. A regressão inicial registrou 222 testes aprovados.

## Fechamento da retomada — 12/09/2026 às 22:19

Este checkpoint anterior permanece histórico. A retomada terminou com **88/90 itens aprovados** (80/82 em F01–F11, mais F00), 254 testes aprovados, reprodução cognitiva v4, ciência v7 e aprendizado contínuo v3. Os fontes e o protocolo F00 conservaram seus hashes; o conjunto reservado não foi pontuado.

O usuário autorizou a revisão por agente especialista, realizada em [SCIENTIFIC_REVIEW_AI.md](SCIENTIFIC_REVIEW_AI.md) e aprovada pelo QA após tratamento dos achados. F10-06/F11-08 receberam aceite com essa identificação explícita; não houve revisão humana por pares ou nova medição independente.

**Restam F10-05 e F10-07**, pelos motivos e próximos critérios descritos no [TODO atual](../../TODO.md). F05/F07 estão integrados, testados e documentados em [COGNITION_OPERATORS.md](COGNITION_OPERATORS.md) e [COGNITION_RESULTS.md](COGNITION_RESULTS.md). O fluxo visual de aprendizagem, aplicação, invenção e contraprova passou, incluindo persistência após reinício e rejeição de uma família refutada. Servidor e aba temporários foram encerrados. Nenhum commit foi criado nesta execução.
