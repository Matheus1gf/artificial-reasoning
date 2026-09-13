# Parecer científico — revisão independente por agente de IA

**Data:** 12/09/2026, America/Sao_Paulo; verificações finais em 13/09/2026 UTC. **Revisor:** agente de IA `/root/scientific_reviewer`, designado para revisão científica e separado dos agentes de desenvolvimento e QA desta execução. **Decisão:** parecer favorável à qualidade do dossiê como pesquisa delimitada, incluindo seus resultados negativos, com as ressalvas e ações registradas abaixo. Não há evidência de descoberta científica inédita, superioridade neural ou quântica, nem transferência física positiva.

Esta é uma **revisão independente por agente de IA**, autorizada explicitamente pelo usuário para os itens F10-06 e F11-08. O revisor não implementou os componentes examinados e não alterou código, protocolos, dados, resultados congelados, TODO ou matriz de QA. A independência é de função e execução dentro da mesma equipe de agentes: há infraestrutura e contexto compartilhados, sem mascaramento da origem das propostas. Isso pode produzir vieses correlacionados. Não se trata de revisão humana por pares, parecer de instituição externa ou replicação empírica externa. Não houve contato com terceiros, acesso a conversas pessoais nem uso do conjunto reservado F00.

## Escopo, versões e método

Foram lidos o TODO, os documentos SCIENCE_PROTOCOL, SCIENCE_RESULTS, SCIENCE_DISCOVERY, SCIENCE_STATUS, SCIENCE_MOTION_TRANSFER, SPECIALIST_REVIEW_BRIEF, COGNITION_RESULTS, COGNITION_OPERATORS e as responsabilidades/estimativas em MEMORY_LEARNING_OPERATIONS. A inspeção de implementação incluiu ajuste numérico, simulador, busca simbólica, transferência medida, Born/evolução unitária, ajuste contextual, reanálise humana, treino de operadores, seleção ativa, composição e avaliação cognitiva. O aceite funcional e a reprodução integral dos pilotos pertencem ao agente QA; este parecer acrescenta auditoria científica e recálculos independentes específicos.

Versões efetivamente examinadas:

| Artefato | Verificação de identidade |
| --- | --- |
| [Registro científico v7](../../experiments/science/registration.v7.json) e [relatório v7](../../experiments/science/results/pilot.v7.json) | Os 24 hashes registrados coincidem com o relatório e com os arquivos lidos. Registro UTC 01:11:36, relatório UTC 01:11:40 em 13/09/2026 |
| [Protocolo cognitivo v4](../../experiments/cognition/operators-pilot.v4/protocol.json), [registro v4](../../experiments/cognition/operators-pilot.v4/registration.json) e [resultados v4](../../experiments/cognition/operators-pilot.v4/results.json) | Os 11 hashes de fontes e o hash do protocolo coincidem com os arquivos lidos |
| Identidade do relatório científico | SHA256 `fb98304781dd602dc16980d3503bc93edba4582ee5ebf0495653f8a63b73a9a6` |
| Identidade do relatório cognitivo | SHA256 `d7496f141fd524764f247f6f3672454912c7ecf0998deabfe354507945d69658` |

A comparação de hashes demonstra consistência dos artefatos atuais. Datas locais e declarações de pré-registro não provam, por si, ausência histórica de acesso ou escolha informal após conhecer um conjunto público. Os documentos reconhecem exposição anterior da trajetória, dados NIST públicos e emendas cognitivas posteriores ao primeiro piloto; não foi alegado um teste científico secreto.

Os recálculos usaram Python local, NumPy para mínimos quadrados por implementação distinta, `decimal` com 60 algarismos para a regressão NIST e SciPy para um diagnóstico exploratório de otimização contextual. Nenhum resultado exploratório substituiu ou reclassificou o resultado registrado.

## Verificações executadas e interpretação

### Movimento físico e incerteza

