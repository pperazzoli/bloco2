# Project Charter — Bússola ESG Educação

**Estágio TDSP:** 1. Business Understanding · **Data:** 2026-08-24
**edited 21-09-2026:** escopo, riscos, arquitetura e marcos revisados. O que entrou nesta
revisão está indicado no início de cada seção.
**edited 16-11-2026:** problema de negócio reavaliado à luz das novas ferramentas (FastAPI e
Selenium), escopo estendido ao serviço HTTP e à preparação para LLM, riscos e arquitetura
revisados. O que entrou nesta revisão está marcado *edited 16-11-2026*.
**edited 25-11-2026 (TP5):** terceira reavaliação, com a solução final — o assistente com
memória sobre os dados do projeto (seção 1.3); objetivos, metas, riscos, ética, arquitetura e
marcos atualizados. O que entrou nesta revisão está marcado *edited 25-11-2026 (TP5)*.

---

## 1. Problema de negócio

Empresas com agenda ESG investem em educação básica, mas decidem onde aplicar o recurso
por relacionamento, e não por evidência. O dado público existe — INEP e IBGE publicam
indicadores abertos — porém disperso entre microdados e APIs distintas, inacessível a quem
decide. No reporte de sustentabilidade, o impacto é descrito de forma qualitativa, sem
rastreabilidade até a fonte oficial, o que expõe a empresa a risco de *social washing*.

**Solução.** Aplicação que ranqueia territórios por prioridade de investimento a partir dos
indicadores oficiais da ODS 4 e gera o reporte ESG com a fonte de cada número registrada.

### 1.1 Reavaliação do problema à luz das novas ferramentas

*Adicionado em novembro — TP3.*

O problema de negócio não mudou: a decisão de alocação continua sendo tomada por
relacionamento, e o reporte continua exposto ao risco de *social washing*. Mudou o
diagnóstico de **onde** o projeto encontra o seu limite, e as duas ferramentas desta etapa
foram avaliadas contra isso.

**1.1.1 FastAPI — adotado.** O painel atendia ao usuário que olha a tela. Não atendia a dois
usuários reais já identificados na seção 6: o instituto que mantém a própria planilha de
cobertura de programas, e o comitê de ESG cuja área de dados consolida indicadores em BI
corporativo. Para esses, exportar CSV pela interface e reimportar em outro sistema é trabalho
manual repetido a cada atualização. O serviço HTTP resolve isso sem alterar o problema de
negócio — é o mesmo dado, pelo canal que o sistema do usuário consome. Também separa o que
estava acoplado: o cálculo do índice deixou de ser função da interface e passou a ser serviço
com contrato declarado, o que o torna verificável de fora.

**1.1.2 Selenium — avaliado e dispensado.** O projeto raspa quatro sites. A Agência Brasil
entrega a listagem da editoria em HTML servido pelo servidor, paginado por parâmetro de URL —
não há conteúdo que dependa de JavaScript. Os outros três são WordPress atrás de Elementor:
a listagem **depende** de JavaScript, e é por isso que o ponto de entrada passou a ser o XML
de sindicação de cada site na etapa anterior. O feed é interface estável, publicada pelo
próprio site para consumo automatizado, e entrega o mesmo conteúdo da listagem dinâmica com
menos requisições e sem navegador. Automatizar um navegador para obter o que um feed entrega
em uma requisição acrescentaria dependência de binário externo, tempo de execução e
fragilidade, sem acrescentar dado. A decisão, com a justificativa técnica detalhada, está
registrada na seção 1.4 do Data Summary Report; fica reaberta se alguma fonte futura exigir
interação — formulário de consulta, filtro que só existe no cliente ou rolagem infinita sem
feed equivalente.

**1.1.3 LLM — preparação, não implementação.** A etapa de IA generativa altera o escopo da
solução de "painel que mostra" para "sistema que também redige". Isso toca diretamente o
risco 8.4, e por isso a preparação foi documentada antes de qualquer código:
[`../3_modeling/plano_llm.md`](../3_modeling/plano_llm.md) registra as tarefas previstas, os
insumos de cada uma e as contenções exigidas.

### 1.2 Segunda reavaliação: o modelo de linguagem local

*Adicionado em novembro — TP4.*

O problema de negócio continua o mesmo. O que a exigência de **execução local** mudou foi
qual tarefa de linguagem o projeto podia de fato entregar nesta etapa, e a mudança foi na
direção oposta à prevista.

**1.2.1 A ordem planejada se inverteu, e isso é decisão de negócio, não detalhe técnico.** O
`plano_llm.md` pôs em primeiro lugar as tarefas gerativas — a narrativa do reporte ESG e o
resumo das matérias —, porque são as que mais poupam tempo do analista. Ambas exigem modelo
gerativo, e um modelo gerativo útil em português leva dezenas de segundos por item num
processador sem GPU. A tarefa de classificação, terceira na lista, roda em dezenas de
milissegundos. Em um ambiente local sem GPU, a tarefa menos valiosa é a única viável.

**1.2.2 Duas tarefas entraram, e elas não têm o mesmo risco.** A classificação de sentimento
foi implementada primeiro. A tarefa de **resumo**, gerativa, entrou em seguida, depois que a
medição mostrou um modelo em português que resume uma matéria em cerca de 4 segundos em CPU —
custo aceitável para uma matéria por vez, proibitivo para o corpus em lote. O resumo é
oferecido nesse formato e só nesse.

A distinção entre as duas atravessa o sistema inteiro, no campo `gerativo` que a API devolve
e a tela exibe. Um classificador escolhe entre três rótulos fixos: **não há número a inventar
nem frase a fabricar**. Um modelo de resumo redige, e pode afirmar o que não está no texto.

**1.2.3 O risco 8.4 foi reaberto pela própria entrega.** Uma versão anterior deste documento
registrou que a escolha de um classificador *eliminava* o risco 8.4 em vez de administrá-lo.
Isso valia enquanto havia só o classificador. Com a entrada do resumo deixou de valer: na
verificação, o modelo produziu **uma data, um estado e uma cifra que não estavam no texto de
entrada**. Os dois casos estão transcritos na seção 5.2 de
[`../3_modeling/modelo_llm.md`](../3_modeling/modelo_llm.md), e o risco 8.4 abaixo foi
atualizado com o que a entrega faz a respeito.

