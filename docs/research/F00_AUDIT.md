# F00 — Auditoria de capacidades, modelos e conhecimentos embutidos

F00-02. Base auditada: commit `d2c32a33171819a25ba7b896991647019cac1ffb`, 08/09/2026. O novo laboratório está separado em `src/research/`; nenhuma alteração F00 muda o caminho de resposta do chat.

Este inventário descreve a versão auditada. O protótipo de pássaros, seus arquivos auxiliares e os scripts históricos `evaluate_conversation.py` e `setup_local_model.py` foram removidos da árvore atual na higienização de 13/09/2026; continuam consultáveis no histórico Git. Para executar e validar a aplicação atual, consulte o [README](../../README.md) e a [validação do chatbot](../CHATBOT_VALIDATION.md).

## 1. Critérios de classificação

**Implementada:** existe execução e verificação funcional para um contrato delimitado. **Limitada:** existe mecanismo, mas escopo/evidência não sustentam a capacidade geral. **Planejada:** consta do TODO e falta implementação no caminho ativo. **Sem evidência:** a afirmação existe em documentação ou nome de módulo, porém não há demonstração reproduzível aplicável ao objetivo atual. As categorias não são percentuais de inteligência.

| Capacidade | Classificação | Evidência e limite |
| --- | --- | --- |
| Conversas, histórico, persistência e IDs de envio | Implementada | `src/chat/server.py`, `engine.py`, `memory.py`; testes/chat HTTP, aprendizagem e conversa |
| Extração própria de português | Limitada | `extraction.py`: expressões regulares, vocabulário fechado e algumas referências; o modelo pode complementar a extração |
| Contexto e respostas gerais | Limitada / dependente de modelo | `provider.py` preserva papéis e a última mensagem; conhecimento geral e interpretação ampla vêm do modelo pré-treinado |
| Memória com fontes, conflitos e retrações | Implementada no contrato de triplas | `memory.py`; não equivale a memória causal, probabilística ou conhecimento científico validado |
| Dedução por pertencimento e regra universal | Limitada | `Reasoner.deduce`; propagação delimitada, sem aprender o operador de inferência |
| Oposição, analogia e composição | Limitada | `Reasoner.opposition`, `analogies`, `compose`: propostas marcadas como hipóteses; compatibilidade física não verificada |
| Planejamento de ações no chat | Planejada | Não há adaptador de estado/ação nem planejamento com verificador no caminho ativo |
| Aprender regras novas, treinar redes e meta-aprendizado no chat | Planejada | Não há atualização de pesos ou aprendizagem de operadores em `src/chat/`; L1/L2 não demonstram L3/L4 |
| Qwen estritamente como redator | Planejada | Atualmente participa da extração e produz a resposta geral; separação pertence a F01 |
| Simulação física e quântica integrada ao chat | Planejada | Nenhum módulo de simulação está conectado a `ChatEngine.reply` |
| Inovação científica geral, raciocínio humano ou melhoria autônoma superior | Sem evidência | Não há protocolo/resultado que sustente essas alegações; F00 começa a infraestrutura para investigar capacidades delimitadas |
| Controle de composição observado no laboratório F00 | Implementada após QA | `src/research/`: instrumento offline separado; composição e exatidão das observações são priors fornecidos, não aprendidos |

Regressão inicial reproduzida pelo integrador e pelo QA: `python3 -m unittest discover -s tests/chat -q`, **57 testes aprovados em Python 3.9.6**, antes das mudanças F00. A suíte usa respostas simuladas em testes de provedor; não mede qualidade de um modelo real. O roteiro histórico de seis pedidos em [CHATBOT_VALIDATION.md](../CHATBOT_VALIDATION.md) inclui uma falha de contagem de palavras e não fornece medida de inteligência geral.

## 2. Chamadas a modelos no caminho ativo

Os quatro pontos de entrada `main.py`, `app.py`, `launcher.py` e `run_frontend.py` importam `src.chat.server.main`. A auditoria leu `src/chat/*.py` e pesquisou invocações e transporte HTTP em `src`, `scripts` e scripts Python da raiz. Linhas abaixo referem-se à base auditada, acompanhadas dos nomes estáveis das funções.

| Local de invocação | Função e informação fornecida | Consequência |
| --- | --- | --- |
| `src/chat/engine.py:45` | `LanguageModel.complete(EXTRACTION_PROMPT, ...)`: mensagem atual e referente, esquema de afirmações | Modelo participa **antes** da memória e inferência. Validação local reduz extrações inválidas, sem provar interpretação completa |
| `src/chat/engine.py:107` | `LanguageModel.chat`: mensagem, histórico selecionado e contexto de memórias/inferências | Modelo escolhe conteúdo e formula a resposta; o prompt permite usar conhecimento geral |
| `src/chat/server.py:112` | `complete("Responda apenas OK.", ...)` no teste de conexão | Também é inferência por modelo, embora seja apenas teste de configuração |
| `src/chat/provider.py:100–153` | `_request` centraliza POST: Ollama `/api/chat` ou OpenAI `/responses` | Ollama pode ser local ou outro endereço configurado; OpenAI usa serviço externo. Redirecionamento bloqueado. Não registrar credenciais |
| `scripts/evaluate_conversation.py` | Executa `ChatEngine.reply` com provedor configurado | Avaliação histórica faz as mesmas chamadas de extração e conversa; não é uma referência independente do modelo |