Reconstruí a seleção diretamente das 3.000 linhas brutas, usando os oito inícios e os vinte deslocamentos temporais do protocolo, sem chamar a seleção do projeto. Conferi associação temporal, ausência de duplicatas, coincidência das coordenadas com os segmentos registrados e separação dos dez tempos de ajuste dos dez tempos futuros. Cada um dos três eixos foi ajustado por `numpy.linalg.lstsq`, diretamente nos monômios temporais. As medidas futuras não entram no ajuste ou na seleção de parâmetros.

São **80 poses tridimensionais futuras, representadas por 240 coordenadas escalares**, e a mesma quantidade na parte de ajuste. Os 24 segmentos são combinações de eixo e janela, sem independência estatística presumida. O RMSE agregado abaixo é de coordenadas escalares, não a raiz do erro de distância tridimensional por pose.

| Modelo | RMSE independente (m) | Maior erro absoluto independente (m) |
| --- | ---: | ---: |
| Aceleração constante | 0,1417374523576001 | 0,7915462791778165 |
| Velocidade constante | 0,1544858161666878 | 0,5266589214633857 |
| Persistência | 0,09995649428626435 | 0,4103000000000000 |

A diferença máxima entre minhas previsões de mínimos quadrados e as do relatório foi `9,55 × 10⁻¹⁵ m`. A reprodução confirma a perda para persistência e a falha dos limites registrados de RMSE e erro máximo. O erro do integrador contra a solução analítica do mesmo ajuste é um controle de implementação; não valida a aproximação de aceleração constante perante movimento manual.