**1.2.4 O que o usuário ganha, em escala honesta.** O rótulo de sentimento acrescenta direção
ao volume de menções que a página de notícias já mostrava: deixa de ser "o estado aparece em
12 matérias" e passa a ser "aparece em 12, das quais 2 em tom negativo". É camada de
contexto, não de medição — e, no corpus atual, formado em boa parte por comunicação
institucional, a maioria das matérias é classificada como neutra, o que é descrição correta
do material. O resumo serve a uma decisão menor e concreta: **se vale ler a matéria inteira**.
Para citar, não serve, e a interface diz isso ao mostrar o resumo gerado ao lado do resumo
escrito pela redação. A decisão completa, com os quatro modelos medidos e os números de cada
um, está em [`../3_modeling/modelo_llm.md`](../3_modeling/modelo_llm.md).

**1.2.5 O que ficou fora, e por quê.** A narrativa do reporte ESG — a tarefa de maior valor
para o usuário — continua fora, e agora por um motivo mais forte que o custo: **um modelo que
inventa cifras ao resumir não pode redigir um relatório que cita cifras.** Fazê-la exigiria
ou um modelo muito maior, com GPU ou provedor remoto, ou uma arquitetura em que todo valor do
texto gerado seja verificado contra a tabela de origem antes de ser exibido. A segunda é a
que respeita o risco 8.4, e é trabalho de outra entrega.

### 1.3 Terceira reavaliação: a solução final, um assistente com memória sobre os dados

*Adicionado em novembro — TP5.*

O problema de negócio é o mesmo desde o TP1, e esta seção registra como a solução final o
resolve — e por que dados, IA e engenharia de prompt aparecem nessa ordem de importância.

**1.3.1 O que faltava ao painel.** As oito páginas respondem a quem sabe onde clicar. O
usuário primário (seção 6.1) usa planilha e BI, não programa, e a sua pergunta real é
encadeada: "quais territórios priorizar?", "por que esse?", "e comparado com aquele?", "o que
a imprensa diz?". No painel, cada uma dessas perguntas é uma página, um filtro e uma leitura
de tabela; o diagnóstico territorial comparado, que a meta 4.5 quer em menos de cinco
minutos, depende de o usuário saber montar o caminho. O assistente aceita a pergunta como o
analista a faria a um colega, **lembra o que já foi conversado** e responde com o número, a
fonte e a conferência. É a mesma base de dados, por um canal que dispensa saber o caminho.

**1.3.2 O dado é o centro, o modelo é a interface.** A primeira medição desta etapa foi
perguntar ao modelo, sem dado nenhum, o que mede a taxa de alfabetização: ele respondeu, com
segurança, que ela "é medida pelo IDH e pelo IDE" — o que é falso. Com o ranking do projeto
no prompt, devolveu as cinco UFs prioritárias com os cinco índices exatos. O valor da
solução não vem do modelo: vem das 189 observações coletadas da API do IBGE, das 105
matérias raspadas e do índice que `nucleo.py` calcula sobre elas. O modelo **lê** esses
números e redige sobre eles; não sabe, não calcula e não estima nada. É a regra 1 do risco
8.4, fixada no TP3 antes de haver modelo, levada ao pé da letra: até a média, a diferença e a
posição de cada UF chegam prontas no prompt. A verificação da seção 6 de
[`../3_modeling/assistente_llm.md`](../3_modeling/assistente_llm.md) mede o que acontece sem
os dados.

**1.3.3 A engenharia de prompt é a governança aplicada ao texto gerado.** Cada regra do
prompt traduz uma regra deste documento: não produzir número (risco 8.4), não fazer previsão
nem recomendação de investimento financeiro (escopo 2.2), não ler o índice como mérito
(seção 9), não ler notícia como medida do território (risco 8.6), citar a matéria que
sustenta a resposta (tarefa 2.4 do plano de LLM). A forma do contexto foi ajustada falha a
falha: seis respostas erradas observadas no desenvolvimento viraram seis mudanças, e três
delas tinham todos os números certos e a relação errada — posição contada errado, contagem
atribuída à UF errada, comparação invertida. Num reporte ESG, esse é o erro mais perigoso,
porque passa por qualquer conferência de número. A seção 4.4 do documento do assistente
registra os seis casos.

**1.3.4 Um caminho, e por quê.** Das três opções do enunciado, foi escolhida a memória
conversacional. A sumarização já tinha sido levada no TP4 até onde ela serve — uma matéria
por vez, com conferência — e um agente que propusesse ações tiraria a decisão dos pesos
explícitos, que o risco 8.3 existe para proteger. O assistente apoia a decisão sem tomá-la.
Entre modelo local e API online, foi escolhido o local: o `llama3.1:8b`, servido pelo Ollama
nesta máquina, já estava instalado, fala português e mantém o compromisso de soberania do
dado da seção 9 — nenhuma pergunta sai do computador. O problema não pede um modelo maior,
porque o modelo não precisa saber nada sobre educação: precisa ler bem uma tabela.

**1.3.5 O que o usuário ganha, em escala honesta.** Uma conversa de três perguntas — as
prioritárias, por que a primeira, como ela está num indicador — leva menos de um minuto e
devolve os números com a fonte, em vez de três páginas e duas tabelas. O ganho é de
**acesso**, não de dado novo: o assistente não sabe nada que o painel não mostre. E tem
limite declarado: a conferência pega número inventado, não pega número verdadeiro posto no
lugar errado (risco 8.15), e por isso cada resposta vem com o gráfico, as fontes e o bloco de
dados que o modelo leu, à vista.

---

## 2. Escopo

**2.1 Inclui** — coleta via API dos indicadores oficiais da ODS 4; Índice de Prioridade de
Investimento por Unidade da Federação; painel interativo de ranking; geração do reporte ESG
com rastreabilidade de fonte, ano e URL.

*edited 21-09-2026* — o TP2 acrescentou ao escopo: extração de conteúdo jornalístico da web
com Beautiful Soup como camada de contexto qualitativo; nuvem de palavras e estatísticas
descritivas desse conteúdo; serviço de upload e download de CSV para que o usuário
complemente a base com dados próprios; e a publicação da aplicação com controle de versão
em Git.

