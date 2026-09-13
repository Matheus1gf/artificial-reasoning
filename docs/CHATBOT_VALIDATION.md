# Validação do núcleo próprio

A referência de aceite é a [matriz independente F01–F11](research/F01_F11_QA.md), que registra testes, defeitos, correções e requisitos ainda incompletos. A F00 mantém seu [relatório histórico de QA](research/F00_QA.md) e seu protocolo congelado. Os resultados de conversa livre anteriores à separação do Qwen foram preservados em [LEGACY_QWEN_VALIDATION.md](research/LEGACY_QWEN_VALIDATION.md); não representam o novo núcleo.

## Três níveis de evidência

| Nível | Verificação | Interpretação permitida |
| --- | --- | --- |
| Software | Testes de contratos, operações, memória, API, cancelamento e regressões | A implementação respeita os comportamentos cobertos |
| Aprendizes | Dados de treino e avaliação distintos, pesos próprios, métricas e comparadores | Ganho/erro no domínio e protocolo medidos |
| Pesquisa científica | Simulação, dados observados, análise de referências e replicação | Apenas as conclusões sustentadas por cada experimento; teste unitário não prova descoberta científica |

## Reprodução das suítes

```sh
python3 -m unittest discover -s tests/chat -v
python3 -m unittest discover -s tests/cognition -v
python3 -m unittest discover -s tests/science -v
python3 -m unittest discover -s tests/research -v
node --check src/chat/web/app.js
```

O servidor e os testes de backend usam a biblioteca padrão. Node é opcional para a checagem de sintaxe do JavaScript. A configuração de CI cobre Python 3.9/3.12; uma configuração de CI não deve ser confundida com uma execução remota já concluída.

O QA executa testes independentes, incluindo modelos falsos que tentam mudar o pacote, acesso a rede proibido no modo de pesquisa, fonte retirada, conflito, vazamento de amostra, versão que esquece tarefa anterior, plano inválido, orçamento, unidades incompatíveis e cancelamento real via HTTP. Uma alteração intencional do produto — como retornar desconhecimento sem base do núcleo — exige atualizar o contrato esperado, sem esconder regressões reais.

## Verificação manual da interface

Foi iniciado um servidor isolado na porta 8766, com dados em diretório temporário, sem ler conversas pessoais. Pela interface, foram observados:

- `Calcule 2 m + 30 cm` → 2,3 m, com evidências de conversão/validação, sete operações e zero chamadas ao organizador.
- Registro de premissas sobre metal/cobre, fontes `M#` e dedução visível na memória. O primeiro teste revelou uma falha no verificador: a ordem de IDs das premissas podia suprimir uma dedução válida. O defeito foi enviado ao desenvolvedor e coberto por regressão nas duas ordens de inserção.
- Mudança para “buraco de minhoca” → desconhecimento específico desse conceito, sem reaproveitar a resposta sobre cobre ou o exemplo de oposição.
- Expansão do pacote aprovado e dos episódios da conversa.
- Configurações exibindo modo de pesquisa ligado; teste de conexão confirmou funcionamento sem chamadas a modelos gerais.

No reteste visual após a correção, a pergunta sobre cobre incluiu a dedução condicional `cobre conduz eletricidade [M3]`. O pedido `physics/simulate` com `x=0`, `v=2`, `a=1`, `dt=1.5` retornou `4.125 m` e `3.5 m/s` na conversa, com o pacote de evidências disponível. Este smoke visual foi executado pelo integrador; o agente QA independente verificou API/contratos/assets e não teve superfície de navegador própria disponível.

A aparência da interface e a legibilidade do painel de evidências foram inspecionadas no navegador. A validação responsiva herdada não substitui uma auditoria completa de acessibilidade.

### Reteste da retomada — 12/09/2026

O integrador abriu novamente uma instância isolada na porta 8766, com diretório temporário novo, e executou pela interface as mensagens do README. Duas observações `(0,1)` e `(1,3)` identificaram o mecanismo condicional `2*x+1`. A aplicação em `x=3` produziu `7`; a invenção compôs `0 → 1 → 3 → 7` e verificou o programa. O painel exibiu fontes, coeficientes, domínio, estado condicional, operações, CPU, pico de memória do processo e zero chamadas ao organizador.

A contraprova `(2,8)` retirou o modelo anterior e os procedimentos dependentes. O primeiro pedido posterior de invenção bloqueou o uso do modelo, mas descreveu incorretamente zero candidatos como ambiguidade. O desenvolvedor corrigiu o estado e a explicação; o QA acrescentou a regressão. Após reiniciar o servidor, a memória persistiu e o reteste visual informou que a família foi refutada e que acrescentar uma observação não restaura sua compatibilidade. O histórico original foi preservado. A aparência e a legibilidade da resposta foram conferidas visualmente.

O aceite automatizado final da retomada registra **254 testes aprovados**: 119 de cognição, 60 de chat, 40 de ciência e 35 de F00. O QA também reproduziu integralmente o piloto cognitivo e conferiu os hashes dos relatórios cognitivo v4, científico v7 e aprendizado contínuo v3. Esses números e o estado de cada requisito estão na [matriz independente](research/F01_F11_QA.md).

### Correção da conversa natural reportada pelo usuário