O formato e a descrição primários identificam posição da câmera em referencial mundial e trajetória manual; não fornecem forças controladas. Os limites empíricos do sistema de captura são inferiores a 1 mm entre quadros e 10 mm sobre a área, segundo a seção VI.C do artigo. Não são uma distribuição calibrada por pose. A página TUM falhou ao servir o PDF durante esta revisão; a passagem foi conferida no exemplar indexado no site do primeiro autor. [Formato TUM](https://cvg.cit.tum.de/data/datasets/rgbd-dataset/file_formats), [descrição da sequência](https://cvg.cit.tum.de/data/datasets/rgbd-dataset/download#testing_and_debugging), [Sturm et al., artigo primário](https://jsturm.de/publications/data/sturm12iros.pdf).

A expressão de sensibilidade `0,01 × (1 + Σ|wᵢ|)` é coerente com erro determinístico limitado nas posições de treino e na medida futura: deriva da desigualdade triangular aplicada à previsão linear nas observações. Ela não exige erros independentes. Recalculei os pesos por pseudoinversa; os orçamentos nos dois modelos variam aproximadamente entre 0,0280 e 0,2533 m. Essa amplificação evidencia que extrapolar um ajuste quadrático pode ser sensível mesmo com posições aparentemente precisas. O cálculo não inclui erro estrutural ou incerteza temporal, nem torna 10 mm um limite certificado universal. O dossiê declara essas limitações e evita intervalos de confiança artificiais para as janelas/eixos correlacionados.

**Conclusão física:** há utilidade no confronto falsificável com dados medidos e no bloqueio de promoção. A experiência rejeita a adequação preditiva desta aproximação nestes intervalos; não refuta a mecânica Newtoniana, não identifica uma nova lei e não demonstra utilidade de previsão além dos dados testados.

### Calibração NIST, precisão e anterioridade

Refiz a regressão afim com fórmulas escalares em aritmética decimal de 60 algarismos, usando os 36 pares, e refiz os três comparadores com o corte módulo três. Não chamei o QR ou a busca simbólica do projeto para esses cálculos.

| Quantidade | Reprodução independente |
| --- | ---: |
| Intercepto, todos os dados | −0,262323073774029495282164116195 |
| Inclinação, todos os dados | 1,002116818020454398944372442625 |
| RMSE afim, 12 pares de avaliação no corte declarado | 0,9794151927080429 |
| RMSE sem intercepto, expressão escolhida | 0,9925501905688077 |
| RMSE da média | 373,7670152434907 |

Os resultados concordam com o relatório às tolerâncias declaradas e confirmam a perda de aproximadamente `0,013135` para mínimos quadrados afins. A penalização da expressão mais simples não satisfaz o critério registrado de utilidade. A fidelidade aos coeficientes certificados é evidência de cálculo correto sobre aqueles mesmos dados. [Conjunto Norris do NIST](https://www.itl.nist.gov/div898/strd/lls/data/Norris.shtml), [descrição primária das variáveis](https://www.itl.nist.gov/div898/strd/lls/data/LINKS/i-Norris.shtml).

O corte evita sobreposição de linhas, mas não cria medições novas nem garante independência entre condições instrumentais. Com incerteza também na variável de referência, uma adoção metrológica exigiria investigar um modelo de erros nas variáveis e a estrutura instrumental; OLS aqui é o comparador numérico do conjunto publicado. Unidades/condições/incertezas não declaradas permanecem desconhecidas. É correto manter a interpretação metrológica sem aprovação.

A relação afim já é publicada. Coeficientes aprendidos pelo algoritmo e nomes de variáveis ocultados não transformam o resultado em novidade científica. A busca em catálogo de cinco fontes é útil para evitar alegações elementares de ineditismo, porém não determina ausência de anterioridade ou liberdade de exploração de uma futura invenção. A abordagem se insere na família conhecida de regressão simbólica, exemplificada pelo trabalho original [AI Feynman](https://arxiv.org/abs/1905.11481). Não reivindico uma busca exaustiva.

### Quântica, modelo contextual e dados humanos

O estado puro normalizado, a evolução `exp(−iωtX/2)`, as probabilidades de Born e a exigência de observável Hermitiano são coerentes no domínio descrito. Conferi o caso analítico `Rx(π)|0⟩`, obtendo probabilidades `[3,75 × 10⁻³³, 1]`, e três casos adversos: norma inválida, matriz não unitária e observável não Hermitiano foram rejeitados. A inferência de frequência aprende um parâmetro em uma classe fornecida e depende da grade candidata; verossimilhanças normalizadas nessa grade não são confiança científica calibrada.

Para o modelo contextual, escrevendo `s = cos²φ`, a primeira resposta zero tem probabilidade `cos²θ` em AB e `cos²(θ−φ)` em BA; a segunda mantém a resposta com probabilidade `s`. As quatro conjuntas são, portanto, `p·s`, `p·(1−s)`, `(1−p)·(1−s)` e `(1−p)·s`. Essa fatoração demonstra a equivalência ao controle clássico contextual escolhido. Conferi 442 contextos em uma grade de ângulos que inclui sinais negativos; a maior diferença entre implementações foi `5,00 × 10⁻¹⁶`. O empate é esperado por construção e não um teste com poder para encontrar vantagem de um formalismo sobre o outro.

A tabela 1 do artigo primário confirma as quatro contagens reconstruídas: `[29,7,34,46]`, `[35,7,23,43]`, `[57,5,19,37]` e `[60,14,3,29]`. O código preserva a ordem das respostas em BA. São 448 registros de resposta sequencial nos agregados, sem demonstrar 448 indivíduos únicos entre experiências. O formalismo do artigo admite dimensão arbitrária e discute uma previsão QQ distinta do ajuste restrito aqui feito. [Wang e Busemeyer, 2013, tabela 1 e seções 2.2–5](https://jbusemey.pages.iu.edu/quantum/QuestOrdEff.pdf).

Também investiguei se a rejeição humana poderia ser apenas artefato da grade 21 × 21. Em diagnóstico **exploratório posterior**, minimizei independentemente a mesma perda com evolução diferencial, semente 17, população 25 e tolerância `10⁻¹²`, primeiro no quadrante registrado e depois em `[0,π]²`. Os resíduos máximos foram aproximadamente 0,258343 no primeiro conjunto e 0,180503 no segundo, continuando acima de 0,10. As perdas totais foram 308,654400 e 259,555950. Essa otimização numérica não prova um mínimo global nem altera os números registrados; ela reduz a suspeita de que a conclusão negativa dependa somente da grade grosseira.

Repartir os mesmos agregados cinco vezes é diagnóstico de sensibilidade, sem novas pessoas ou réplica empírica. O limiar de resíduo é uma regra de adequação do piloto, sem significância populacional. A sonda lógica que troca conjunção por um limiar de probabilidade contextual é uma contraprova válida a essa substituição, mas não uma avaliação da lógica quântica inteira. São adequadas as decisões de não delegar implicação a esse mecanismo e de não adquirir hardware sem algoritmo com vantagem demonstrada.

### Aprendizagem, seleção ativa e invenção local

No piloto cognitivo v4, verifiquei a disjunção das entradas em todas as 360 condições e recalculei **os 720 MSEs dos modelos neurais diretamente dos pesos, escalas e entradas de avaliação salvos**. A diferença para os valores registrados foi zero. Conferi 693 consultas, 24 condições de invenção e os nove resultados do fluxo integrado. A reprodução funcional completa é responsabilidade do QA, separadamente documentada.

O resultado afim com dois exemplos limpos distingue bem aprendizagem de otimização: mínimos quadrados atinge erro zero; a rede tem MSE médio 1,31555 dentro do orçamento de 300 épocas. Com 16 exemplos quadráticos limpos, a rede afim falha (MSE 371,569), a base quadrática fornecida melhora a rede (MSE `8,89758 × 10⁻⁵`), e mínimos quadrados sobre a **mesma base** atinge MSE `1,29066 × 10⁻²⁹`. Não há evidência para atribuir vantagem à rede ou abstração descoberta à inclusão de `x²`.

Cada tarefa treina pesos novos. A comparação entre famílias examina adequação de representações e adaptação por tarefa; não demonstra transferência de pesos aprendidos em uma família para outra ou metaprendizagem. Os modelos com abstenção têm cobertura separada do erro condicionado a responder. Uma amostra insuficiente não identifica coeficientes só porque um neurônio produz uma curva.

A consulta ativa empata com as alternativas porque duas retas distintas que passam pelo mesmo ponto se distinguem em qualquer outro ponto. O desenho fornece uma referência simples, mas tem pouco poder para comparar políticas de aquisição. As ablações de memória e busca retiram, respectivamente, evidência e a possibilidade de compor as ações necessárias; seus resultados 0/6 demonstram essa dependência operacional. O núcleo completo e o núcleo sem rede obtêm 6/6. A injeção de seis programas incorretos confere o verificador; não estima taxa natural de erro.

Assinaturas canônicas e execução de programas justificam falar em novidade para a memória e síntese no idioma aritmético fornecido. Não justificam novidade de mecanismo científico, originalidade geral ou validação física. Os resultados de intenção preservados — treino 100%, avaliação 58–68% em três sementes — também não sustentam compreensão aberta. É proporcional manter essa rede sem autoridade decisória.

## Achados por gravidade e ações

**Não identifiquei achado crítico ou de alta gravidade que invalide os resultados negativos examinados.** As classificações abaixo dizem respeito ao alcance da conclusão e à clareza do dossiê, não a novos critérios retrospectivos para fazer um piloto passar.

1. **Gravidade média — contagem e unidade do erro TUM.** A redação inicial “240 posições futuras” podia sugerir 240 poses independentes ou erro de distância 3D. Ação concluída e conferida nesta revisão: SCIENCE_MOTION_TRANSFER e SCIENCE_RESULTS agora declaram 80 poses/240 coordenadas, 24 segmentos eixo × janela e RMSE escalar, sem alterar o piloto.
2. **Gravidade média — limites do experimento contextual.** A grade de ângulos e a equivalência deliberada delimitam o que se pode rejeitar/comparar. Ação concluída e conferida: SCIENCE_PROTOCOL explicita o quadrante `[0,π/2]²`, mantém o empate como controle de equivalência e restringe a rejeição ao modelo/orçamento registrados. O refinamento independente acima preserva o negativo e não autoriza rejeição de todo o formalismo.
3. **Gravidade média — significado de transferência e contribuição neural.** Novo ajuste em cada tarefa não demonstra reutilização de aprendizado entre famílias. Ação concluída e conferida: COGNITION_RESULTS distingue o novo ajuste por tarefa da transferência de pesos e apresenta o MSE do comparador quadrático com a mesma base junto da rede. Os arquivos congelados foram preservados.
4. **Gravidade média — independência empírica e limites de incerteza.** NIST é o mesmo corpus certificado; TUM é uma sequência pública; partições humanas reutilizam agregados. Ação: preservar essas limitações e manter F10-07 aberto. Nova coleta não é requisito para concluir este parecer, mas continua necessária quando a alegação futura exigir validação física ou replicação independente apropriada.
5. **Gravidade baixa — referências de estado desatualizadas.** SCIENCE_RESULTS inicialmente chamava v5 de atual e SCIENCE_DISCOVERY ainda pedia a aquisição TUM já executada. Ação concluída e conferida: estado corrente atualizado para v7 e avaliação TUM negativa concluída, mantendo versões anteriores. Relatórios históricos não foram reescritos.
6. **Gravidade baixa — cronologia de registro e revisão sem mascaramento.** Hashes e arquivos locais preservam versões, mas não comprovam cegamento ou independência institucional. Ação: declarar as emendas posteriores, origem conhecida pelo revisor e natureza de revisão por IA. Esses limites constam deste parecer e do piloto cognitivo; uma alegação confirmatória futura precisará de novo corte e registro anterior à avaliação pertinente.

As correções documentais dos achados 1, 2, 3 e 5 foram relidas pelo revisor; os achados 4 e 6 permanecem como limites científicos explicitamente documentados. Não resta correção bloqueante identificada por este parecer. O QA conserva a responsabilidade pelo aceite final. Este documento registra achados mesmo quando foram corrigidos na mesma execução. Recomendações para futuros domínios — novas trajetórias com condições apropriadas, erros nas variáveis, tarefas com real discriminação entre consultas e famílias de adaptação inéditas — são próximas pesquisas, não condições artificiais para aceitar os resultados negativos atuais.

## Parecer de utilidade, novidade e requisitos

**Utilidade:** o dossiê é útil como laboratório reproduzível de testes pequenos, comparação com referências fortes, detecção de falhas e controle de promoção. A evidência favorece manter mínimos quadrados nas tarefas lineares nas características, a busca verificável no domínio aritmético e o registro persistente de contraprovas. Não há utilidade metrológica, ganho físico real ou ganho neural/quântico demonstrado além desse alcance.

**Novidade:** não foi demonstrada novidade científica. Há aprendizagem de parâmetros dentro de classes fornecidas e composição nova para a memória local. Cinemática constante, relação NIST, bases polinomiais, fatoração probabilística contextual e idioma de composição incorporam conhecimento anterior. O parecer não é uma avaliação de patentes nem prova de inexistência de trabalhos relacionados.

**F10-06:** recomendo o aceite da entrega de dossiê e revisão especializada **por agente de IA**, conforme autorização do usuário, após conferência das ações documentais pelo QA. O parecer concreto avaliou matemática, fontes, utilidade e novidade e reproduziu contas relevantes. A conclusão desfavorável a superioridade/novidade é um resultado admissível da revisão.

**F11-08:** a matriz de responsabilidades, competências e estimativas existe; o revisor especializado agora participou efetivamente, com escopo, independência e limitações identificados. Recomendo o aceite dessa participação por IA sob a autorização registrada, sem atribuir credenciais profissionais humanas ao agente ou converter estimativas de planejamento em esforço efetivamente medido.

**F10-05 e F10-07:** permanecem abertos. Uma revisão favorável à documentação não fornece solução de problema aberto nem réplica empírica independente. O resultado TUM negativo não replica uma descoberta da calibração NIST, e os testes da DSL não constituem medição do mundo.

O aceite de requisitos pertence ao QA independente. Este parecer é revisável se aparecerem novos dados, mudanças nos artefatos identificados ou contraprovas; não confere autorização para ampliar as afirmações além dos experimentos descritos.