*edited 16-11-2026* — o TP3 acrescentou ao escopo: serviço HTTP em FastAPI que expõe os
indicadores, o índice de prioridade e o corpus de notícias a consumidores externos, com
rota de escrita para dado próprio do usuário; extração do núcleo de dados e cálculo para um
módulo sem dependência de interface, de modo que painel e serviço devolvam o mesmo número; e
a especificação documentada das tarefas de LLM a implementar na etapa seguinte.

*edited 25-11-2026 (TP5)* — a solução final acrescentou ao escopo: o assistente
conversacional com memória, que responde em linguagem natural sobre os indicadores, o índice
e as notícias a partir dos dados já apurados, por modelo local; a conferência de cada
resposta contra esses dados; a visão do ciclo completo, do dado ao insight, na página inicial
do painel; e o relatório final do projeto, em `5_customer_acceptance/`.

**2.2 Não inclui** — dados nominais de escolas individuais; dados pessoais de estudantes ou
docentes; avaliação jurídica de entidades beneficiadas; recomendação de investimento
financeiro. *edited 21-09-2026:* também está fora de escopo qualquer modelo preditivo — o
índice é composição determinística de indicadores observados, não previsão. *edited
16-11-2026:* também está fora de escopo a persistência do dado enviado pelo usuário — nem o
upload de CSV nem a rota de escrita da API gravam em disco, por decisão registrada no risco
8.8; e está fora de escopo publicar o serviço HTTP em rede aberta, que exigiria autenticação,
limite de requisições e CORS restrito, conforme a seção 4.1 da Referência da API. *edited
25-11-2026 (TP5):* também está fora de escopo guardar as conversas com o assistente — a
memória vive na sessão do usuário e o serviço não guarda estado —, e o assistente recusa,
por regra do prompt, previsão de valor futuro e recomendação de investimento financeiro.

**2.3 Restrição** — os indicadores 4.a.1 e 4.c.1 do IBGE só descem até o nível de UF. A
descida ao nível municipal depende dos microdados do INEP.

---

## 3. Objetivos

*Objetivos 3.5 e 3.6 adicionados em setembro — TP2. Objetivos 3.7 e 3.8 adicionados em
novembro — TP3. Objetivos 3.9 a 3.12 adicionados em novembro — TP4. Objetivos 3.13 e 3.14
adicionados em novembro — TP5.*

**3.1** Coletar via API os indicadores oficiais de monitoramento da ODS 4.

**3.2** Consolidá-los em um Índice de Prioridade de Investimento por território.

**3.3** Disponibilizar o ranking em painel interativo.

**3.4** Gerar o reporte ESG com rastreabilidade de fonte, ano e URL de cada valor.

**3.5** Monitorar a agenda pública da educação por extração de conteúdo web, para
que o diagnóstico quantitativo venha acompanhado do contexto qualitativo do período.

**3.6** Abrir a base à contribuição do usuário por upload de CSV, sem exigir acesso
ao código nem ao repositório.

**3.7** Expor os dados e o índice por serviço HTTP documentado, para que sistemas de
terceiros — BI corporativo, planilha do instituto, notebook de análise — consumam a mesma
informação do painel sem passar pela interface.

**3.8** Preparar o projeto para as tarefas de LLM da etapa seguinte, especificando
tarefas, insumos e contenções antes de implementá-las.

**3.9** Processar o corpus de notícias com modelos de linguagem **executados na própria
máquina**, sem envio de conteúdo a serviço externo: classificação de sentimento, que
acrescenta direção qualitativa ao volume de menções que o painel já media, e resumo, que
reduz o custo de triagem de uma matéria.

**3.10** Garantir que a indisponibilidade de um modelo degrade apenas a funcionalidade dele,
mantendo intactas as rotas e as páginas de dados — e a outra tarefa de linguagem.

**3.11** Tornar visível, na própria interface, o que cada modelo erra: que texto gerado pode
conter afirmação ausente do original, e que `neutro` descreve o registro do texto e não a
situação do território.

**3.12** Entregar todo texto gerado por modelo acompanhado da conferência dos seus números,
datas e nomes próprios contra o texto que o originou, de modo que o que o modelo inventou
apareça apontado e não dependa da atenção de quem lê.

**3.13** Responder às perguntas do analista em linguagem natural, **lembrando a conversa**,
a partir dos dados já apurados pelo projeto — indicadores, índice e notícias —, por modelo
executado na própria máquina.

**3.14** Garantir que todo número citado pelo assistente venha dos dados entregues a ele, e
que cada resposta apareça com as suas fontes e com a conferência do que escreveu contra esses
dados.

---

## 4. Metas e indicadores de sucesso

*Metas 4.8 e 4.9 adicionadas em setembro — TP2. Metas 4.10 e 4.11 adicionadas em
novembro — TP3. Metas 4.12 a 4.16 adicionadas em novembro — TP4. Metas 4.17 a 4.19
adicionadas em novembro — TP5.*

**4.1 Cobertura territorial** — indicador: % de UFs com índice calculado. Alvo: 100%, as 27 UFs.

**4.2 Profundidade do dado** — indicador: número de indicadores oficiais da ODS 4 integrados.
Alvo: pelo menos 6.

**4.3 Rastreabilidade** — indicador: % de valores com fonte, ano e URL registrados. Alvo: 100%.

**4.4 Atualidade** — indicador: defasagem do dado mais recente exibido. Alvo: no máximo 2 anos.

**4.5 Esforço do usuário** — indicador: tempo para produzir um diagnóstico territorial
comparado. Alvo: menos de 5 minutos.

**4.6 Reporte ESG** — indicador: tempo para gerar a minuta alinhada aos ODS. Alvo: menos de
1 minuto.

**4.7 Qualidade do ranking** — indicador: sobreposição do top-10 do índice com a avaliação de
um especialista. Alvo: pelo menos 70%.

**4.8 Cobertura da imprensa** — indicador: número de fontes de conteúdo web
integradas. Alvo: pelo menos 3. **Situação atual: 4 fontes, 105 matérias.**

**4.9 Resposta da interface** — indicador: tempo de resposta a uma troca de filtro
com os dados já em cache. Alvo: menos de 1 segundo.