O fechamento anterior não cobria adequadamente definições compostas, relações inversas no contexto e pedidos naturais de criação. O usuário demonstrou que a resposta repetia uma premissa em vez de tratar a pergunta; sete aceites foram reabertos pelo QA. Os testes desta correção estão em `tests/chat/test_conceptual_reasoning.py`, incluindo a sequência literal reportada e casos independentes com nomes arbitrários.

O reteste completo passou com **286 testes**: 92 de chat/HTTP (incluindo 31 conceituais), 119 de cognição, 40 de ciência e 35 de F00. O [parecer lógico independente por IA](research/CONVERSATIONAL_REASONING_REVIEW.md) registra seis grupos de defeitos encontrados e corrigidos, além de injeções de propostas incorretas que o verificador deve rejeitar mesmo quando o gerador é adulterado.

O integrador executou o teste visual numa instância isolada, porta 8767, sem acrescentar mensagens ao histórico pessoal:

- A definição original de buraco negro foi decomposta em tipo, absorção de matéria e absorção de luz. A causa informada permaneceu uma qualificação sem confirmação.
- A pergunta que assume buraco branco como inverso produziu “buraco branco expulsa luz e matéria”, marcada como hipótese local. O painel mostrou duas fontes, a suposição temporária, `absorve → expulsa`, sete operações e zero chamadas ao organizador.
- Na mesma conversa, foram fornecidas as funções de Plorin e Xaret. O pedido de transformar luz em movimento produziu a cadeia `luz → calor → movimento`. O primeiro teste visual revelou uma frase irrelevante herdada do assunto anterior; após correção, reteste e nova regressão de QA, o texto e as premissas passaram a mencionar apenas os componentes usados.
- Após o reinício da instância temporária, a sessão antiga recusou envio até recarregar a página, como previsto pela proteção local. Recarregar renovou a sessão e o envio passou. O histórico anterior foi conservado.

O servidor usado pelo usuário na porta 8766 foi reiniciado com os mesmos dados em `data/chat-teste`, após encerramento e cópia de segurança completa em `data/chat-teste-backup-conceitual-20260912-230453`. A aba foi recarregada e a conversa original permaneceu intacta. Respostas antigas permanecem como registro do comportamento da versão anterior; uma nova mensagem usa o núcleo corrigido. As definições antigas são interpretadas estruturalmente sem exigir sua reinserção.

Um teste adicional usou uma cópia temporária desse banco original e repetiu apenas `o que é um buraco branco?`: gerou as duas hipóteses de expulsão de matéria e luz com as premissas antigas M6/M7, sem chamadas ao organizador. O banco original e o backup mantiveram suas 24 mensagens; esse teste não acrescentou mensagens à conversa pessoal.

A avaliação conversacional registra **7 diálogos conhecidos, 31 mensagens e 240 verificações**, com 14 hipóteses avaliadas e zero chamadas a modelos gerais. [Protocolo](../experiments/conversation/conceptual-pilot.v1/protocol.json), [registro](../experiments/conversation/conceptual-pilot.v1/registration.json) e [resultados](../experiments/conversation/conceptual-pilot.v1/results.json) foram preservados, com reprodução v2. Isso verifica regressões de desenvolvimento; não é avaliação cega de generalização. O piloto de operadores foi reproduzido em [v5](../experiments/cognition/operators-pilot.v5/results.json), com dependências atuais registradas, e em v6; os resultados v4 continuam históricos.

```sh
python3 scripts/evaluate_conceptual_chat.py --output-dir /tmp/ar-conversa-nova
python3 scripts/evaluate_operators.py --output-dir /tmp/ar-operadores-novo
```

Escolha diretórios ainda inexistentes; os scripts recusam sobrescrever registros anteriores. O suporte ao português continua delimitado e os operadores de oposição/analogia/composição são fornecidos pelo programa. A ampliação necessária para o objetivo geral está registrada na F12 do TODO.

## Experimentos registrados

- [F00](research/F00_RESULTS.md): comparadores e pequenos mundos; conjunto científico reservado sem pontuação.
- [Aprendizado contínuo](research/MEMORY_LEARNING_OPERATIONS.md): cinco sementes, três condições de retenção, reversão, restauração, retirada de fontes e mudança explícita de domínio.
- [Física e quântica](research/SCIENCE_RESULTS.md): simuladores, ajuste e comparadores com resultados positivos e negativos.
- [Descoberta numérica](research/SCIENCE_DISCOVERY.md): corpus NIST observado, procedência, referências e limites de utilidade.
- [Aprendizagem e invenção](research/COGNITION_RESULTS.md): 360 condições, 720 ajustes próprios, seleção de exemplos, ablações e nove passos reais de conversa.
- [Transferência física](research/SCIENCE_MOTION_TRANSFER.md): 80 poses 3D futuras, 240 coordenadas escalares, resultado negativo preservado e expansão do modelo rejeitada.

O [parecer científico por agente de IA](research/SCIENTIFIC_REVIEW_AI.md) acrescenta recálculos por métodos independentes, revisão de fontes e análise de utilidade/novidade; seu escopo é distinto de revisão humana por pares e replicação empírica. A rede neural própria e os dados anotados da frente cognitiva têm protocolo/relatório separados. Dados sintéticos, dados humanos publicados e medições físicas não são intercambiáveis. Aprender coeficientes ou resolver um laboratório pequeno não demonstra raciocínio humano geral, descoberta científica inédita nem equivalência com ChatGPT.
