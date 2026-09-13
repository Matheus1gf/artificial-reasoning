# Parecer de QA sobre o planejamento do objetivo

Revisão documental por `/root/qa_specialist`, em 12/09/2026, de [OBJECTIVE_PLAN.md](../OBJECTIVE_PLAN.md) e [TODO.md](../../TODO.md). **Este parecer avalia o planejamento; não aprova capacidades, implementações novas ou resultados científicos.** Não foram executados testes de código nem reavaliados arquivos de resultados nesta revisão.

**Conclusão final:** parecer favorável à consistência do planejamento, após os quatro ajustes abaixo serem tratados e relidos. O plano corrigiu a confusão entre entrega experimental e aquisição de capacidade. A regra transversal afirma que um resultado negativo pode encerrar um experimento, mas não alcança C01–C08. As fases históricas ficam preservadas, F12 mantém requisitos abrangentes e F13–F21 desdobram sua execução. O marco M1 exige estrutura aprendida além dos coeficientes afins, tarefa nova pelo chat e contribuição causal do estado aprendido. Não ficou pendência documental bloqueante identificada nesta revisão.

## Conferência de estrutura

- C01–C08 aparecem uma vez cada na tabela de capacidades, todos sem alegação de aquisição ampla.
- Foram encontrados48 itens F13–F21, todos abertos, e nenhum ID de tarefa duplicado no TODO.
- Os62 links locais do TODO e os5 do plano apontam para caminhos existentes. Foram conferidos caminhos locais, não o conteúdo de referências externas ou seus resultados científicos.
- As seis exigências F12 têm fases filhas e não são encerradas automaticamente pela conclusão de um filho. F10-05/F10-07 continuam distintos do aceite de software.
- Dados, comparadores, recursos, experiência prévia, limiares, amostragem e critérios de interrupção têm execução prevista em F13. Linguagem natural, transferência, intervenção, retenção e invenção possuem tarefas explícitas nas fases seguintes.

## Achados encaminhados e corrigidos

| ID | Local e problema | Ajuste necessário |
| --- | --- | --- |
| P1 | TODO, seção5: os novos limiares ainda são atribuídos a F00-06, enquanto o plano e a F13 os atribuem ao novo contrato. | Referir F13-01 para os novos marcos; preservar F00-06 como protocolo histórico, sem revisão retroativa do reservado. |
| P2 | F13-02 separa dados e congela o candidato; o plano exige que o mecanismo oculto não vaze. Falta tornar a proteção uma entrega executável e auditável. | Incluir isolamento entre aprendiz e avaliador, interface de observações limitada pelo orçamento e auditoria de acesso a mecanismos, respostas, arquivos e caches. A separação nominal dos agentes ou dos arquivos não prova independência. |
| P3 | F18-04 exige “restrições não usadas na busca”. A frase pode significar avaliar o artefato contra requisitos nunca fornecidos ao sistema. | Distinguir requisitos e envelope de operação informados de valores, cenários e condições de teste reservados. Requisito novo exige nova revisão do projeto; não pode ser critério oculto de aprovação da meta anterior. |
| P4 | M1 inclui escolha de observação informativa; F16-06 executa M1, mas a experimentação está em F17, que depende de candidatos da F16. | Explicitar a ordem entre entregas: candidatos iniciais F16 → investigação F17 → integração/avaliação de M1 em F16-06/F21. Evitar interpretar a fase inteira F16 como pré-condição para iniciar F17 ou concluir M1 antes da experimentação necessária. |

Esses ajustes foram incorporados aos itens existentes, sem trocar os marcos nem aumentar artificialmente o número de tarefas. A ausência de limiares numéricos definitivos hoje não é um falso aceite: defini-los antes de pontuar o novo teste é precisamente uma tarefa aberta da F13.

O reteste documental confirmou P1 na seção5 do TODO, P2 em F13-02, P3 em F18-04 e P4 na sequência interna da F16 e na seção8 do plano. Todos estão **corrigidos e relidos**. Também foram conferidas as emendas da revisão científica: arquiteturas candidatas podem ser substituídas, inadequação da classe exige evidência, fidelidade de um simulador quântico é distinta de vantagem e o diagrama verifica a fidelidade após o redator, com retorno à renderização determinística.

O próximo passo recomendado é executar F13 e registrar o contrato de M1. Esta revisão não executou F13 nem modificou o chatbot. C01–C08 continuam sem aceite de capacidade; concordância deste revisor com a direção do plano não altera esse estado. Não foi concedido aceite antecipado a nenhum item F13–F21, nem reclassificado resultado experimental negativo como competência adquirida.