**4.10 Cobertura do serviço** — indicador: número de rotas HTTP documentadas que cobrem os
ativos do projeto (indicadores, índice, corpus, catálogo de fontes). Alvo: pelo menos 2
rotas, com ao menos uma de consulta e uma de escrita. **Situação atual: 14 rotas, 8 de
consulta, 2 de escrita e 4 de linguagem natural, todas com documentação interativa gerada
pelo FastAPI.** *edited 25-11-2026 (TP5):* 15 rotas — a quinta de linguagem natural é
`POST /assistente`.

**4.11 Paridade entre canais** — indicador: diferença entre o índice devolvido pela rota
`/ranking` e o índice exibido na página de prioridade, com os mesmos pesos e método. Alvo:
zero. Garantido por construção — os dois chamam a mesma função de `nucleo.py`, e não há
segunda implementação do cálculo no projeto.

**4.12 Custo do processamento de linguagem** — indicador: tempo por item em processador
comum, sem GPU. Alvo: que caiba numa interação de painel. **Situação atual: 0,08 s para
classificar uma matéria — o corpus inteiro, 105 matérias, em cerca de 9 segundos — e cerca de
3 segundos para resumir uma, o que mantém o resumo em uma matéria por vez.**

**4.13 Contrato declarado das respostas** — indicador: % das rotas cujo formato de resposta
está declarado na especificação OpenAPI, e não só na documentação escrita. Alvo: 100%.
**Situação atual: 100% — as 14 operações declaram `response_model`, com 26 esquemas gerados.**

**4.14 Degradação contida** — indicador: número de rotas e de páginas que deixam de funcionar
quando um modelo não pode ser carregado. Alvo: nenhuma além das que dependem dele.
**Situação atual: verificado com o serviço rodando sem os pesos e sem rede — as 10 rotas de
dados responderam normalmente e as 4 de linguagem responderam 503 com o motivo, nas duas
tarefas. A carga é por tarefa, de modo que a falha de um modelo não derruba o outro.**

**4.15 Visibilidade do erro do modelo** — indicador: o limite de cada modelo está demonstrado
na interface, não apenas descrito na documentação. Alvo: sim para os dois. **Situação atual:
no sentimento, dois exemplos prontos mostram o mesmo fato recebendo rótulos diferentes
conforme a moldura; no resumo, o texto gerado aparece ao lado do resumo escrito pela redação,
e a truncagem é dita em proporção — "o modelo viu 44% do texto".**

**4.16 Respaldo do texto gerado** — indicador: % dos resumos entregues com a conferência dos
seus números, datas e nomes próprios contra o texto de origem. Alvo: 100%, sem possibilidade
de desligar. **Situação atual: 100% — a conferência é anexada dentro da função que gera o
resumo, não pela rota, e aparece tanto na resposta da API quanto na tela.** *edited
25-11-2026 (TP5):* vale também para o assistente — toda resposta vem conferida contra os dados
que o modelo recebeu, sem opção de desligar.

**4.17 Ancoramento das respostas do assistente** — indicador: termos da resposta — números,
datas e nomes próprios — sem respaldo nos dados que o modelo recebeu, na bateria de
verificação. Alvo: zero. **Situação atual: zero em 55 termos conferidos nas dez perguntas,
com o assistente como está em produção.** Sem o bloco de dados, o mesmo modelo inventou
regiões, cifras, matérias e empresas — seção 6 de
[`../3_modeling/assistente_llm.md`](../3_modeling/assistente_llm.md).

**4.18 Continuidade da conversa** — indicador: perguntas que dependem da anterior — "a
primeira delas", "comparado com ela", "qual das duas" — respondidas corretamente. Alvo: todas.
**Situação atual: 5 de 5 com memória, 0 de 5 sem ela.** Sem memória o erro não aparece na
conferência: a resposta trata de outra coisa com dados verdadeiros — "ela" virou o Pará, "das
duas" virou Paraíba e Alagoas.

**4.19 Tempo de resposta do assistente** — indicador: segundos por resposta, com o modelo
carregado, na máquina do projeto. Alvo: menos de 30 segundos. **Situação atual: média de 10,4
s e máximo de 24,1 s na verificação, com 68% do modelo na GPU.** A primeira pergunta depois de
o modelo sair da memória soma a carga pelo Ollama, que levou 45 s na primeira medição.

---

## 5. ODS atendida e justificativa

**ODS 4 — Educação de Qualidade.** O projeto atende à ODS 4 de duas formas: direciona
recurso privado para os territórios mais distantes de cumprir suas metas, e torna visível a
distância entre a situação atual e o compromisso do Brasil para 2030.

Metas da ODS 4 endereçadas e o indicador oficial usado em cada uma:

**5.1 Meta 4.1** — concluir o ensino básico com qualidade. Indicador 4.1.2, taxa de conclusão.

**5.2 Meta 4.2** — educação na primeira infância. Indicador 4.2.2, participação no ensino
organizado aos 5 anos.

**5.3 Meta 4.6** — alfabetização de jovens e adultos. Indicador 4.6.1, taxa de alfabetização
das pessoas de 15 anos ou mais.

**5.4 Meta 4.a** — instalações educacionais adequadas e inclusivas. Indicador 4.a.1,
infraestrutura das escolas.

**5.5 Meta 4.c** — professores qualificados. Indicador 4.c.1, docentes com formação adequada.

**5.6 ODS secundárias** — ODS 10, Redução das Desigualdades, por priorizar territórios
historicamente preteridos pelo investimento social; e ODS 17, Parcerias, por qualificar a
relação entre setor privado e poder público na educação.

**5.7 Pilar ESG** — Social, com forte componente de Governança: a rastreabilidade
fonte → número → afirmação é o que torna o reporte auditável.

---

## 6. Público-alvo

**6.1 Usuário primário** — analista ou gerente de Sustentabilidade, ESG ou Investimento
Social Privado em empresa de médio ou grande porte, instituto ou fundação empresarial. Decide
onde alocar o orçamento anual em educação e precisa reportá-lo. Usa planilha e BI, não
programa.

**6.2 Usuários secundários** — institutos, fundações e ONGs de educação, que fundamentam
captação com evidência de carência; comitês de ESG, que avaliam a coerência da alocação; e
gestores públicos de educação, que usam o diagnóstico para atrair parceria privada.

**6.3 Beneficiários finais** — estudantes da educação básica pública em territórios de alta
carência, beneficiários indiretos do redirecionamento do recurso.

