# F00 — Domínio inicial, recursos e lacunas

F00-08. Inventário fornecido pelo integrador em 09/09/2026 01:43:29 UTC (08/09/2026 22:43:29 America/Sao_Paulo). Valores de disco/serviços são instantâneos, não requisitos fixos.

## 1. Domínio escolhido

Começar por **transformações discretas de estados totalmente observáveis**, determinísticas, com ações e planejamento curto. O instrumento F00 usa estados categóricos, duas etapas e observações exatas para medir composição e reconhecimento de evidência insuficiente. A família futura reservada trata transferência discreta de quantidade; F00 não pontua essa família. Nenhum desses resultados será anunciado como simulação de pensamento humano.

Primeiro domínio de física quantitativa selecionado para F06: **mecânica de uma partícula em uma dimensão, começando por movimento uniforme**, com posição em metros, velocidade em metros/segundo, duração em segundos e medições com incerteza explicitada. Faixas iniciais propostas: posição inicial entre −10 e 10 m, velocidade entre −3 e 3 m/s e intervalo de tempo entre 0,1 e 2 s, começando sem ruído. São parâmetros de planejamento para F06, não dados já gerados; resolução, amostragem, erro tolerado e posterior modelo de ruído precisam de registro antes da execução. Primeiro testar `x(t+Δt)=x(t)+vΔt` contra solução analítica; depois estudar aceleração constante e ruído, uma extensão por vez.

Há dois ensaios distintos: (a) composição de leis fornecidas, para testar cálculo/unidades; (b) aprendizagem de relação ocultada ao aprendiz, para testar indução. Não chamar (a) de descoberta de uma lei. Em (b), os dados podem ser gerados pela lei conhecida do avaliador, mas o aprendiz recebe somente medições permitidas; avaliação independente deve conferir previsões fora das observações usadas no ajuste.

O simulador físico, descoberta de equações e qualquer módulo quântico **ainda não foram implementados na F00**. Mecânica quântica permanece uma linha experimental com função e critérios próprios em F08; não exige aquisição imediata de hardware quântico.

## 2. Recursos observados

| Recurso | Evidência local |
| --- | --- |
| Repositório base | Git HEAD `d2c32a33171819a25ba7b896991647019cac1ffb` |
| Sistema | Darwin, macOS 26.5.2, arquitetura arm64 |
| Processador | Apple M4, 10 CPUs lógicos |
| RAM | 25.769.803.776 bytes = 24 GiB |
| Disco disponível | 305.899.659.264 bytes, aproximadamente 284,9 GiB no instante de coleta |
| Python | 3.9.6, `/Library/Developer/CommandLineTools/usr/bin/python3` |
| Node | v24.7.0; útil à interface, não requerido pelo avaliador F00 |
| Dependências do chat/F00 | Biblioteca padrão Python 3.9+; `requirements.txt` não exige pacote externo |
| Ollama | Binário `.runtime/ollama/ollama` presente. GET local `/api/version` e `/api/tags` falhou por indisponibilidade; não há confirmação de serviço ativo nessa coleta |
| Modelo configurado no código | `qwen3.5:9b` em `src/chat/runtime.py`; configuração não prova pesos carregados nem serviço disponível. F00 não requer o modelo |
| Dados do laboratório | Gerados por código próprio e sementes versionadas; sem leitura de conversas pessoais, sem download de dados |

Método de coleta do integrador: Python/platform, `sysctl` para CPU/RAM, estatística do sistema de arquivos para disco, `python3 --version`, `node --version`, Git e GETs locais de saúde. Não foram lidas chaves, textos de conversas ou respostas pessoais. Versão de Python/arquitetura também é registrada automaticamente em cada relatório experimental.

## 3. Orçamento inicial e custos a medir

- F00: 120 episódios × 3 comparadores, 8 observações por episódio, 128 operações lógicas e 1 segundo pós-retorno por caso. Sem GPU, Qwen, contratação de API ou instalação adicional. O custo marginal de API desta execução é zero porque não existe chamada; energia e tempo de trabalho não foram monetizados.
- Desenvolvimento/QA: executar controles pequenos e independentes; resultados de tempo por comparador ficam nos relatórios. O piloto mede viabilidade local, não fornece estimativa de treinar inteligência geral.
- Próximo modelo neural: medir primeiro RAM, tempo, tamanho dos dados e curva de ganho em um modelo pequeno; declarar limite de treino e um comparador sem rede antes de escolher arquitetura maior. Os 24 GiB disponíveis não são uma promessa de viabilidade de qualquer treinamento.
- Serviços externos e hardware adicional: exigir estimativa a partir de carga medida e preço verificado no momento de decidir; não há compra, contratação ou valor financeiro presumido neste plano.

## 4. O que falta e quem precisa cobrir

| Necessidade | Evidência/entregável antes de avançar |
| --- | --- |
| Dados para compreensão própria | Conversas sintéticas/anotadas com origem, paráfrases, ambiguidades e splits por estrutura; consentimento e retirada quando forem usados dados pessoais |
| Dados físicos confiáveis | Soluções analíticas iniciais; depois medições públicas licenciadas, unidades e incerteza. Procedência e verificação independente precedem ingestão |
| Aprendizagem própria | Arquitetura, parâmetros inicializados, função de perda, conjuntos de treino/validação e budget; nenhuma dependência neural é necessária para concluir F00 |
| Estatística experimental | Competência em comparação pareada, incerteza por família, análise de poder e prevenção de vazamento; definir efeito mínimo relevante antes da alegação de ganho |
| IA e lógica | Competência em modelos estruturados, planejamento, indução e causalidade; validar pressupostos e evitar dar ao aprendiz a regra que deveria descobrir |
| Física e métodos numéricos | Revisão de domínio, unidades, validade das leis, erro numérico e simulador independente; antes de estender movimento 1D |
| Mecânica quântica | Revisão especializada de estados/observáveis/medição e comparadores clássicos; antes de interpretar um resultado quântico como ganho cognitivo |
| QA e engenharia | Contratos, casos adversos, reprodutibilidade, limites, versionamento, regressões e revisão das evidências antes de marcar TODO |
| Novidade e utilidade científica | Especialista do domínio e busca de trabalhos anteriores, seguidos de reprodução independente; só necessários para alegar uma invenção científica |

Papéis podem ser cobertos pela mesma equipe, mas a validação precisa de verificação independente do mecanismo que gerou a resposta. Nesta entrega há um agente desenvolvedor, um agente QA separado e integração/revisão final; agentes de software não substituem evidência experimental ou revisão científica especializada.
