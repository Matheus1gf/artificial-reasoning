# Dossiê de redescoberta controlada — calibração publicada pelo NIST

Data original: 09/09/2026; atualizado em 12/09/2026. Estado: estudo numérico executável, com **novidade científica não alegada**. A [revisão científica por agente de IA independente](SCIENTIFIC_REVIEW_AI.md) foi concluída na retomada; não houve revisão humana externa.

## Problema, origem e autorização de uso

Problema delimitado: prever a medição de um cliente a partir de uma medição de referência, no conjunto observado de calibração de monitores de ozônio **Norris**, do NIST. Há 36 pares observados; a publicação fornece parâmetros certificados para conferir algoritmos de regressão. A [página do conjunto](https://www.itl.nist.gov/div898/strd/lls/data/Norris.shtml) e a [descrição das variáveis](https://www.itl.nist.gov/div898/strd/lls/data/LINKS/i-Norris.shtml) são as fontes primárias. Isso oferece uma referência acessível para a confiabilidade do cálculo, sem estabelecer ganho científico novo.

O corpus contém o arquivo original, uma derivação com valores numéricos, metadados e [aviso de atribuição](../../experiments/science/corpus/NOTICE-NIST.md). Os dois arquivos de dados têm hashes SHA256 conferidos em cada carga. A [política do NIST](https://www.nist.gov/open/license) distingue dados de empregados e produtos SRD licenciados; a documentação identifica autoria NIST e preserva o aviso e a atribuição. Não se afirma que todos os produtos NIST sejam livres de restrições.

O arquivo não declara a unidade de concentração nem a incerteza instrumental ou condições detalhadas dos monitores. Esses campos permanecem `unspecified`. O desvio residual publicado não é substituto da incerteza instrumental. O corpus pode alimentar o estudo numérico, mas `physical_interpretation_approved=false` impede apresentá-lo como uma calibração metrológica validada.

## Separação entre aprendiz e avaliador

O aprendiz recebe apenas medições `{variables:{q:valor},target:valor}`. Não recebe título, equação publicada, parâmetros certificados, identificador do instrumento ou descrição semântica. O método enumera uma gramática polinomial de grau até dois e até dois termos, estima coeficientes e seleciona por erro mais complexidade.

Índices com resto diferente de zero na divisão por três são usados para ajuste: 24 pares. Os 12 restantes são usados na avaliação declarada. O conjunto é público e conhecido; essa separação permite medir previsão neste recorte, mas não o torna um teste secreto de inteligência. A comparação contra valores certificados usa os 36 pares em um ensaio separado de precisão numérica; não participa da seleção da expressão.

As referências são média constante e mínimos quadrados ordinários. Critério prévio de utilidade do piloto: reduzir RMSE frente à média e igualar o comparador linear em até `10⁻⁸`. O critério é de confiabilidade numérica no conjunto, não de adoção de um instrumento real. Se uma parte falhar, ela deve constar no relatório; não alterar a penalização após observar o teste para produzir um aceite retrospectivo.

## Trabalho anterior e avaliação de novidade

O [catálogo de fontes primárias](../../experiments/science/corpus/prior-art.v1.json) registra consultas, fontes, relações conhecidas e limites. `src.science.discovery.prior_art_search` permite consultar esse catálogo pelo núcleo. A busca inicial identificou a relação afim no próprio NIST, além de regressão simbólica e descoberta de equações em trabalhos anteriores.

Classificação deste resultado:

- **Novo para o aprendiz:** o algoritmo estimou coeficientes usando as observações permitidas.
- **Conhecido no conjunto:** a relação e parâmetros de referência já estavam publicados.
- **Novidade científica:** não demonstrada. Uma busca em cinco fontes não equivale a uma revisão sistemática ou busca exaustiva de anterioridade.

Não houve contato com pessoas ou especialistas externos. Um agente de QA pode verificar cálculo, isolamento de dados e reprodução do programa; isso não substitui a revisão científica independente ou uma validação instrumental.

## Hipóteses e condições de refutação

| Hipótese | Previsão prévia | Resultado que a refuta ou limita |
| --- | --- | --- |
| Relação polinomial simples é útil nestes pares | Superar média em novos pares | RMSE igual ou pior que a média |
| Penalização adotada preserva a qualidade do comparador afim | Diferença de RMSE ≤10⁻⁸ | Diferença maior; registrar perda, sem ajustar o protocolo após o teste |
| Implementação QR reproduz o certificado | Coeficientes próximos aos valores publicados | Diferença relevante em caso numérico benigno exige revisão |
| Resultado pode sustentar uso metrológico | Unidade, incerteza, condições e validação independente disponíveis | Metadados ausentes mantêm esse uso sem aprovação |

## Próximas condições para avançar

F06-08 foi avaliado separadamente com a [trajetória medida TUM](SCIENCE_MOTION_TRANSFER.md), unidades, procedência e limites de medição. A transferência do modelo de aceleração constante foi rejeitada. Os pares de ozônio continuam sem demonstrar transferência da mecânica simulada.

Para F10-05: formular um problema aberto depois de satisfazer os critérios anteriores, com nova separação de dados e pré-registro. O resultado atual é uma referência de redescoberta; nenhuma proposta foi promovida a descoberta aberta.

Para F10-06: este dossiê contém método, dados, artefato, resultado, limitações e reprodução. O [agente especialista independente](SCIENTIFIC_REVIEW_AI.md) avaliou novidade e utilidade por solicitação do usuário, reproduziu os cálculos e conferiu as correções documentais. Seu parecer é favorável ao dossiê delimitado, sem novidade científica demonstrada. O aceite individual consta da matriz de QA e identifica explicitamente a revisão por IA.

Para F10-07: a referência NIST constitui verificação numérica independente do programa, mas usa os mesmos dados. Ainda falta replicação com novas medições, outro conjunto independente ou uma experiência instrumental adequada. Resultados negativos devem ser preservados, inclusive ausência de transferência ou melhoria real.