---

## 7. Stakeholders

*Stakeholder 7.5 adicionado em setembro — TP2.*

| # | Stakeholder | Papel | Interesse | Como o projeto responde |
| --- | --- | --- | --- | --- |
| 7.1 | Área de Sustentabilidade e ESG | Usuário primário e patrocinador | Decidir e reportar com segurança | Ranking com pesos explícitos e minuta de reporte rastreável |
| 7.2 | Institutos, fundações e ONGs de educação | Usuário secundário e executor | Ser encontrado e financiado | Evidência de carência territorial para fundamentar captação |
| 7.3 | Secretarias estaduais e municipais de educação | Parceiro público | Atrair recurso complementar | Diagnóstico comparável entre territórios |
| 7.4 | IBGE e INEP | Provedores de dados | Reúso qualificado do dado público | Citação de fonte, ano e URL em cada valor exibido |
| 7.5 | Imprensa e terceiro setor | Provedores de contexto | Circulação qualificada da pauta | Link para a matéria original em toda menção |
| 7.6 | Estudantes da rede pública | Beneficiário final | Melhoria das condições de ensino | Redirecionamento do recurso para territórios carentes |

---

## 8. Riscos

*Riscos 8.5 a 8.8 adicionados em setembro — TP2. Riscos 8.9 a 8.11 adicionados em
novembro — TP3. Riscos 8.12 a 8.14 adicionados em novembro — TP4. Riscos 8.15 a 8.17
adicionados em novembro — TP5.*

**8.1 Indisponibilidade ou mudança das APIs públicas** — mitigação: coletar e armazenar os
dados em ambiente local. *edited 21-09-2026:* a aplicação lê exclusivamente os arquivos de
`data/`, nunca a rede; a indisponibilidade de uma API atrasa a atualização, não derruba o
painel.

**8.2 Granularidade municipal indisponível para indicadores-chave** — mitigação: UF
garantido, depois municípios.

**8.3 Índice composto embutir juízo de valor não explicitado** — mitigação: expor os pesos.
*edited 21-09-2026:* os pesos passaram a ser editáveis pelo usuário na interface e são
impressos na seção 1 do reporte ESG gerado.

**8.4 IA generativa produzir afirmação incorreta no reporte** — mitigação: LLM's não
produziram dados, apenas consultas. *edited 16-11-2026:* com as tarefas de LLM previstas para
a etapa seguinte, a mitigação foi detalhada em
[`../3_modeling/plano_llm.md`](../3_modeling/plano_llm.md) e se apoia em quatro regras: o
modelo nunca calcula nem estima — todo valor citado é injetado no prompt a partir do dado já
apurado por `nucleo.py`; toda resposta sobre o corpus cita título, fonte e URL das matérias
que a sustentam, e resposta sem citação não é exibida; todo texto gerado aparece identificado
como tal, com data e modelo, na interface e no reporte; e a geração fica atrás de ação
explícita do usuário, nunca de recarregamento de página.

*edited 16-11-2026 (TP4):* **o risco se materializou e está medido.** A entrega tem duas
tarefas de linguagem. A de sentimento é um classificador e não pode inventar nada. A de
resumo é gerativa, e na verificação produziu uma data, um estado e uma cifra ausentes do
texto de entrada — os dois casos estão transcritos na seção 5.2 de
[`../3_modeling/modelo_llm.md`](../3_modeling/modelo_llm.md). O texto gerado era gramatical e
plausível, que é precisamente o que torna o risco perigoso.

Situação das quatro regras:

- **Valor nunca calculado pelo modelo** — cumprida por construção: nenhum número do projeto
  passa por modelo. Os indicadores e o índice são apurados por `nucleo.py`, e o resumo não
  alimenta nada: não entra no reporte, não é gravado, não é insumo de cálculo.
- **Citação da matéria que sustenta a afirmação** — cumprida: todo resumo gerado a partir do
  corpus aparece com a matéria de origem, e ao lado do resumo escrito pela própria redação.
- **Identificação do que é gerado** — cumprida: o campo `gerativo` vem verdadeiro na resposta,
  o `aviso` declara que o resumo pode afirmar o que não está no original, e a tela exibe os
  dois.
- **Geração atrás de ação explícita** — cumprida: tanto a carga do modelo quanto cada resumo
  ficam atrás de um botão.

Acrescentou-se uma quinta contenção, que não estava prevista nas quatro e que é a única a
não depender de o leitor prestar atenção ao aviso: **toda resposta de resumo traz a
conferência automática dos seus números, datas e nomes próprios contra o texto de origem.**
O que ela aponta como ausente, o modelo produziu por conta própria. Não usa modelo — é
comparação léxica, em `texto.conferir_resumo` — e é anexada dentro da própria função que
gera o resumo, de modo que nenhum consumidor receba um resumo sem ela.

O que **falta**, e fica declarado: a conferência pega termo inventado e não pega relação
invertida entre duas entidades que estejam ambas no texto. Essa camada semântica é a
pendência 9.2 do documento do modelo, e é o que ainda separa o resumo de hoje — ferramenta
de triagem — de um texto que pudesse entrar num reporte.

*edited 25-11-2026 (TP5):* o assistente é a terceira tarefa gerativa, e a primeira que
responde sobre os números do índice — exatamente o terreno do risco. As quatro regras valem
para ele, todas cumpridas por construção: **o modelo não calcula** — ranking, valores,
médias, diferenças, posições e comparações chegam prontos de `nucleo.py`, e o prompt proíbe
calcular, estimar ou projetar; **a matéria é citada** — pelo número entre colchetes, e a
lista das matérias e dos indicadores do contexto acompanha toda resposta, cite o modelo ou
não; **o gerado é identificado** — modelo, instante, aviso e campo `gerativo` em toda
resposta; **a geração fica atrás de ação explícita** — cada resposta é uma pergunta enviada.
A quinta contenção, a conferência automática, também vale: toda resposta é conferida contra
o bloco de dados que o modelo recebeu. A medição em quatro condições está na seção 6 de
[`../3_modeling/assistente_llm.md`](../3_modeling/assistente_llm.md); o erro que a
conferência não pega ficou registrado como risco próprio, o 8.15.

