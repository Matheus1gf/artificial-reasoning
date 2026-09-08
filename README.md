# Raciocínio Artificial

Um chatbot de uso geral com memória e raciocínio experimental. Responde à mensagem atual usando o contexto da conversa e o conhecimento de um modelo de linguagem. Os aprendizados persistentes ajudam quando são relevantes; deduções, oposições, analogias e composições são recursos adicionais, não um formato obrigatório de resposta.

O primeiro domínio experimental foi a identificação de pássaros. Agora o ponto de entrada é uma aplicação conversacional independente dos modelos de visão. O protótipo anterior foi preservado para consulta e comparação.

O [TODO principal de pesquisa e desenvolvimento](TODO.md) define a próxima arquitetura: compreensão e raciocínio próprios antes da resposta, com o Qwen restrito à redação de conteúdo aprovado. O plano inclui redes próprias, aprendizado contínuo, física, experimentos quânticos e validação de invenções. **Essa arquitetura ainda está planejada**; as instruções e capacidades descritas abaixo correspondem à implementação atual.

## Executar

Requer **Python 3.9 ou superior**. O núcleo, a interface web e os testes usam apenas a biblioteca padrão. Não é preciso instalar TensorFlow, YOLO, Streamlit ou Node para usar o chat.

Para preparar o modelo local uma vez, em macOS Apple Silicon:

```bash
python3 scripts/setup_local_model.py
```

