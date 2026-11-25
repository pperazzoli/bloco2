# Relatório final — Bússola ESG Educação

**Estágio TDSP:** 5. Customer Acceptance · **Data:** 2026-11-25

Documento de encerramento do projeto — o *exit report* do TDSP. Apresenta a solução final,
argumenta como ela resolve o problema de negócio, mostra o que cada etapa do ciclo de ciência
de dados acrescentou, os insights que os dados produziram e o papel dos modelos de IA em
transformá-los em conhecimento. A seção 7 é o roteiro da apresentação.

> **Em uma frase.** A Bússola ESG Educação transforma 189 indicadores oficiais da ODS 4 e 105
> matérias de imprensa num ranking de prioridade de investimento por UF, com a fonte de cada
> número, e deixa o analista conversar com esses dados em português — por um modelo de
> linguagem que roda na própria máquina, não calcula nada e tem cada resposta conferida.

---

## 1. O problema de negócio

Empresas com agenda ESG investem em educação básica, mas decidem **onde** aplicar o recurso
por relacionamento, e não por evidência. O dado público existe — o IBGE publica os
indicadores oficiais da ODS 4 por UF —, mas está disperso em APIs e tabelas que quem decide
não consulta. No reporte de sustentabilidade, o impacto aparece descrito de forma
qualitativa, sem rastreabilidade até a fonte, o que expõe a empresa a risco de *social
washing*.

O usuário é o analista de Sustentabilidade ou de Investimento Social Privado: decide a
alocação do orçamento anual em educação e precisa reportá-la. Usa planilha e BI, não
programa. A solução tinha de responder a quatro perguntas dele, nesta ordem: **onde a
carência é maior, por quê, o que se sabe sobre esses territórios e como reportar a escolha
com a fonte de cada número.**

## 2. A solução, pergunta por pergunta

| Pergunta do analista | Onde a solução responde | Etapa do ciclo |
| --- | --- | --- |
| Onde a carência é maior? | Página *Índice de prioridade*: ranking das 27 UFs com pesos ajustáveis | Modelagem |
| Por quê? | Páginas *Indicadores da ODS 4* e *Assistente ESG*: os indicadores em que a UF está abaixo da média | Dados + IA |
| O que a imprensa diz? | Páginas *Notícias* e *Análise de linguagem*: nuvem, tom e resumo conferido | Coleta + IA |
| Posso perguntar do meu jeito? | Página *Assistente ESG*: conversa com memória sobre os dados | IA |
| Como reporto? | Minuta do reporte ESG em Markdown, com pesos, UFs e fontes | Implantação |
| Posso levar para o meu BI? | Serviço HTTP com 15 rotas documentadas | Implantação |

---

## 3. O ciclo de ciência de dados, etapa por etapa

Cada etapa abaixo traz o que foi feito e **o que daria errado sem ela** — que é a medida da sua
importância.

### 3.1 Entendimento do negócio

O Project Charter fixou, antes de qualquer código, três regras que decidiram todo o resto: o
índice mede **prioridade de investimento, nunca mérito** do território; os **pesos são
explícitos** e do usuário (risco 8.3); e **todo número tem fonte, ano e URL** (meta 4.3). Sem
essas regras, o projeto seria mais um painel de indicadores; com elas, é um instrumento de
decisão auditável.

### 3.2 Coleta

- **API do IBGE** (`coleta.py`): 7 indicadores de monitoramento da ODS 4, nas 27 UFs, anos de
  2024 e 2025 — 189 observações, zero nulos —, mais a malha territorial e o domínio de UFs e
  regiões. Cada linha guarda a URL da consulta que a produziu.
- **Raspagem com Beautiful Soup** (`scraping.py`): 105 matérias de 4 fontes — Agência
  Brasil, Todos Pela Educação, GIFE e Observatório do Terceiro Setor —, com o `robots.txt`
  de cada site conferido antes de qualquer download e o intervalo que cada um pede respeitado.

*Sem ela:* o reporte voltaria a ser qualitativo. A escolha de coletar dado **oficial** é o que
torna cada número do reporte verificável por terceiro. E uma decisão de coleta tomada por
outro motivo — ler os feeds em vez das páginas dinâmicas — trouxe de graça o resumo escrito
pela redação, que no TP4 virou a referência humana para avaliar o modelo de resumo.

### 3.3 Limpeza e preparação