**8.5 Quebra do seletor de raspagem** — os sites de origem podem mudar de HTML.
Mitigação: `scraping.py` isola cada fonte em sua própria função, registra aviso e segue com
as demais; os dados já coletados permanecem em `data/raw/`.

**8.6 Viés de cobertura da imprensa** — a contagem de menções por UF reflete a
atenção editorial, não a carência do território. Mitigação: a menção nunca entra no cálculo
do índice; aparece apenas como camada de contexto, e a aplicação declara isso na própria tela.
*edited 16-11-2026 (TP4):* o rótulo de sentimento está sob a mesma regra e a amplia — além de
não entrar no índice, carrega o aviso em toda resposta da API e na tela. Há um modo de erro
específico a vigiar: `neutro` significa "texto escrito em registro informativo", **não**
"situação estável no território". A seção 4.1 de
[`../3_modeling/modelo_llm.md`](../3_modeling/modelo_llm.md) mostra a mesma notícia de evasão
escolar classificada como `negativo` quando escrita de forma direta e como `neutro` quando
trazida na moldura jornalística; as duas frases estão lado a lado na interface, como exemplos,
para que quem usa a tela veja o limite em vez de ler sobre ele.

**8.7 Site de origem passar a proibir a coleta** — o `robots.txt` pode mudar a
qualquer momento. Mitigação: a permissão é reconsultada a cada execução, não fica em cache
entre execuções; se o caminho passar a ser proibido, o script pula aquele host e registra a
recusa, e os dados já coletados permanecem em `data/raw/`.

**8.8 Dado enviado pelo usuário contaminar o ranking** — mitigação: as linhas
enviadas vivem apenas no estado da sessão, são marcadas com `origem = usuário` e somem ao
fim da sessão. Nenhum upload altera os arquivos do repositório. *edited 16-11-2026:* a rota
`POST /indicadores` segue a mesma regra — as linhas ficam na memória do processo, recebem
`origem = api` e desaparecem quando o serviço reinicia; e qualquer consulta pode pedir
`incluir_enviados=false` para ver só o dado oficial.

**8.9 Índice divergir entre o painel e o serviço HTTP** — dois canais sobre os mesmos
dados abrem a possibilidade de o número publicado no relatório não ser o número exibido na
tela, o que é falha de rastreabilidade, não apenas inconsistência de interface. Mitigação:
não existe segunda implementação do cálculo — `utils.py` e `api.py` chamam a mesma função de
`nucleo.py`, e cada um só acrescenta a sua camada de cache. A verificação está registrada na
seção 5 da Referência da API.

**8.10 Serviço de escrita exposto sem controle** — a rota `POST /indicadores` aceita dado
sem autenticação. Mitigação: o serviço roda em `127.0.0.1` para uso local, a escrita é
volátil e isolada por processo, e o dado recebido fica permanentemente marcado com
`origem = api`. Publicá-lo em rede aberta exigiria autenticação, limite de requisições por
cliente e CORS restrito à origem do painel — registrado como pendência explícita na seção
4.1 da Referência da API, e fora do escopo atual conforme a seção 2.2.

**8.11 Dependência de rede na aplicação** — o painel foi construído para subir sem rede
(seção 10), e tanto o serviço HTTP quanto as chamadas de LLM futuras rompem isso.
Mitigação: a dependência está confinada a uma página. A página *Serviço de API* detecta a
ausência do serviço, informa na tela e instrui como subi-lo; as outras seis seguem lendo os
arquivos de `data/` diretamente. A mesma regra vale para a etapa de LLM: falha de chamada
degrada a funcionalidade de texto e não derruba o painel. *edited 16-11-2026 (TP4):* a regra
foi cumprida e verificada. São agora duas as páginas dependentes do serviço — *Serviço de
API* e *Análise de linguagem* —, ambas com o mesmo aviso de tela, e as outras seis continuam
sem tocar a rede. Do lado do serviço, a verificação foi feita rodando-o com o cache de
modelos vazio e sem acesso à internet: as 10 rotas de dados responderam normalmente e as 4
de linguagem responderam 503 com o motivo. *edited 25-11-2026 (TP5):* o assistente não
reabre o risco: o Ollama é programa local, e a conversa não toca a internet. A página
*Assistente ESG* é a terceira dependente do serviço, com o mesmo aviso de tela, e as outras
seis continuam lendo `data/`.

**8.12 Modelo de linguagem indisponível no ambiente de quem executa** — os pesos somam cerca
de 2 GB nos dois modelos e não entram no repositório; a primeira carga depende de rede, e a
máquina pode não ter memória suficiente. Mitigação: a carga é preguiçosa, por tarefa, e seu
fracasso é contido — nenhuma rota de dados e nenhuma página de análise depende de modelo, e a
falha de um modelo não afeta o outro. A resposta 503 nomeia os modelos do serviço, o motivo
da falha, o que fazer e o que continua funcionando; `GET /modelo` informa, antes de qualquer
tentativa, se os pesos de cada um já estão em disco. O risco é de execução, não de dado: nada
do que o projeto apura depende de modelo.

**8.13 Rótulo de sentimento ser lido como medida do território** — detalhado no risco 8.6.
Fica registrado aqui como risco de **interpretação**, que não produz erro visível: um gestor
que lê `neutro` como "situação estável" toma decisão errada sem que nada no sistema acuse
falha. Mitigação: o aviso acompanha toda resposta da API e aparece na tela; a página traz os
dois exemplos que demonstram o limite; e o rótulo nunca entra no cálculo do índice.

**8.14 Resumo gerado ser lido como apuração** — o risco mais grave desta etapa, porque o
texto gerado é gramatical, plausível e, pela forma, indistinguível de texto apurado. O modelo
inventa quando o texto de entrada é curto demais para sustentar uma frase de abertura:
preenche com o que é estatisticamente provável no gênero — um estado, um número, uma data.
Mitigação, toda implementada: **a conferência automática de cada número, data e nome próprio
do resumo contra o texto de origem**, anexada a toda resposta; o campo `gerativo` e o `aviso`
em toda resposta; o resumo gerado exibido ao lado do resumo da redação; busca em feixe no
lugar da gulosa, que reduziu a invenção ao custo de 2 a 3 segundos por matéria; e o resumo
não alimentando nada — nem reporte, nem `data/`, nem cálculo.