O instalador verifica uma distribuição oficial do Ollama por SHA-256, baixa o modelo `qwen3.5:9b` (cerca de 6,6 GB) e salva sua configuração. O executável fica em `.runtime/ollama` e os pesos em `data/chat-runtime/models`, ambos fora do Git. Nesta máquina essa preparação já foi feita. Referências: [modelo no catálogo oficial](https://ollama.com/library/qwen3.5:9b) e [distribuição Ollama utilizada](https://github.com/ollama/ollama/releases/tag/v0.33.3).

Depois, basta iniciar a aplicação; ela inicia seu Ollama local quando necessário:

```bash
python3 main.py
```

Abra **http://127.0.0.1:8765**. No Windows, use `python` se esse for o nome do seu interpretador. `python3 app.py`, `python3 launcher.py` e `python3 run_frontend.py` também abrem o novo servidor.

Em outros sistemas, instale Ollama pela distribuição oficial e baixe um modelo, ou configure a API da OpenAI na interface. O instalador incluído é específico para macOS Apple Silicon; o chatbot funciona com qualquer um desses provedores HTTP.

Para conversar pelo terminal, mantendo o mesmo banco de memória:

```bash
python3 main.py --cli
```

Use `/sair` para encerrar. Para um laboratório separado:

```bash
python3 main.py --port 8766 --data-dir ./data/chat-experimento
```

## Conversar

Experimente uma sequência como:

1. `O que é fotossíntese? Explique em duas frases.`
2. `Resuma sua última resposta em cinco palavras.`
3. `Agora escreva uma função Python que conte as palavras de um texto.`

A última mensagem determina o que responder. Expressões como “isso”, “a última resposta” e “explique melhor” usam o histórico da conversa atual, enviado ao modelo com os papéis reais de usuário e assistente. Uma nova conversa começa com outro histórico. Conhecimentos salvos podem ser recuperados entre conversas, mas não substituem a pergunta atual. As respostas aparecem progressivamente na tela.

O modelo responde a perguntas gerais mesmo sem conhecimentos ensinados anteriormente. O conhecimento prévio do modelo vem de seu treinamento; ele não foi aprendido do zero pelo projeto.

## Experimentar o aprendizado e as inferências

Para testar especificamente o recurso de oposição, use estas mensagens:

1. `Um buraco negro absorve matéria.`
2. `Qual seria o oposto de um buraco negro?`

O motor usa a premissa ensinada e as relações linguísticas `absorve ↔ expulsa` e `negro ↔ branco` para propor **“buraco branco expulsa matéria”**. A proposta fica marcada como **hipótese por oposição**, com referência à mensagem de origem e indicação de que o nome e a inversão não demonstram a existência do objeto. Não há uma resposta astronômica pronta nem fatos sobre buracos negros pré-carregados no banco.

Experimente também um domínio fictício, para observar o que foi aprendido no próprio laboratório:

| Mensagem | Comportamento esperado |
| --- | --- |
| `Todo cristal emite luz.` | Guarda uma regra universal explícita. |
| Em uma nova conversa: `Neral é um cristal.` | Deduz condicionalmente que Neral emite luz, citando as duas premissas. |
| `Corrigindo: todo cristal não emite luz.` | Retira a versão anterior e as deduções dependentes; aplica a nova premissa. |
| `Neral armazena energia. Vetra armazena energia.` | Registra relações compartilhadas que podem sustentar analogias. |
| `Compare Neral e Vetra por analogia.` | Explora uma propriedade transferível, quando houver, como hipótese. |
| `Um filtro filtra água. Uma turbina produz energia.` | Registra funções de componentes. |
| `Crie algo combinando filtro e turbina.` | Propõe uma composição funcional e um plano de verificação. |
| `O oposto de filtrar é misturar.` | Acrescenta uma relação de oposição ensinada pelo usuário. |

A aba **Memória** permite buscar conhecimentos, consultar mensagens de origem e retirar uma premissa. Conclusões dependentes são revistas automaticamente. O histórico preserva as respostas originais; os cartões de evidência mostram o estado atual.

## O que significa aprender nesta versão

- **Toda mensagem enviada com sucesso vira experiência registrada**, inclusive perguntas e mensagens que o extrator não entende.
- **Afirmações extraídas viram memória estruturada**, compartilhada entre conversas do mesmo laboratório e preservada após reiniciar o servidor.
- **Relações alimentam novas inferências**. Deduções precisam de premissas explícitas; analogias, oposições e composições continuam sendo hipóteses.
- **Correções revisam as consequências do aprendizado anterior**. Afirmações contraditórias são sinalizadas e deixam de fundamentar novas conclusões enquanto o conflito não for resolvido.

Isso é aprendizado por memória e revisão de conhecimento. **Os pesos de uma rede neural não são atualizados a cada mensagem.** Uma afirmação do usuário tampouco equivale a uma verdade verificada. O sistema não promove automaticamente suas próprias respostas ou hipóteses a fatos, nem usa repetição como prova.

## Configurar o modelo

O padrão da aplicação web é **Ollama com `qwen3.5:9b`**, para conversar usando um modelo neural local. Configurações salvas anteriormente continuam sendo respeitadas. Abra **Configurações** para mudar de modelo ou provedor. O modo simbólico fica disponível como ferramenta técnica de memória e regras, sem conversa geral:

| Modo | Necessário | Uso dos dados |
| --- | --- | --- |
| Simbólico | Apenas Python | Nenhuma chamada de rede para modelos. |
| Ollama | Servidor Ollama em execução e um modelo instalado com suporte adequado a JSON estruturado | Mensagem, referente e contexto relevante enviados ao endereço configurado; um servidor local mantém esse processamento no computador. |
| OpenAI | Modelo compatível com Responses e Structured Outputs; chave em `OPENAI_API_KEY` no ambiente do servidor | Mensagem, histórico recente e memórias relevantes enviados à API configurada. Pode haver cobrança pelo provedor. |

Informe o **nome exato de um modelo disponível**, salve e use **Testar conexão salva**. Os padrões de endereço são `http://127.0.0.1:11434` para Ollama e `https://api.openai.com/v1` para OpenAI. A chave não é solicitada na interface, salva no banco ou incluída nas respostas da aplicação.

Também é possível configurar antes de iniciar:

```bash
AR_PROVIDER=ollama AR_MODEL=NOME_DO_MODELO_INSTALADO python3 main.py
```

`AR_PROVIDER`, `AR_MODEL` e `AR_BASE_URL` prevalecem sobre a configuração salva na inicialização. Alterações feitas na interface valem imediatamente; se essas variáveis continuarem definidas, voltarão a prevalecer no próximo início.

O modelo recebe a pergunta atual por último, o histórico desta conversa em ordem e memórias auxiliares selecionadas por relevância. Perguntas não exigem uma chamada adicional de extração. Se a extração de afirmações falhar, a conversa neural continua com aviso; se a geração da resposta falhar, a interface mostra um erro e permite tentar novamente, sem inventar uma resposta padronizada. Os modelos são baixados apenas quando o instalador é executado. Com Ollama local, as conversas são processadas neste computador.

## Estrutura e dados

```text
main.py / app.py          Entradas da aplicação conversacional
src/chat/domain.py       Representação de afirmações e hipóteses
src/chat/extraction.py   Extração local e validação da extração neural
src/chat/memory.py       SQLite, origem, dependências e revisões
src/chat/reasoner.py     Recuperação, dedução, oposição, analogia, composição
src/chat/engine.py       Ciclo de aprendizado e resposta
src/chat/provider.py     Adaptadores HTTP Ollama e OpenAI
src/chat/runtime.py      Inicialização do modelo local instalado no projeto
src/chat/server.py       Servidor local e terminal
src/chat/web/            Interface de conversas, memória e configurações
scripts/setup_local_model.py      Preparação do modelo local
scripts/evaluate_conversation.py  Avaliação qualitativa com um modelo real
tests/chat/              Testes do chatbot sem serviços externos
data/chat/               Banco e configurações locais, ignorados pelo Git
```

O laboratório é **pessoal e local**: todas as conversas no mesmo banco compartilham conhecimento. O servidor escuta apenas em `127.0.0.1`. Ainda não há contas, isolamento entre usuários, criptografia do banco, embeddings ou verificação externa de fatos. Retirar um conhecimento preserva o registro para auditoria; não é uma operação de apagar dados pessoais. Para fazer backup consistente, pare o servidor e copie a pasta de dados inteira.

## Verificar

```bash
python3 -m unittest discover -s tests/chat -v
```

A suíte testa aprendizado com um exemplo, persistência, inferências, correções, separação de conceitos com palavras semelhantes, histórico por conversa, contexto enviado ao modelo, streaming e falhas. Os testes unitários dos provedores usam respostas simuladas e não medem a qualidade de um modelo real. A CI executa a suíte do chat em Python 3.9 e 3.12.

Para registrar respostas reais em um banco temporário, sem alterar suas conversas:

```bash
python3 scripts/evaluate_conversation.py
```

O modelo deve estar em execução. O roteiro inclui mudança de assunto, referência à resposta anterior, resumo e código. Salva prompts, respostas, latências e memórias recuperadas em `.runtime/conversation-evaluation.json`. A revisão é qualitativa, sem converter uma pequena amostra em uma alegação de exatidão geral. Consulte os [resultados e limites observados](docs/CHATBOT_VALIDATION.md).

Leia a [arquitetura atual e os limites de pesquisa](docs/CHATBOT_ARCHITECTURE.md), o [roteiro de evolução](docs/CHATBOT_ROADMAP.md) e o [TODO detalhado do núcleo próprio](TODO.md). Os resultados funcionais não são uma demonstração de raciocínio humano geral, criatividade científica validada ou exatidão com qualquer conjunto pequeno de dados.

## Protótipo de pássaros

O [README histórico](docs/README_PASSAROS.md), os módulos de visão, modelos, dados e relatórios anteriores foram preservados. As entradas antigas são `bird_main.py`, `bird_app.py`, `bird_launcher.py` e `bird_run_frontend.py`; as dependências estão em `requirements-birds.txt`. O chat não importa nem executa esses módulos. Relatórios e scripts antigos de instalação se referem à fase de visão; não são necessários para iniciar o chatbot e não foram revalidados nesta migração.