Os detalhes pequenos foram os que mais pesaram. Sem acento, "Pará" vira a preposição "para", e
o estado aparecia em 104 das 105 matérias — os nomes passaram a ser comparados acentuados. A
malha do IBGE vem com os polígonos num sentido que o Plotly lê como "o mundo inteiro menos o
estado", e o mapa saía como um retângulo verde — o sentido é invertido na coleta. As datas
chegam em dois formatos e são normalizadas; o HTML é removido com regra declarada. No TP5,
montar o contexto do assistente revelou mais um: o rodapé do feed do WordPress dentro do
resumo das matérias (seção 8.3 do Data Summary Report).

*Sem ela:* cada um desses detalhes produziria um número errado com aparência de certo — o
tipo de erro que um reporte ESG não pode ter.

### 3.4 Modelagem

O **Índice de Prioridade de Investimento** é composição determinística dos sete indicadores:
cada um normalizado (min-max entre UFs ou distância de 100%), ponderado pelos pesos do usuário
e combinado numa nota de 0 a 100, em que maior é mais carência. Não há modelo preditivo, por
decisão (escopo 2.2): o índice descreve o que foi observado.

*Sem ela:* o analista teria sete rankings que discordam entre si e nenhuma forma explícita de
combiná-los. O índice faz a combinação **à vista**, com o peso de cada indicador na tela e no
reporte.

### 3.5 IA: três modelos, cada um para uma pergunta

| Modelo | Tarefa | O que acrescenta | Contenção |
| --- | --- | --- | --- |
| `cardiffnlp/twitter-xlm-roberta-base-sentiment` (TP4) | tom das matérias | direção ao volume de menções: "aparece em 12, das quais 2 em tom negativo" | nunca entra no índice; `neutro` não é "situação estável" |
| `recogna-nlp/ptt5-base-summ-xlsum` (TP4) | resumo de uma matéria | decidir se vale ler a matéria inteira | conferência de números, datas e nomes contra a matéria |
| `llama3.1:8b` via Ollama (TP5) | conversa com memória | perguntar aos dados em português, com memória | o modelo não calcula; resposta conferida contra os dados |

Os três rodam **na própria máquina**: nenhum texto do corpus e nenhuma pergunta do usuário
são enviados a serviço externo. Os dois primeiros foram escolhidos entre quatro candidatos
medidos sobre o corpus (`3_modeling/modelo_llm.md`); o terceiro, e a forma de usá-lo, estão em
`3_modeling/assistente_llm.md`.

*Sem ela:* o painel mostraria os dados, mas o analista teria de saber onde clicar para cada
pergunta. A IA é a camada que **dá acesso** ao dado — e o projeto inteiro cuida para que ela
não seja a camada que **produz** o dado.

### 3.6 Implantação

- **Painel Streamlit** com nove páginas em três grupos, cache e estado de sessão, upload e
  download de CSV, e a visão do ciclo completo na página inicial.
- **Serviço FastAPI** com 15 rotas, contrato declarado em todas (`response_model`) e
  documentação interativa gerada a partir do código.
- **Um núcleo de cálculo só** (`nucleo.py`), chamado pelo painel, pelo serviço e pelo
  assistente: o índice que a tela mostra, o que a API devolve e o que o assistente cita são,
  por construção, o mesmo número (meta 4.11).
- **Degradação contida**: sem os modelos, sem o Ollama ou sem a API, só a funcionalidade que
  depende deles para, com aviso na tela; as rotas de dados e as outras páginas seguem.

### 3.7 Aceite

Este relatório, a situação das metas na seção 9 e o roteiro de validação com usuário na seção
8, que é o passo que falta.

---

## 4. Os insights que os dados produziram

Todos calculados por `nucleo.py`, sem modelo, e verificáveis no painel. São também o que o
assistente encontra e explica quando perguntado.