A conferência é a mitigação que importa, porque as demais dependem de o leitor ler o aviso e
ela aponta o dedo no termo. Numa execução de verificação pela interface, com uma entrada de
25 palavras sobre vagas em creche, o modelo produziu "Cochabamba" — cidade boliviana —,
"Estado de Goiás" e "mil", e os quatro termos saíram marcados como ausentes do original. O
que ela ainda não pega é relação invertida entre entidades presentes no texto: pendência 9.2
em [`../3_modeling/modelo_llm.md`](../3_modeling/modelo_llm.md).

**8.15 Assistente pôr um número verdadeiro no lugar errado** — o risco de maior
consequência do TP5, porque passa por toda conferência de número. No desenvolvimento, o
modelo disse que o Acre era o 3º pior em internet, sendo o 2º; atribuiu a Pernambuco a
contagem de indicadores da Bahia; e concluiu que a Bahia tinha a pior alfabetização com
90,5% contra 89,9% de Pernambuco. Os números estavam todos nos dados; a relação estava
errada. Mitigação implementada: **o que exigiria contar, comparar ou ordenar chega pronto no
contexto** — posição em cada indicador, "pior situação" e "melhor situação" por extenso,
comparação direta entre as UFs em foco, nome da UF repetido em cada frase do seu bloco —, e
os três casos passaram a ser respondidos certo. O risco residual fica declarado: em pergunta
que o contexto não antecipa, o erro de relação continua possível. Por isso cada resposta
aparece com o gráfico dos dados por trás dela e com o bloco que o modelo leu, para
conferência humana em segundos.

**8.16 Memória carregar o foco errado** — a memória de foco decide que dados entram no
prompt, e uma UF que entrou de passagem pode ocupar o lugar de outra. Mitigação: o que a
pergunta cita vem sempre antes do que a memória guarda; o foco é limitado a três UFs; região,
tema e indicador só entram pela pergunta do usuário, nunca pela resposta do modelo; e as
quatro listas da memória ficam à vista na barra lateral, com o botão que as apaga. A memória
não é resumo gerado por modelo, de propósito: um resumo carregaria uma invenção para todos os
prompts seguintes.

**8.17 Assistente indisponível no ambiente de quem executa** — depende do Ollama instalado,
do modelo baixado (4,9 GB) e, para responder em segundos, de GPU. Mitigação: a falha é
contida como a dos modelos do TP4 — a rota responde 503 com o motivo e a instrução
(`ollama pull llama3.1:8b`), `GET /modelo` diz antes de qualquer pergunta se o modelo está no
Ollama, e as rotas de dados e as outras páginas não dependem dele. Sem GPU o Ollama roda em
CPU, mais devagar.

---

## 9. Ética

O projeto opera apenas sobre agregados públicos oficiais. Não há tratamento de dados
pessoais, portanto nenhuma operação sujeita à LGPD. O índice deve ser lido como medida de
**prioridade de investimento**, nunca como ranking de mérito de um território.

*edited 21-09-2026* — a extração de conteúdo web coleta apenas material jornalístico
publicado em acesso aberto. Nenhuma página é baixada antes da consulta ao `robots.txt` do
host: o script se identifica como `bussola-esg-educacao`, só busca URLs permitidas a esse
agente e respeita o `Crawl-delay` declarado por cada site — 10 segundos no caso da Agência
Brasil. Se o `robots.txt` estiver inacessível ou negar acesso, a coleta daquele host é
suspensa; a postura padrão é não raspar. A conferência fica registrada em
`data/processed/robots_verificacao.csv` e visível na própria aplicação. Toda matéria é
exibida com a fonte e o link para o original; a aplicação não republica o texto integral
como conteúdo próprio, usa-o como corpus de análise linguística.

*edited 16-11-2026* — o serviço HTTP não altera a postura ética do projeto: expõe os mesmos
agregados públicos e o mesmo material jornalístico de acesso aberto, com a mesma citação de
fonte e URL em cada registro devolvido. A rota que entrega o corpo das matérias
(`com_texto=true`) acompanha sempre a fonte e o link do original, de modo que nenhum
consumidor receba o texto desacompanhado de sua procedência. Sobre o conteúdo gerado por
modelo de linguagem na etapa seguinte, a regra está fixada no risco 8.4: identificação
explícita do que é gerado, citação obrigatória da matéria que sustenta a afirmação, e
nenhuma geração de número — o modelo descreve o dado apurado, não o produz.

*edited 16-11-2026 (TP4)* — o processamento de linguagem acrescenta dois compromissos, ambos
cumpridos nesta entrega. O primeiro é de **soberania do dado**: o modelo roda na própria
máquina, e nenhum trecho das matérias, nem nenhum texto que o usuário digite na interface, é
enviado a serviço de terceiro. O que sai da máquina é o download dos pesos, uma vez. O
segundo é de **identificação**: toda resposta das rotas de linguagem carrega o modelo que a
produziu, o instante da análise, o campo `gerativo` e o aviso de que é resultado automático
não revisado por pessoa, e a interface exibe os quatro. Vale aqui a mesma distinção que a
seção 9 já fazia para a raspagem: o corpus é insumo de análise, não conteúdo republicado — e
o rótulo atribuído a uma matéria é leitura do projeto sobre o texto, nunca afirmação
atribuída ao veículo que a publicou.

O resumo gerado leva essa última ressalva mais longe, e é obrigação ética dizê-lo: **um
resumo automático de matéria alheia, exibido sem marca, seria atribuir ao veículo frases que
ele não escreveu** — e, como a verificação mostrou, às vezes fatos que ele não publicou. Por
isso o resumo nunca aparece sozinho na interface: vem rotulado como gerado, com o modelo e o
instante, e, quando a matéria vem do corpus, ao lado do resumo que a própria redação
publicou. O leitor vê as duas versões e sabe qual é de quem.

*edited 25-11-2026 (TP5)* — o assistente mantém os dois compromissos e acrescenta um. A
**soberania do dado** continua: o modelo roda no Ollama desta máquina, e nem a pergunta do
usuário nem os dados do projeto são enviados a terceiro. A **identificação** continua: toda
resposta traz o modelo, o instante, o aviso de que é texto gerado não revisado e a
conferência do que escreveu. O compromisso novo é de **procedência que acompanha o texto**:
quando o usuário baixa a conversa, cada resposta sai com a conferência e com as matérias que
estavam no contexto, de modo que o texto gerado não circule separado da sua origem. Vale para
a conversa a mesma ressalva do rótulo e do resumo: o que o assistente diz sobre uma matéria é
leitura do projeto, citada pelo número e com o link para o original, nunca frase atribuída ao
veículo.

