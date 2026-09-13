# Registro histórico anterior à separação núcleo/redator

Este documento preserva a avaliação do fluxo anterior. Não descreve o comportamento atual nem demonstra capacidade do novo núcleo próprio. Consulte [validação atual](../CHATBOT_VALIDATION.md).

# Validação da conversa — 8 de setembro de 2026

## Escopo

Corrigir o comportamento que respondia perguntas novas com memórias do exemplo anterior. A validação cobre o uso da última mensagem, histórico da conversa atual, troca de assunto, continuidade e preservação do aprendizado.

## Testes automatizados

Comando: `python3 -m unittest discover -s tests/chat -q`.

**57 testes passaram** em Python 3.9.6. Cobrem memória, inferências, correções, origens, isolamento do histórico por conversa, recuperação de conceitos compostos, mensagens nativas dos provedores, streaming, falhas, reenvio idempotente e reutilização de um servidor local existente. Também foram verificados a sintaxe do JavaScript e os espaços em branco do diff.

Os testes unitários usam respostas simuladas onde necessário. Eles verificam o funcionamento do programa, sem medir a inteligência de um modelo.

## Avaliação com modelo real

Modelo: `qwen3.5:9b`, via Ollama 0.33.3 em macOS Apple Silicon com 24 GB de memória. A avaliação usou memória temporária. Antes das perguntas, foram registradas a premissa sobre buraco negro e uma hipótese de oposição pelo motor simbólico, reproduzindo o contexto que originou o problema.

Roteiro utilizado na versão histórica: `python3 scripts/evaluate_conversation.py --model qwen3.5:9b`. Esse avaliador foi removido da árvore atual; permanece no histórico Git. A avaliação conversacional atual usa `scripts/evaluate_conceptual_chat.py`. As respostas completas daquela execução foram registradas no arquivo local `.runtime/conversation-evaluation-9b.json`, ignorado pelo Git.

| Caso | Observação |
| --- | --- |
| Perguntar sobre buraco de minhoca após o exemplo de oposição | Gerou uma explicação sobre uma conexão hipotética no espaço-tempo. Não recuperou a memória do buraco negro como se fosse o conceito perguntado. |
| Pedir “explique isso” com uma analogia | A analogia tratou do conceito da resposta anterior. |
| Mudar de assunto para fotossíntese | Explicou fotossíntese, sem continuar a discussão de buracos. |
| Resumir a última resposta em exatamente cinco palavras | Manteve o assunto correto, mas retornou oito palavras. A restrição de contagem falhou. |
| Pedir uma função Python `dobro` | Retornou uma função com `return x * 2`. |
| Perguntar a diferença entre lista e tupla | Respondeu sobre mutabilidade de coleções em Python. |

Depois do carregamento inicial, o primeiro trecho de texto chegou entre aproximadamente 1,6 e 2,9 segundos nesta execução. A primeira resposta, incluindo carregamento e a condição de memória naquele momento, levou 76,4 segundos no total. Os números não são uma garantia de desempenho: carga da máquina, tamanho do histórico, modelo e comprimento da resposta alteram a latência.

## Limites observados

O modelo responde sobre o pedido atual e usa referências do diálogo, mas ainda pode errar fatos, formulações e restrições de formato. Uma amostra de seis pedidos não demonstra equivalência de qualidade com ChatGPT nem exatidão geral. A contagem de palavras falhou explicitamente e permanece uma limitação do modelo escolhido.

A recuperação de memória continua lexical, com proteção para conceitos compostos e prioridade para fontes da conversa atual. Não equivale a busca semântica por embeddings. O histórico enviado ao modelo tem um limite de tamanho; o banco persiste as conversas completas.

As respostas do modelo permanecem no histórico e não viram automaticamente fatos. O aprendizado do projeto continua ocorrendo pela memória, relações e revisão de premissas, sem atualizar pesos neurais a cada mensagem.