| Insight | Evidência | O que sugere a quem investe |
| --- | --- | --- |
| A carência se concentra no Norte e no Nordeste | as 10 UFs de maior prioridade são 5 de cada região; índice médio de 48,6 no Norte e 40,1 no Nordeste, contra 18,4 a 20,3 nas outras | a alocação por evidência desloca o recurso para onde o relacionamento raramente chega |
| O topo não depende de escolha técnica | os dois métodos de normalização dão o mesmo conjunto de 10 UFs prioritárias | a decisão é robusta; o analista não precisa dominar a normalização para confiar nela |
| A maior desigualdade é de infraestrutura escolar | internet para fins pedagógicos vai de 17,8% no Pará a 90,8% no Espírito Santo, 73 pontos; computador, 67; alfabetização, 11,6 | a meta 4.a é onde o investimento privado age mais direto: conectividade e equipamento |
| O Acre está abaixo da média nos sete indicadores | maiores distâncias em internet (22,9% contra 62,6%), computador (46,8% contra 86,4%) e acessibilidade (51,5% contra 84,7%) | prioridade 1, com o problema localizado na infraestrutura |
| O índice composto esconde lacunas pontuais | Santa Catarina, 16ª no índice, empata com Roraima no pior valor do país em docentes com formação adequada, 75,4% | programas de formação docente têm um mapa próprio, que o ranking geral não mostra |
| A imprensa olha pouco para onde a carência é maior | o Acre, 1º no índice, aparece em uma das 105 matérias; só 4 matérias citam alguma das 5 UFs prioritárias | os territórios mais carentes são os menos disputados — e os de menor visibilidade para o reporte |
| O tom da cobertura é institucional | 25 de 30 matérias classificadas como neutras pelo modelo de sentimento (TP4) | o corpus informa a pauta, não mede a situação; o projeto o trata assim |
| O período coletado não cobre creche | nenhuma das 105 matérias menciona creche; o assistente disse isso em vez de inventar | lacuna de pauta do período — e um teste de honestidade do assistente que ele passou |

---

## 5. Como a IA transforma dado em conhecimento

### 5.1 O princípio: o modelo lê, não sabe

A primeira medição do TP5 decidiu a arquitetura. Perguntado, sem dado nenhum, o que mede a
taxa de alfabetização, o modelo respondeu que ela "é medida pelo IDH e pelo IDE" — falso, e
dito com segurança. Com o ranking do projeto no prompt, devolveu as cinco UFs prioritárias com
os cinco índices exatos. Daí a regra que organiza o assistente: **todo número chega pronto no
prompt, apurado por `nucleo.py`**, inclusive média, diferença, posição e comparação; o modelo
lê e redige.

### 5.2 A memória: a conversa como o analista a faria

"Quais são as prioritárias?" → "por que a primeira?" → "e como ela está em internet?" → "e
comparada com a Bahia?". O assistente guarda as últimas seis mensagens, para entender as
referências, e o **foco** da conversa — UFs, regiões, temas e indicadores citados —, que decide
que dados entram na resposta seguinte. A memória fica à vista na barra lateral e pode ser
apagada.

### 5.3 A engenharia de prompt: governança aplicada ao texto

Cada regra do prompt traduz uma regra do Charter — não produzir número, não prever, não
recomendar investimento financeiro, não ler índice como mérito, citar a matéria. E a forma dos
dados no prompt foi ajustada falha a falha: seis respostas erradas no desenvolvimento viraram
seis mudanças. Três delas tinham todos os números certos e a relação errada — o modelo contou
mal uma posição, atribuiu a uma UF a contagem de outra, inverteu uma comparação —, e foram
corrigidas entregando pronta a posição, a comparação e as palavras "pior situação" e "melhor
situação".

### 5.4 A medição: cada peça isolada

A mesma bateria de dez perguntas, em quatro conversas, passou por quatro condições
(`avaliar_assistente.py`):

| Condição | Respostas certas | Perguntas que dependem da memória | Termos sem respaldo nos dados |
| --- | --- | --- | --- |
| **Assistente final** — dados, regras e memória | **10 de 10** | **5 de 5** | **0 de 55** |
| Sem memória | 5 de 10 | 0 de 5 | 0 de 40 |
| Sem as regras do prompt | 6 de 10 | 3 de 5 | 9 de 85 |
| Sem os dados | 1 de 10 | 0 de 5 | 47 de 106 |

Sem os dados, o modelo pôs o Sudeste e o Sul como regiões prioritárias, inventou IDEB, IDH e
taxas de alfabetização — invertendo a conclusão sobre a Bahia e Pernambuco — e descreveu
notícias sobre creche que não existem no corpus. Sem as regras, acertou os números mas sugeriu
fundos e empresas como investimento e chamou o Pará de estado do Nordeste. Sem memória, errou
as cinco perguntas que dependem da anterior — com zero termos sem respaldo, porque respondeu a
outra pergunta com dados verdadeiros. **Cada peça tem uma função medida**, e a revisão manual
das respostas confirma a checagem automática: o assistente final teve nove respostas certas e
uma parcial, sem nenhuma errada. A análise completa está na seção 6 de
`3_modeling/assistente_llm.md`.

### 5.5 O que a IA não faz neste projeto