---

## 10. Arquitetura da solução

*Adicionado em setembro — TP2.* *edited 16-11-2026: entraram as camadas de núcleo e de
serviço HTTP; a interface passou a sete páginas.* *edited 16-11-2026 (TP4): entrou a camada
de modelo e a oitava página.* *edited 25-11-2026 (TP5): entraram o assistente, o Ollama e a
nona página.*

| Camada | Componente | Responsabilidade |
| --- | --- | --- |
| Coleta | `coleta.py` | APIs do IBGE: indicadores da ODS 4 e malha territorial |
| Coleta | `scraping.py` | Beautiful Soup sobre 4 fontes de conteúdo em educação |
| Texto | `texto.py` | Stopwords, tokenização, menções de UF, temas e conferência de resumo |
| Dados | `data/raw`, `data/processed` | Camada bruta e camada tratada, ambas versionadas |
| Núcleo | `nucleo.py` | Leitura dos arquivos e cálculo do índice, em pandas puro |
| Modelo | `modelo_llm.py` | Carga e uso dos três modelos de linguagem locais, sem framework web |
| Modelo | Ollama, `llama3.1:8b` | Programa local que serve o modelo da conversa, na GPU quando há |
| Assistente | `assistente.py` | Memória de foco, contexto de dados e prompt da conversa, sem framework web |
| Serviço | `utils.py` | Cache do Streamlit, estado de sessão, chamada à API e reporte ESG |
| Serviço | `api.py` | Serviço HTTP em FastAPI: 15 rotas sobre o mesmo núcleo |
| Interface | `app.py` + `paginas/` | Nove páginas de navegação, filtros, conversa e downloads |

A coleta roda fora da aplicação, por decisão de projeto: o painel não depende de rede,
sobe em segundos e pode ser publicado sem credenciais.

*edited 16-11-2026* — `nucleo.py` foi extraído de `utils.py` quando a API passou a ser um
segundo consumidor dos mesmos dados. É a peça que garante a meta 4.11 e mitiga o risco 8.9:

```
data/  →  nucleo.py  →  utils.py  →  app.py + paginas/     (painel Streamlit)
                    ↘  api.py                              (serviço HTTP FastAPI)
                       ↑
            modelo_llm.py                                  (modelos de linguagem locais)
```

*edited 16-11-2026 (TP4)* — `modelo_llm.py` segue a mesma regra de `nucleo.py`: não importa
`fastapi` nem `streamlit`, porque os modelos são recurso do projeto e não do servidor web. A
seta aponta só para `api.py` de propósito. Cada modelo é carregado **uma vez por execução do
serviço**, e a página *Análise de linguagem* os consome por HTTP em vez de carregá-los: o
Streamlit reexecuta o script inteiro a cada interação do usuário, e modelos de centenas de
milhões de parâmetros não podem ser carregados nesse ritmo. Dentro do arquivo há um registro
por tarefa, e cada uma carrega, falha e é relatada em separado.

O painel e o serviço são processos independentes, e o painel não depende do serviço. A
Referência da API, em [`../4_deployment/api_reference.md`](../4_deployment/api_reference.md),
documenta as rotas, os parâmetros e os limites de cada uma.

*edited 25-11-2026 (TP5)* — o assistente acrescenta uma peça ao lado do modelo, com a mesma
regra de não importar framework web:

```
paginas/assistente.py  ──POST /assistente──►  api.py  →  assistente.py  →  nucleo.py
     (memória na sessão)                                     │    (dados prontos)
                                                             ▼
                                              modelo_llm.py  →  Ollama (llama3.1:8b)
                                                             │
                                                             ▼
                                              texto.py  (conferência contra os dados)
```

O serviço não guarda a conversa: a memória vem na requisição e volta atualizada na resposta.
O ranking que o assistente cita é calculado pela mesma função `nucleo.calcular_indice`, com
os pesos que a página envia — a meta 4.11 vale também para a conversa.

---

## 11. Marcos

*Adicionado em setembro — TP2.* *edited 16-11-2026: acrescentados os marcos do TP3 e, em
seguida, os do TP4.* *edited 25-11-2026 (TP5): acrescentados os marcos da solução final.*

| Marco | Estágio TDSP | Situação |
| --- | --- | --- |
| Project Charter e definição do problema | Business Understanding | Concluído |
| Coleta via API e Data Summary Report | Data Acquisition | Concluído |
| Extração de conteúdo web e corpus textual | Data Acquisition | Concluído |
| Índice de prioridade e interface interativa | Modeling | Concluído |
| Núcleo de dados sem dependência de interface | Modeling | Concluído |
| Serviço HTTP em FastAPI e sua referência | Deployment | Concluído |
| Especificação das tarefas de LLM | Modeling | Concluído |
| Seleção dos modelos de linguagem, com candidatos medidos | Modeling | Concluído |
| Integração dos modelos locais ao serviço FastAPI | Deployment | Concluído |
| Contrato de resposta declarado em todas as rotas | Deployment | Concluído |
| Tratamento de erro e degradação contida, verificados | Deployment | Concluído |
| Interface de análise de linguagem | Deployment | Concluído |
| Resumo automático do corpus, uma matéria por vez | Modeling | Concluído |
| Conferência do texto gerado contra a fonte | Modeling | Concluído |
| Assistente com memória sobre os dados, por modelo local | Modeling | Concluído |
| Engenharia de prompt medida em quatro condições | Modeling | Concluído |
| Rota `POST /assistente` e página *Assistente ESG* | Deployment | Concluído |
| Ciclo do dado ao insight na página inicial | Deployment | Concluído |
| Relatório final do projeto | Customer Acceptance | Concluído |
| Camada semântica da conferência | Modeling | Previsto — pendência 9.2 |
| Narrativa do reporte ESG a partir do ranking | Modeling | Parcial — o assistente redige com números conferidos; falta o fluxo de revisão humana antes da minuta |
| Validação com usuário de Sustentabilidade | Customer Acceptance | Previsto — roteiro na seção 8 do relatório final |
