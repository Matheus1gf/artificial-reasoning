# Transferência para movimento medido — F06-08

Em 12/09/2026, o modelo de aceleração constante foi confrontado com uma trajetória física externa. **O portão de transferência falhou.** A engenharia agora mede a diferença entre simulação e realidade e bloqueia a promoção quando os critérios registrados não são atendidos. Isso não demonstra sucesso de previsão física.

## Fonte e significado das medidas

A sequência TUM RGB-D **fr1/xyz**, de Sturm, Engelhard, Endres, Burgard e Cremers, contém posições de uma câmera movida manualmente diante de uma mesa, obtidas por captura de movimento externa. A orientação foi mantida aproximadamente fixa; forças e acelerações não foram controladas. Analisamos cada coordenada mundial independentemente, sem afirmar que a trajetória tridimensional inteira é retilínea. [Descrição primária](https://cvg.cit.tum.de/data/datasets/rgbd-dataset/download#testing_and_debugging).

Os tempos estão em segundos desde a época Unix; os gráficos do artigo expressam as posições em metros. Na seção VI.C, os autores relatam erro absoluto inferior a 10 mm na área de captura e relativo entre quadros inferior a 1 mm. São estimativas empíricas do sistema, não covariância certificada por amostra. Usamos 10 mm como escala condicional de sensibilidade; não tratamos erro de um quadro como incerteza de vários segundos. Covariância por pose, correlação temporal e incerteza do timestamp não foram disponibilizadas. [Formato primário](https://cvg.cit.tum.de/data/datasets/rgbd-dataset/file_formats), [artigo IROS 2012](https://cvg.cit.tum.de/_media/spezial/bib/sturm12iros.pdf).

A [página atual do conjunto](https://cvg.cit.tum.de/data/datasets/rgbd-dataset) declara CC BY 4.0. [Atribuição](../../experiments/science/corpus/NOTICE-TUM.md) e [metadados](../../experiments/science/corpus/tum-fr1-xyz.metadata.v1.json) registram origem, licença, transformações e limites. O arquivo bruto tem 3.000 poses/201.100 bytes; o download primário de 12/09 reproduziu exatamente o arquivo preservado da sessão anterior. Não usamos imagens pessoais.

## Protocolo e controle de vazamento

O [protocolo v1](../../experiments/science/motion-transfer.protocol.v1.json) foi gravado antes de qualquer ajuste ou pontuação. Não é teste cego: o conjunto era público, já havia sido baixado e suas primeiras linhas tinham sido vistas. Os índices não foram selecionados pelo resultado.

- Oito janelas começam em 0, 4, 8, 12, 16, 20, 24 e 28 segundos.
- Cada janela usa 20 amostras espaçadas aproximadamente 0,1 s, associadas por timestamp com tolerância de 0,02 s, sem interpolação ou duplicação.
- Dez posições iniciais ajustam x0, v0 e a por mínimos quadrados; as dez posteriores entram somente na avaliação. Três eixos totalizam 24 segmentos eixo × janela: 80 poses 3D de ajuste e 80 poses 3D futuras, correspondentes a 240 coordenadas escalares em cada partição. Os eixos e tempos da mesma trajetória não são réplicas independentes.
- Comparamos aceleração constante, velocidade constante e persistência da última posição. Os primeiros modelos usam o integrador do projeto; posições analíticas do ajuste servem apenas como controle de erro numérico.
- O portão exige todos os segmentos no domínio, RMSE total até 0,03 m, erro máximo até 0,10 m e ganho mínimo de 5% contra persistência.

A sensibilidade a erros nas posições usa pesos da previsão por mínimos quadrados: `0,01 × (1 + Σ|peso|)` m. Inclui erro das entradas de ajuste e da medida futura sob uma hipótese de erro limitado. Não substitui covariância, erro de estrutura ou temporal. Não calculamos intervalos que tratem eixos/janelas correlacionados como réplicas independentes.

## Resultado

O RMSE abaixo agrega erros de coordenadas escalares em metros; não é distância Euclidiana 3D por pose.

| Modelo | RMSE nas 240 coordenadas futuras | Maior erro absoluto |
| --- | --- | --- |
| Aceleração constante | 0,141737 m | 0,791546 m |
| Velocidade constante | 0,154486 m | 0,526659 m |
| Última posição observada | 0,099956 m | 0,410300 m |

Todos os segmentos ficaram no domínio numérico. Quinze dos 24 excederam RMSE local de 0,03 m. O erro máximo do integrador contra o controle analítico foi `1,9984×10⁻¹⁵ m`, muito menor que a diferença perante as posições medidas. Precisão numérica não garantiu adequação do modelo. O modelo perdeu para persistência, falhou nos limites de RMSE/erro máximo e recebeu `constant_acceleration_transfer_rejected`, com `new_physical_law=false`.

A conclusão é rejeitar a promoção da hipótese local de aceleração constante para estes intervalos. O movimento manual tem ação externa desconhecida e pode variar a aceleração; o resultado não refuta a cinemática Newtoniana nem sugere automaticamente uma nova força ou lei.

O [registro v7](../../experiments/science/registration.v7.json) precede o [relatório v7](../../experiments/science/results/pilot.v7.json); 24 hashes coincidem. O relatório preserva falhas anteriores, inclusive NIST e equivalência quântica/clássica. O QA aprovou a nova entrega em 12/09/2026: seis testes adicionais cobrem a transferência e a integração no chat, totalizando 40 testes científicos. A aprovação da avaliação não muda a rejeição da hipótese física.

## Uso integrado e revisão

O dispatcher local usa protocolo fixo, sem Qwen, rede ou parâmetros que mudem os critérios após observar resultados:

```json
{"domain":"physics","operation":"measured_transfer","parameters":{}}
```

A resposta propaga `status=answered` para a avaliação concluída, com `physical_transfer_promoted=false`, rejeição explícita da hipótese, métricas, origem e limitações. A verificação de execução é separada da promoção científica. Reprodução exige destinos novos:

```sh
python3 scripts/evaluate_science.py --register --output /tmp/ar-science-register.json
python3 scripts/evaluate_science.py --output /tmp/ar-science-report.json
```

F06-08 pode receber aceite de engenharia para o portão testado com resultado negativo real. **Transferência positiva e expansão para problemas maiores permanecem bloqueadas.** Reabrir exige outra sequência independente, condições/forçamento adequadamente conhecidos, modelo revisado e critérios registrados antes de pontuar. Esta experiência não conclui problema aberto F10-05, revisão externa F10-06 ou replicação de descoberta F10-07.

Para o revisor independente: conferir seleção anterior ao ajuste, corte temporal, unidades, interpretação dos limites empíricos, diferença entre controle numérico e observação independente, perda contra persistência e se a conclusão permanece restrita ao modelo/intervalos testados. Código em `src/science/motion_transfer.py`; protocolo, dados e relatório estão ligados acima. Nenhuma aquisição de hardware ou serviço pago foi feita; a execução completa v7 levou cerca de 4,06 s nesta máquina, sem inferência de LLM.