- **Não calcula o índice nem nenhum número** — todo valor vem de `nucleo.py`.
- **Não entra no reporte sozinha** — o parágrafo que o assistente redige é texto gerado,
  marcado como tal, e passa por quem assina o reporte.
- **Não sai da máquina** — os três modelos são locais.
- **Não persiste** — classificação, resumo e conversa vivem na sessão e no arquivo que o
  usuário baixar, sempre com a procedência ao lado.

---

## 6. Alinhamento com a ODS 4 e com o ESG

**ODS 4 — Educação de Qualidade.** Os indicadores do índice são os oficiais de monitoramento
da ODS 4, publicados pelo IBGE como custodiante nacional da Agenda 2030:

| Meta | Indicador usado |
| --- | --- |
| 4.1 — concluir o ensino básico com qualidade | 4.1.2, taxa de conclusão do ensino médio |
| 4.2 — educação na primeira infância | 4.2.2, participação no ensino organizado aos 5 anos |
| 4.6 — alfabetização de jovens e adultos | 4.6.1, taxa de alfabetização de 15 anos ou mais |
| 4.a — instalações adequadas e inclusivas | 4.a.1, internet, computador e infraestrutura acessível |
| 4.c — professores qualificados | 4.c.1, docentes com formação adequada |

**ODS 10 e 17.** Redução das desigualdades, ao direcionar recurso para os territórios
historicamente preteridos; parcerias, ao qualificar a relação entre o investidor privado, as
organizações executoras e o poder público.

**ESG.** O pilar é o **Social**, e o diferencial é de **Governança**: a cadeia fonte → número →
afirmação é verificável em cada elo. Cada indicador traz a URL da consulta ao IBGE; cada
resposta do assistente traz a conferência do que escreveu e a lista das fontes que recebeu; o
reporte imprime os pesos que o analista escolheu. É o oposto do *social washing* — que é,
precisamente, afirmação de impacto sem rastro até o dado.

---

## 7. Simplicidade de uso: o roteiro da demonstração

Cinco passos, cerca de dez minutos, na ordem em que o analista usaria:

1. **Visão geral.** A seção *Do dado ao insight* mostra o ciclo inteiro em uma linha — coleta,
   contexto, modelagem, IA e decisão —, com os números calculados na hora e um atalho para cada
   página.
2. **Índice de prioridade.** Mover um peso na barra lateral e ver o ranking se reordenar;
   levar o top 5 para a cesta com um clique.
3. **Assistente ESG.** Clicar em "Quais são as cinco UFs com maior prioridade de
   investimento?" e, em seguida, escrever "Por que a primeira delas está no topo?" e "E como ela
   está em internet nas escolas?". Mostrar a memória na barra lateral, o ✅ da conferência e,
   no expansor de cada resposta, o gráfico, as fontes e o bloco que o modelo leu. Pedir "Qual
   será o índice do Acre em 2030?" e ver a recusa.
4. **Notícias e Análise de linguagem.** O tom da cobertura por UF ao lado do índice e o resumo
   de uma matéria ao lado do resumo da redação, com a conferência.
5. **Reporte.** Baixar a minuta do reporte ESG, com os pesos, as UFs da cesta e as fontes; e
   baixar a conversa com o assistente, que sai com a conferência e as matérias de cada
   resposta.

**Para rodar**, na raiz do projeto, com o ambiente virtual ativo e o Ollama instalado:

```bash
pip install -r requirements.txt
ollama pull llama3.1:8b
uvicorn api:app
streamlit run app.py
```

O painel sobe sem a API e sem o Ollama: só as páginas *Serviço de API*, *Análise de linguagem*
e *Assistente ESG* dependem deles, e avisam na tela quando estão fora do ar.

---

## 8. Validação com o usuário: o passo que falta

A aceitação formal pelo usuário de Sustentabilidade não foi feita nesta entrega. O roteiro
abaixo é o protocolo para fazê-la, e fecha as duas metas que só um usuário real pode medir.

| Item | Como |
| --- | --- |
| Participantes | dois a três analistas de Sustentabilidade ou Investimento Social Privado, e um especialista em educação básica |
| Tarefa 1 | produzir o diagnóstico comparado de três UFs, sem ajuda — cronometrado contra a **meta 4.5**, menos de 5 minutos |
| Tarefa 2 | o especialista monta o seu top 10 sem ver o painel; compara-se com o do índice — **meta 4.7**, sobreposição de ao menos 70% |
| Tarefa 3 | cada analista faz cinco perguntas próprias ao assistente; para cada resposta, marca certa, parcial ou errada, e se confiaria nela para o reporte |
| Critério de aceite | metas 4.5 e 4.7 atingidas; ao menos 4 de 5 respostas do assistente julgadas certas; nenhuma resposta errada sem algum sinal na tela — conferência, gráfico ou fontes — que permitisse percebê-la |