`Settings()` começa simbólico para construção explícita; `Settings.load()` usa Ollama/`qwen3.5:9b` quando não há configuração persistida ou substituição por ambiente. Registrar a configuração de cada experimento, em vez de inferir o provedor apenas pelo construtor. Na F00 nenhum desses módulos é chamado pelo avaliador.

Transporte sem inferência: `runtime.runtime_available()` faz GET local `/api/version`; `runtime.start_local_runtime()` pode iniciar o binário local; `scripts/setup_local_model.py` baixa Ollama e solicita download do modelo em `/api/pull`. São dependências operacionais, não raciocínio. F00 não executa instalação, inicialização ou download.

## 3. Inventário estático do legado

O protótipo de pássaros é acessado por `bird_*.py` e depende de `requirements-birds.txt`. Não está importado pelo caminho ativo do chat. A pesquisa estática encontrou também estas chamadas de modelos, **não executadas** nesta auditoria:

| Arquivo legado | Chamadas encontradas e conhecimento externo |
| --- | --- |
| `src/core/curator.py` e cópia `hybrid_curator.py` | `_validate_with_gemini`, POST linha 227 para `gemini-1.5-pro-latest:generateContent`; `_validate_with_gpt4v`, POST linha 314 para chat completions, modelo configurado `gpt-4-vision-preview`; enviam imagem e instrução de identificação de pássaro |
| `continuous_learning.py` | POST linhas 152/240 para Gemini ou OpenAI em fluxo legado de validação; conhecimento visual pré-treinado |
| `hybrid_analysis_system.py` | POST linhas 96/163 para `gemini-1.5-flash:generateContent` ou OpenAI; classificação/descrição por imagem |
| `bird_main.py` e utilitários de modelos | Inferência local Keras em classificadores previamente treinados; pesos/dados não são aprendizado do núcleo conversacional |

Os nomes de modelo acima são strings existentes no código, não confirmação de disponibilidade atual de APIs. O levantamento de chamadas foi estático; não houve execução integral, validação de todos os pesos ou auditoria completa de cada mecanismo do legado. Citações antigas de “santo graal”, autoevolução ou percentuais de conclusão, especialmente em `docs/SANTO_GRAAL_IMPLEMENTADO.md`, `checklist.md` e módulos `src/core/*learning*.py`, não são evidência da capacidade do novo chat. Reutilizar um componente legado exige auditoria funcional própria e resultados reservados.

## 4. Priors e conhecimentos programados do chat

1. `domain.py`: remoção de acentos, caixa e artigos; conjunto `STOPWORDS`; dicionário `VERBS` com flexões, sinônimos e normalização para relações. Tipos de afirmação, polaridade e universal/instância também são escolhas humanas.
2. `extraction.py`: gramática de perguntas/ordens, marcadores de hipótese e correção, negações, universais “todo/toda/cada”, resolução limitada de pronomes e formatos de nome/preferência. Limite de 12 afirmações, tamanhos de campos e validações de trecho literal são priors. Prompt e esquema restringem o extrator neural, mas não eliminam seu treinamento prévio.
3. `reasoner.retrieve`: palavras em comum, assunto composto e preferência da conversa; cobertura mínima 0,67; pesos 3/5/2; limites 12/24. Similaridade lexical não é comprovação semântica nem factual.
4. `Reasoner.deduce`: regra fixa de herança de propriedade universal para uma instância; até 32 propostas por chamada e 4 passagens em `engine.py`. Essa regra não foi aprendida pelas mensagens.
5. `VERBAL_PAIRS`: absorve↔expulsa, aquece↔resfria, produz↔consome, armazena↔libera, aumenta↔diminui, emite↔recebe, permite↔impede. `NAME_PAIRS`: negro↔branco, quente↔frio, claro↔escuro, entrada↔saída. São transformações linguísticas fornecidas, não leis físicas nem provas de existência; novas oposições explícitas podem ser armazenadas.
6. `analogies`: relações compartilhadas como critério de transferência, bloqueios por negativas e limites de alvos/premissas/propostas. `compose`: seleciona duas/três funções e usa um texto de combinação; não testa interfaces, causalidade ou viabilidade.
7. `memory.py`: estados e precedência de correções, unicidade de triplas, conflitos, fontes e dependências são política programada. Afirmação do usuário continua sendo premissa informada; repetição não é confirmação independente.
8. `provider.py`: prompt de assistente geral, instruções sobre incerteza e aprendizado; histórico de até 24.000 caracteres, contexto selecionado pelo motor, temperaturas 0/0,7 e limites de geração. A competência e o conhecimento pré-treinado do modelo devem ser contabilizados separadamente.

Os valores exatos permanecem no código citado; alterá-los muda o prior e exige nova versão experimental. O laboratório F00 adiciona outros priors, descritos em [F00_PROTOCOL.md](F00_PROTOCOL.md): estados completos e determinísticos, transições exatas e composição programada. O resultado não será atribuído a “raciocínio emergente” sem um experimento que isole essa hipótese.