O último critério é o que mais importa: o projeto não promete um assistente que nunca erra;
promete que o erro seja **perceptível** antes de chegar ao reporte.

---

## 9. Situação das metas do Project Charter

| Meta | Alvo | Situação |
| --- | --- | --- |
| 4.1 Cobertura territorial | 27 UFs com índice | **atingida** — 27 de 27 |
| 4.2 Profundidade do dado | ao menos 6 indicadores oficiais | **atingida** — 7 |
| 4.3 Rastreabilidade | 100% dos valores com fonte, ano e URL | **atingida** — 189 de 189 observações com `fonte_url` |
| 4.4 Atualidade | defasagem de até 2 anos | **atingida** — dados de 2024 e 2025 |
| 4.5 Esforço do usuário | diagnóstico comparado em menos de 5 minutos | **a medir com usuário** (seção 8); a conversa de três perguntas do teste levou menos de um minuto |
| 4.6 Reporte ESG | minuta em menos de 1 minuto | **atingida** — download imediato na página do índice |
| 4.7 Qualidade do ranking | top 10 com 70% de sobreposição ao do especialista | **a medir com especialista** (seção 8) |
| 4.8 Cobertura da imprensa | ao menos 3 fontes | **atingida** — 4 fontes, 105 matérias |
| 4.9 Resposta da interface | menos de 1 s com cache | sem medição formal; leituras e cálculos em cache desde o TP2 |
| 4.10 Cobertura do serviço | ao menos 2 rotas | **atingida** — 15 rotas |
| 4.11 Paridade entre canais | diferença zero | **atingida** — 27 de 27 UFs idênticas entre painel e API; o assistente usa a mesma função |
| 4.12 Custo da linguagem | caber numa interação | **atingida** — 0,08 s por classificação, ~3 s por resumo, de 2 a 25 s por resposta do assistente |
| 4.13 Contrato declarado | 100% das rotas | **atingida** — 15 de 15 |
| 4.14 Degradação contida | só para o que depende do modelo | **atingida** — verificado sem os pesos (TP4) e sem o Ollama (TP5) |
| 4.15 Erro do modelo visível | demonstrado na tela | **atingida** — exemplos do sentimento, resumo ao lado da redação, conferência e bloco lido no assistente |
| 4.16 Respaldo do texto gerado | 100% conferido | **atingida** — resumo e resposta do assistente, sem opção de desligar |
| 4.17 Ancoramento do assistente | zero termos sem respaldo | **atingida** — 0 de 55 na verificação |
| 4.18 Continuidade da conversa | todas as perguntas dependentes | **atingida** — 5 de 5 com memória, contra 0 de 5 sem |
| 4.19 Tempo de resposta do assistente | menos de 30 s | **atingida** — média de 10,4 s, máximo de 24,1 s |

Dezesseis das dezenove metas estão atingidas e medidas. Duas — esforço do usuário e qualidade
do ranking contra um especialista — só se medem com pessoas, e são o objeto do roteiro da
seção 8. A 4.9 nunca foi cronometrada, e fica declarada assim.

---

## 10. Limites e próximos passos

- **A conferência é léxica.** Pega número ou nome fora dos dados, não número verdadeiro posto
  no lugar errado (risco 8.15). Próximo passo: verificação de relação para as afirmações mais
  comuns — posição, comparação e "acima/abaixo da média" —, conferidas contra a tabela.
- **Nível municipal.** Os indicadores do IBGE param na UF. Os microdados do INEP, previstos
  desde o TP1, levariam o índice ao município, que é onde o investimento acontece.
- **Série histórica.** O corpus cobre sete semanas e os indicadores, um ano cada. Reexecutar a
  coleta periodicamente — `scraping.py` já reaproveita o que coletou — permitiria falar de
  tendência, o que hoje o projeto se recusa a fazer.
- **Narrativa no reporte.** O assistente já redige o parágrafo com os números conferidos; falta
  o fluxo de revisão humana registrada antes de o texto entrar na minuta.
- **Publicação.** O serviço roda em `127.0.0.1`. Abri-lo exigiria autenticação, limite de
  requisições e CORS restrito (seção 4.1 da Referência da API).
