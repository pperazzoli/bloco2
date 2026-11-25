# Bússola ESG Educação

Aplicação Streamlit que ranqueia territórios brasileiros por prioridade de investimento
social privado em educação básica, a partir dos indicadores oficiais de monitoramento da
ODS 4, e gera a minuta do reporte ESG com a fonte de cada número registrada.

Projeto organizado segundo o **TDSP** (Team Data Science Process).

---

## Como rodar

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Coleta dos dados (roda separado da aplicação, precisa de internet):

```bash
python coleta.py
python scraping.py
```

Sobe a aplicação:

```bash
streamlit run app.py
```

Sobe o serviço de API (segundo terminal, opcional):

```bash
uvicorn api:app --reload
```

Os arquivos de dados já estão versionados em `data/`, então a aplicação sobe sem rodar a
coleta. Os dois scripts só precisam ser reexecutados para atualizar a base. A API também é
opcional: só as páginas *Serviço de API* e *Análise de linguagem* dependem dela, e avisam na
tela quando está fora do ar.

**Modelos de linguagem (TP4).** `transformers`, `torch` e `sentencepiece` já estão no
`requirements.txt`; o `torch` é a build de CPU, não há dependência de GPU. São **dois
modelos, um por tarefa**, carregados em separado e sob demanda:

| Tarefa | Modelo | Pesos | Por item, em CPU |
| --- | --- | --- | --- |
| `sentimento` | `cardiffnlp/twitter-xlm-roberta-base-sentiment` | 1,1 GB | 0,08 s |
| `resumo` | `recogna-nlp/ptt5-base-summ-xlsum` | 892 MB | ~3 s |

O serviço sobe sem modelo carregado — a carga é preguiçosa, e quem usa só uma tarefa nunca
paga o custo da outra. Na primeira vez os pesos são baixados do HuggingFace Hub para
`~/.cache/huggingface/hub` e isso exige rede; depois disso rodam offline. Se um modelo não
puder ser carregado, as rotas que dependem dele respondem 503 com o motivo e todas as demais
continuam atendendo.

Se o `torch` da build de CPU não vier por padrão na sua plataforma:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

**Assistente com memória (TP5).** O terceiro modelo não vem do `requirements.txt`: é o
`llama3.1:8b`, servido pelo **Ollama** (https://ollama.com), programa à parte que já estava
instalado nesta máquina. Uma vez:

```bash
ollama pull llama3.1:8b
```

Depois disso basta o Ollama estar aberto. O serviço fala com ele em `127.0.0.1:11434`, por
HTTP, com o `requests` que já era dependência — nenhuma biblioteca nova. Sem o Ollama, só
`POST /assistente` e a página *Assistente ESG* param, com aviso; o resto não muda.

Para reproduzir a verificação do assistente (cerca de 15 minutos, precisa só do Ollama):

```bash
python avaliar_assistente.py --detalhe
```

---

## Estrutura

```
tp1/
├── 1_business_understanding/  project_charter.md
├── 2_data_acquisition/        data_summary_report.md
├── 3_modeling/                plano_llm.md, modelo_llm.md, assistente_llm.md
├── 4_deployment/              api_reference.md
├── 5_customer_acceptance/     relatorio_final.md
├── data/
│   ├── raw/                   noticias_educacao.csv, noticias_corpus.txt, malha_uf.geojson
│   └── processed/             ods4_uf.csv, fontes.csv, noticias_termos.csv,
│                              noticias_por_uf.csv, noticias_por_tema.csv,
│                              robots_verificacao.csv
├── paginas/                   visao_geral, indicadores, prioridade, noticias,
│                              linguagem, assistente, arquivos, servico_api, documentacao
├── .streamlit/config.toml     tema e limite de upload
├── app.py                     roteador multipágina + barra lateral comum
├── api.py                     serviço HTTP com FastAPI (15 rotas)
├── assistente.py              memória, contexto de dados e prompt da conversa (TP5)
├── avaliar_assistente.py      verificação do assistente em quatro condições (TP5)
├── modelo_llm.py              modelos de linguagem locais, sem FastAPI nem Streamlit
├── nucleo.py                  leitura dos arquivos e cálculo do índice, sem Streamlit
├── coleta.py                  APIs do IBGE (indicadores + malha territorial)
├── scraping.py                extração web com Beautiful Soup
├── texto.py                   stopwords, tokenização, menções de UF, temas, conferência
└── utils.py                   cache do Streamlit, estado de sessão, chamada à API, reporte
```

---

## O que cada página faz

| Página | Conteúdo |
| --- | --- |
| **Visão geral** | Apresentação do projeto (texto do TP1) + métricas de cobertura + *Do dado ao insight*, o ciclo em cinco passos com atalhos (TP5) + perfil rápido de uma UF contra a média nacional |
| **Indicadores da ODS 4** | Filtros de região, indicador, ordem e faixa de valor; abas de ranking, mapa coroplético, tabela e dispersão entre dois indicadores |
| **Índice de prioridade** | Pesos ajustáveis por indicador, dois métodos de normalização, ranking, radar da seleção e download do reporte ESG |
| **Notícias e nuvem de palavras** | Nuvem configurável, termos mais frequentes, estatísticas por fonte/mês/tema, cruzamento entre menções na imprensa e carência medida, leitor de matéria |
| **Upload e download** | Envio de CSV com validação, download individual de cada arquivo e pacote ZIP com tudo |
| **Análise de linguagem** | Ficha dos dois modelos locais e carga sob demanda; processamento de um texto em sentimento (com a distribuição dos três rótulos) ou resumo (ao lado do resumo da redação, quando a matéria vem do corpus); classificação do corpus com agregação por rótulo e por UF ao lado do índice de prioridade |
| **Assistente ESG** | Conversa com memória sobre os dados (TP5): perguntas de exemplo, memória de foco na barra lateral, e ao lado de cada resposta a conferência, o gráfico das UFs citadas, as fontes e o bloco que o modelo leu; download da conversa em Markdown |
| **Serviço de API** | Situação do serviço, tabela das 15 rotas, explorador de consultas GET e formulário de envio POST |
| **Documentação** | Os sete documentos do repositório: Project Charter, Data Summary Report, Plano de uso de LLM, Escolha do modelo de linguagem, Assistente com memória, Referência da API e Relatório final |

---

## Observações sobre as mudanças do TP2

Este arquivo é anotação pessoal: está no `.gitignore` e não é lido pela aplicação. O que
entra no repositório e aparece na página de Documentação são o Project Charter e o Data
Summary Report.

Tudo que foi alterado em arquivo do TP1 está marcado com `# edited 21-09-2026` no código, ou
com `edited 21-09-2026` no texto dos documentos.

**1. Os dados saíram de `2_data_acquisition/` e foram para `data/`.**
No TDSP os diretórios de estágio guardam a *documentação* do estágio; os dados ficam em um
diretório próprio. O enunciado do TP2 também pede os arquivos em `data/`. Os dois CSVs do
TP1 foram movidos para `data/processed/` sem alteração de conteúdo, e `coleta.py` e o
Data Summary Report tiveram os caminhos corrigidos. Se preferir voltar ao layout antigo,
basta mudar `DESTINO` em `coleta.py` e os caminhos em `utils.py`.

**2. `app.py` virou roteador.**
O conteúdo estático do TP1 está inteiro em `paginas/visao_geral.py`, com o texto preservado.
`app.py` agora monta a navegação com `st.navigation` e desenha a barra lateral comum às
seis páginas.

**3. A malha do IBGE precisou de correção geométrica.**
A API de Malhas entrega os anéis dos polígonos no sentido anti-horário. O motor de mapas do
Plotly (d3-geo) lê esse sentido como "todo o globo menos o polígono", e o mapa saía como um
retângulo verde sólido. `coleta.py` inverte o sentido dos anéis antes de gravar o GeoJSON.
Se o mapa algum dia voltar a sair preenchido, é esse o ponto a investigar.

**4. A raspagem consulta o `robots.txt` antes de baixar qualquer coisa.**
`baixar()` é o único ponto de saída para a rede em `scraping.py`, e ele sempre passa por
`permitido()`. O agente declarado é `bussola-esg-educacao`, e o `Crawl-delay` de cada host é
respeitado — a Agência Brasil pede **10 segundos** entre requisições, e é daí que vem a
lentidão do script. Se o `robots.txt` não responder, ou responder 401, 403 ou erro de
servidor, o host é pulado: o padrão é não raspar. Cada execução grava
`data/processed/robots_verificacao.csv`, que aparece na página de notícias e na de downloads.

Para não repetir downloads, `scraping.py` reaproveita o corpo das matérias que já estão no
CSV e só busca as novas — uma execução sem novidade leva cerca de 1 minuto, contra os ~12 da
primeira coleta. Se quiser refazer tudo do zero, apague `data/raw/noticias_educacao.csv`.

**5. Por que a raspagem usa duas técnicas.**
A Agência Brasil é raspada do HTML da listagem paginada, com seletores de classe. Os outros
três sites são WordPress atrás de Elementor: o HTML da listagem é instável e depende de
JavaScript, então o ponto de entrada é o XML de sindicação — que também é lido com Beautiful
Soup, no modo XML. O corpo da matéria, nos quatro casos, vem da visita à página com a mesma
heurística de parágrafos longos.

**6. A contagem de menções por UF tem uma armadilha.**
Sem acento, `Pará` vira a preposição `para` e o estado aparecia em 104 das 105 matérias. Por
isso `texto.UFS` guarda os nomes acentuados e `Pará` só conta na forma acentuada. Siglas só
valem entre parênteses ou barras (`(PA)`, `/PA`), senão `TO` e `SE` capturam palavras
comuns em títulos.

**7. Cache e estado de sessão.**
`@st.cache_data` cobre as leituras de arquivo (TTL de 1 hora), o cálculo do índice, a
contagem de termos e a geração do PNG da nuvem. `@st.cache_resource` guarda o objeto
`WordCloud`, que é o único recurso caro e não serializável. O estado de sessão guarda a
cesta de UFs, os pesos do índice, as stopwords extras, os dados enviados por upload e um
histórico de ações — visível no expansor "Estado da sessão", na barra lateral, junto do
botão que limpa o cache.

**8. O upload não escreve em disco.**
As linhas enviadas ficam só no estado da sessão, marcadas com `origem = usuário`, e
alimentam todas as páginas de análise enquanto a sessão durar. Nenhum upload altera os
arquivos do repositório.

**9. Dependências novas.**
`beautifulsoup4` e `lxml` para a raspagem, `wordcloud` e `matplotlib` para a nuvem. O
`.python-version` fixa 3.12 porque é a versão que o Streamlit Community Cloud suporta e que
tem *wheel* pronto para `wordcloud`. Localmente o projeto roda em 3.14 sem problema.

---

## Observações sobre as mudanças do TP3

Tudo que foi alterado em arquivo anterior está marcado com `# edited 16-11-2026` no código,
ou com `edited 16-11-2026` no texto dos documentos.

**1. Nasceu `nucleo.py`, e é a mudança estrutural desta etapa.**
Com a API, passaram a existir dois consumidores dos mesmos dados. Se cada um calculasse o
índice por conta própria, o número da rota `/ranking` poderia divergir do número da tela — o
que neste projeto não é inconsistência de interface, é falha de rastreabilidade. Então a
leitura dos arquivos e os cálculos saíram de `utils.py` e foram para `nucleo.py`, em pandas
puro:

```
data/  →  nucleo.py  →  utils.py  →  app.py + paginas/     (painel Streamlit)
                    ↘  api.py                              (serviço HTTP FastAPI)
```

`utils.py` ficou só com o cache do Streamlit e o estado de sessão, delegando tudo ao núcleo.
**As assinaturas públicas de `utils.py` foram preservadas e nenhuma página precisou mudar** —
`utils.calcular_indice` continua recebendo a tupla de pesos que o cache exige e repassando ao
núcleo como dicionário.

**2. A API tem dez rotas, não duas.**
O mínimo pedido era uma de consulta e uma de escrita. Como o núcleo já estava separado, cada
rota virou cinco a quinze linhas, e cobrir os quatro ativos do projeto (indicadores, índice,
corpus, catálogo de fontes) saiu quase de graça. A documentação interativa em `/docs` é
gerada pelo FastAPI a partir das docstrings e das anotações de tipo de `api.py` — não há
arquivo de especificação mantido à mão. A referência escrita está em
`4_deployment/api_reference.md`.

**3. A escrita é volátil, de propósito.**
`POST /indicadores` guarda as linhas na memória do processo, marcadas com `origem = api`.
Gravar em `data/` daria persistência e tiraria a garantia que o Project Charter dá no risco
8.8 — a de que nenhum dado de terceiro altera os arquivos do repositório. É a mesma regra do
upload de CSV.

**4. Selenium foi avaliado e dispensado — com justificativa registrada.**
Três das quatro fontes raspadas *são* páginas dinâmicas: WordPress atrás de Elementor, cuja
listagem só existe depois do JavaScript. O caso de uso do Selenium existe. Mas o problema já
estava resolvido na etapa anterior pelo XML de sindicação, que cada um dos três sites publica
e que entrega o mesmo conteúdo em uma requisição, sem navegador. Automatizar um navegador
acrescentaria dependência de binário externo — que o Streamlit Community Cloud não provê —,
tempo de execução e fragilidade de espera por elemento, em troca de zero dado novo. A análise
fonte por fonte, e a condição que reabriria a decisão, estão na seção 1.4 do Data Summary
Report.

**5. A preparação para LLM é documento, não código.**
`3_modeling/plano_llm.md` registra cinco tarefas em ordem de prioridade, o insumo de cada
uma, como avaliá-la e o que falta decidir. O ponto útil é a seção 6.3 do Data Summary
Report: as colunas `temas_ods4` e `ufs_citadas` já existem, feitas por dicionário de termos,
e servem de linha de base determinística para medir o ganho de um modelo em vez de avaliá-lo
por impressão. A coluna `resumo` faz o mesmo para sumarização, com referência humana.

**6. Dependências novas.**
`fastapi` e `uvicorn`. Nenhuma das duas é importada pela aplicação Streamlit — quem só quer
o painel não precisa delas instaladas para rodar `streamlit run app.py`.

**7. O que foi testado.**
Vinte e seis verificações HTTP contra o serviço no ar, todas aprovadas, registradas com os
números obtidos na seção 5 da Referência da API: as dez rotas, os códigos de erro (422 para
método inválido e para `uf` fora da validação, 404 para indicador inexistente), o ciclo
completo POST → consulta → `incluir_enviados=false` → DELETE, e a paridade valor a valor
entre o índice do núcleo e o da rota `/ranking` nas 27 UFs. As sete páginas da aplicação
foram abertas no navegador depois da refatoração; o ranking da página de prioridade mostra
AC 81,1, o mesmo que a API devolve.

---

## Observações sobre as mudanças do TP4

**1. Duas tarefas de linguagem, e a escolha de cada uma está justificada com medição.**
O `plano_llm.md` tinha posto as tarefas gerativas em primeiro lugar — narrativa do reporte e
resumo das matérias — e o enunciado desta etapa exige execução local. A classificação de
sentimento entrou primeiro, por custo: roda em dezenas de milissegundos. O **resumo** entrou
depois, quando a medição mostrou um modelo em português que resume uma matéria em cerca de 3
segundos em CPU — aceitável para uma matéria por vez, proibitivo para o corpus em lote, e é
nesse formato que ele é oferecido. A narrativa do reporte continua fora, agora por um motivo
mais forte que o custo (ponto 7). Tudo na seção 1 de `3_modeling/modelo_llm.md` e na seção
1.2 do Project Charter.

**2. Quatro modelos foram carregados e medidos, não comparados por ficha técnica.**
Para o **sentimento**, seis frases de controle escritas para o domínio do projeto mais trinta
matérias reais. O candidato mais leve (`lxyuan/distilbert-...-sentiments-student`, 135 M de
parâmetros, 44 ms) acertou **3 de 6** frases e classificou **26 de 30** matérias como
positivas, incluindo uma reportagem sobre encarceramento indevido — a classe `neutro` nunca
passou de 0,15. O adotado (`cardiffnlp/twitter-xlm-roberta-base-sentiment`, 278 M, 80 ms)
acertou **6 de 6** e classificou 25 de 30 como neutras, que é a descrição correta de um
corpus formado em boa parte por release institucional.

Para o **resumo**, o `mT5_multilingual_XLSum` (582 M, 2,3 GB, 7 a 12 s por matéria) perdeu
para o `recogna-nlp/ptt5-base-summ-xlsum` (223 M, 892 MB, 3,5 a 4,7 s) porque **os dois
alucinam igual** — e, entre dois modelos que erram do mesmo jeito, decide o custo.

**3. `modelo_llm.py` segue a regra de `nucleo.py`, agora com um registro por tarefa.**
Não importa `fastapi` nem `streamlit`: os modelos são recurso do projeto, não do servidor
web. Cada um carrega, falha e é relatado em separado, de modo que a falha de um não derruba o
outro. A página *Análise de linguagem* **não** carrega modelo nenhum — consome as rotas, como
qualquer cliente. O motivo é de ciclo de vida: o Streamlit reexecuta o script inteiro a cada
interação, e centenas de milhões de parâmetros não podem ser carregados nesse ritmo.

**4. Quatro rotas novas, e a pedida pelo enunciado é uma delas.**
`POST /processar_texto` recebe um texto e um campo `tarefa`. Com `sentimento`, devolve o
rótulo **com a pontuação dos três** — em texto institucional a diferença entre o primeiro e o
segundo é pequena, e um rótulo sozinho pareceria mais seguro do que é. Com `resumo`, devolve
o texto gerado, a compressão e o campo `gerativo` em verdadeiro. A resposta tem cabeçalho
comum e um bloco por tarefa; o bloco da tarefa não pedida é **omitido**, não vem nulo. O
campo `tarefa` existia desde a primeira versão, com uma tarefa só, justamente para que a
segunda não quebrasse o contrato — e não quebrou.

`POST /noticias/sentimento` aplica a classificação ao corpus no servidor, para não trafegar
59 mil palavras pela rede. `GET /modelo` relata a situação dos dois **sem** carregar, e
`POST /modelo/carregar?tarefa=<tarefa>` tira a espera da primeira análise e serve de nova
tentativa depois de uma falha.

**5. Todas as 14 rotas declaram `response_model`, não só as novas.**
São 24 esquemas no `openapi.json`, contra os 5 do TP3. Onde a linha varia com o filtro —
indicadores e notícias — o tipo é `list[dict]`, porque ali a forma do registro é a forma do
CSV e congelá-la quebraria a rota a cada mudança de fonte; o envelope em volta é que está
tipado. Nas rotas de linguagem os modelos são estritos. A bateria do TP3 foi reexecutada
inteira depois disso: nenhuma rota anterior mudou de forma.

**6. O 503 foi verificado sem simular nada.**
Um segundo processo do serviço foi iniciado com o cache de modelos apontado para uma pasta
vazia e o acesso ao Hub desligado — a situação de quem clona o repositório e roda a API sem
rede. As 10 rotas de dados responderam 200 com os 27 estados, as 189 observações e as 105
matérias; as 4 de linguagem responderam 503 com motivo e instruções, nas duas tarefas;
`GET /modelo` respondeu 200 relatando as duas falhas em separado. E texto curto recebeu
**422, não 503**: não faz sentido reclamar da indisponibilidade de um modelo para um pedido
que seria inválido de qualquer forma.

**7. O modelo de resumo inventa, isso foi medido, e reabriu um risco que eu tinha dado por
eliminado.**
Uma versão anterior da documentação registrou que a escolha de um classificador *eliminava* o
risco 8.4 do Charter — "IA generativa produzir afirmação incorreta no reporte" —, já que um
classificador não afirma nada. Com a entrada do resumo isso deixou de valer. Dois casos, da
verificação automatizada:

- entrada que dizia "professores **do sexto ao nono ano**" → gerado: "lançam **nesta
  segunda-feira** a **primeira** formação para gestores de redes de ensino e professores **do
  terceiro e último ano**";
- entrada de 25 palavras, sem estado e sem número → gerado: "A rede estadual de ensino
  estadual **do Rio Grande do Sul** ampliou a oferta de vagas em creches […] para **mais de
  mil estudantes**".

Num projeto cujo produto é um reporte ESG sobre investimento por UF, uma cifra inventada
atribuída a um estado inventado é exatamente o dano que o risco descreve — e note que o texto
gerado é gramatical e soa apurado. Seção 5.2 de `3_modeling/modelo_llm.md` e risco 8.14 do
Charter.

**8. A contenção que não depende de quem lê: conferência automática contra a fonte.**
Marcar o texto como gerado é aviso, e aviso depende de atenção. Então todo resumo passa por
`texto.conferir_resumo`, que procura nele os três tipos de termo que um modelo gerativo
inventa com mais frequência — **número, data e nome próprio** — e checa cada um no texto de
origem, palavra inteira, sem acento. Não usa modelo: um modelo que confere outro tem o mesmo
problema do primeiro. Mora em `texto.py`, ao lado de `mencoes_uf` e `temas_do_texto`, e é
anexada **dentro de `modelo_llm.resumir`** — não pela rota — para que nenhum consumidor
receba um resumo sem ela.

A resposta ganha o bloco `conferencia`, com `situacao` (`sem divergência` ou `revisar`), as
contagens e a lista de termos com os ausentes primeiro; a tela marca cada um com ✅ ou ⚠️.
Numa execução pela interface, com a mesma entrada curta de 25 palavras, o modelo produziu
desta vez **"Cochabamba"** — cidade boliviana, em matéria sobre creche no Brasil —, "Estado
de Goiás" e "mil": os quatro termos saíram apontados, e a compressão veio em **132%**, isto
é, o resumo ficou maior que a entrada. Os dois sinais dizem a mesma coisa, e dizem na tela.

A conferência é **léxica, não semântica** — pega termo inventado, não pega relação invertida
entre entidades presentes no texto — e erra de propósito para o lado de apontar demais. Um
termo apontado que está no texto custa um olhar; um termo inventado que passa custa uma
afirmação falsa.

Outras contenções, todas implementadas: `gerativo` verdadeiro na resposta, `aviso` dizendo
que o resumo pode afirmar o que não está no original, o resumo exibido **ao lado do resumo
escrito pela redação**, busca em feixe no lugar da gulosa (que reduziu a invenção, ao custo
de 2 a 3 s por matéria), e o resumo não alimentando nada — nem reporte, nem `data/`, nem
cálculo.

**9. O limite de cada modelo está na tela, não só na documentação.**
No sentimento, a mesma notícia de evasão escolar sai como `negativo` escrita de forma direta
e como `neutro` na moldura jornalística ("aponta o levantamento divulgado nesta semana") — as
duas frases são exemplos prontos na página. A consequência que mais importa: **`neutro` não
significa "situação estável no território"** (risco 8.13). No resumo, a truncagem é dita em
proporção — "o modelo viu 44% do texto" —, porque um rótulo truncado é um rótulo sobre o
começo do texto, mas um resumo truncado parece um resumo do texto inteiro.

**10. O que foi testado.**
Cento e oito verificações nas rotas de linguagem, trinta e sete na indisponibilidade dos
modelos e a bateria do TP3 reexecutada inteira — **nenhuma falha nas três**, com os números
na seção 7 da Referência da API. A conferência foi testada também fora da API, em três casos
de laboratório: os dois resumos alucinados, em que apontou tudo o que era esperado, e um
resumo fiel de controle, em que não apontou nada. As oito páginas foram abertas no navegador;
a classificação de 20 matérias rodou em 1,6 s, o resumo de uma matéria de 895 palavras saiu
em 3,0 s com 1,8% de compressão ao lado do resumo da redação, e o cruzamento por UF apareceu
ao lado do índice de prioridade.

---

## Observações sobre as mudanças do TP5

Tudo que foi alterado em arquivo anterior está marcado com `# edited 25-11-2026 (TP5)` no
código, ou com `edited 25-11-2026 (TP5)` no texto dos documentos.

**1. Um caminho só, e um modelo só.** Das três opções do enunciado, a **memória
conversacional**. Sumarização já tinha sido levada no TP4 até onde ela serve, e um agente que
"propõe ações" tiraria a decisão dos pesos explícitos — que o risco 8.3 protege. Entre local e
API, o **local**: o `llama3.1:8b` já estava no Ollama desta máquina (4,9 GB, Q4_K_M), fala
português, roda 68% na RTX 2060 e não manda nada para fora. Nenhuma biblioteca nova: o
serviço fala com o Ollama por HTTP com o `requests`.

**2. A medição que decidiu o desenho.** Sem dado nenhum, o modelo disse que a alfabetização "é
medida pelo IDH e pelo IDE". Com o ranking no prompt, acertou os cinco índices. Daí a regra:
**o modelo não calcula nada** — ranking, valores, média das UFs, diferença, posição em cada
indicador e comparação chegam prontos de `nucleo.py`. O modelo lê e redige.

**3. Memória em duas camadas.** As seis últimas mensagens voltam ao modelo (ele entende "a
primeira delas"), e o **foco** — UFs, regiões, temas e indicadores citados, extraídos por regra,
sem modelo — decide que dados entram no prompt. Sem o foco, "e Pernambuco, comparado com ela?"
chegaria sem os dados da Bahia. A UF entra também pela resposta (é lá que está a lista de "a
primeira delas"); região, tema e indicador só pela pergunta. O serviço não guarda estado: a
memória vai e volta na requisição, e vive na sessão do Streamlit. Barra lateral mostra e apaga.

**4. A engenharia de prompt foi mais no dado que nas regras.** Seis falhas no desenvolvimento,
seis mudanças (seção 4.4 de `3_modeling/assistente_llm.md`). As que mais ensinaram: o Acre
dado como 3º pior em internet (é o 2º) → posição pronta; "Pernambuco abaixo da Bahia em 5 dos
7" (o 5 era da Bahia contra a média) → nome repetido e comparação pronta; "a Bahia tem a pior
alfabetização, 90,5% contra 89,9%" → "Pior situação"/"Melhor situação" por extenso e regra 8;
"os dados não cobrem" com o dado lá duas vezes, num prompt de 5,4 mil tokens → foco de no
máximo 3 UFs e comparação só quando pedida. **Nas três primeiras os números estavam certos e a
relação errada** — nenhuma conferência de número pegaria.

**5. A conferência ganhou a segunda consumidora.** `texto.conferir_resposta` usa a mesma lógica
de `conferir_resumo`, com três ajustes de forma (maiúscula de início de frase, decimal com ponto
ou vírgula, sigla "UF" colada no nome). `conferir_resumo` ficou idêntica — conferi contra a
versão do commit nos três casos do TP4. A referência é o bloco DADOS mais as perguntas do
usuário; respostas anteriores do assistente não contam, senão uma invenção repetida ganharia
respaldo.

**6. A verificação isola cada peça.** `avaliar_assistente.py` roda 10 perguntas em 4 conversas
sob 4 condições. **Final, com memória: 10 de 10, 5 de 5 nas que dependem da anterior, 0 de 55
termos sem respaldo, 10,4 s por resposta.** Sem memória: 5 de 10 (as cinco dependentes
erradas). Prompt ingênuo: 6 de 10, 9 termos sem respaldo, sugeriu fundos e empresas como
investimento, 24,9 s por resposta. Sem dados: 1 de 10, 47 de 106 termos sem respaldo —
Sudeste e Sul como prioritários, IDEB e IDH inventados, matérias sobre creche que não existem.
Revisão manual da condição final: 9 certas e 1 parcial (listou o Pará entre as matérias que
citam o Nordeste). Reprodutibilidade, entre duas execuções: as condições com o prompt final
repetiram 10 de 10 respostas palavra por palavra; o ingênuo, 7 de 10; o sem dados, 6 de 10 —
temperatura zero não garante determinismo nas respostas longas, com o modelo entre GPU e CPU.

**7. O que a avaliação ensinou sobre a própria avaliação.** A primeira versão das checagens
automáticas reprovou uma resposta certa (olhava a primeira UF citada, não a frase que dizia
"pior") e aprovou duas erradas (o Pará chamado de estado do Nordeste; quatro empresas sugeridas
como "opções de investimento"). As checagens foram corrigidas antes da rodada definitiva, e a
seção 6 do documento do assistente traz a leitura de cada resposta ao lado da checagem.

**8. Erro de memória não aparece na conferência.** Sem memória, "ela" virou o Pará, "das duas"
virou Paraíba e Alagoas — respostas fluentes, com **zero** termos sem respaldo. Por isso a
memória é visível e o foco de cada resposta vai na resposta da rota e na tela.

**9. O que o uso como contexto revelou sobre o dado.** Nenhuma das 105 matérias menciona
creche (o assistente disse isso em vez de inventar); o resumo do Observatório traz o rodapé do
feed do WordPress; a "média nacional" do painel é média simples das UFs, e o contexto passou a
dizer "média das UFs"; e todos os sete indicadores são "maior é melhor" — premissa do índice e
do prompt, registrada como regra de entrada de dado novo (seção 8.3 do Data Summary Report).

**10. Painel final.** Nova página *Assistente ESG* (memória na barra lateral; ao lado de cada
resposta, conferência, gráfico das UFs citadas contra o ranking e contra a média, fontes e o
bloco que o modelo leu; download da conversa com a procedência). Na *Visão geral*, a seção *Do
dado ao insight* mostra o ciclo em cinco passos com atalhos. Pela interface: as prioritárias →
"por que a primeira delas está no topo?" (explicou com as três maiores distâncias e os valores)
→ parágrafo para o reporte sobre Acre e Pará (os dois índices exatos, 3 de 3 termos conferidos).

**11. O que foi testado.** 53 verificações na API, nenhuma falha — contrato, memória de ida e
volta, paridade de pesos e método com o núcleo, 7 casos de 422, 503 com o Ollama inalcançável
numa segunda instância (porta 8001, `OLLAMA_URL` para porta fechada) com as rotas de dados
intactas, 15 de 15 operações tipadas, e a regressão do TP3/TP4 inteira; o caminho "modelo não
baixado" direto em `modelo_llm.py`; a avaliação em quatro condições, duas vezes; e as páginas
no navegador.

**12. Um defeito do TP4 apareceu e foi corrigido.** A página *Análise de linguagem* quebrava
inteira (`StreamlitDuplicateElementKey`) sempre que o modelo de sentimento não estava
carregado: o botão "Carregar agora" aparecia nas duas primeiras abas com a mesma chave. No TP4
o modelo estava sempre carregado durante os testes, por isso passou. A chave agora inclui a aba.

---

## Git e deploy

Os diretórios TDSP vazios (`3_modeling`, `4_deployment`, `5_customer_acceptance`) receberam um
`.gitkeep` para sobreviverem ao commit. O `.gitignore` já está pronto (ignora `.venv/`, `__pycache__/`,
`.streamlit/secrets.toml` e este README). Os arquivos de `data/` são versionados de propósito: são
pequenos, e é o que permite a aplicação subir sem rodar a coleta.

Pendente — inicialização do repositório e publicação, deixado a seu critério:

```bash
git init
git add .
git commit -m "TP2: interface interativa, raspagem web, cache e upload"
git branch -M main
git remote add origin <url-do-repositorio>
git push -u origin main
```

Para o Streamlit Community Cloud, apontar para o repositório, `app.py` como arquivo
principal e Python 3.12.

---

## Mapa da rubrica

| Item da rubrica | Onde está |
| --- | --- |
| Ambiente de desenvolvimento com Git e deploy | `.gitignore`, `.python-version`, `.streamlit/config.toml`, `requirements.txt` |
| Interface com interatividade | `paginas/` — multiselect, slider, radio, toggle, abas, seleção que atravessa páginas |
| Extração web com Beautiful Soup em CSV/TXT | `scraping.py`, que confere o `robots.txt` antes de baixar → `data/raw/noticias_educacao.csv` e `data/raw/noticias_corpus.txt` |
| Nuvem de palavras e estatísticas | `paginas/noticias.py` |
| Cache e estado de sessão | `utils.py` e barra lateral do `app.py` |
| Upload e download de CSV | `paginas/arquivos.py` |
| Project Charter | `1_business_understanding/project_charter.md` |
| Data Summary Report | `2_data_acquisition/data_summary_report.md` |
| **TP3** — menu de navegação e múltiplas páginas | `app.py` com `st.navigation`, sete páginas em `paginas/` em três grupos |
| **TP3** — API com FastAPI, ao menos duas rotas documentadas | `api.py` (10 rotas), referência em `4_deployment/api_reference.md`, docs interativas em `/docs` |
| **TP3** — revisão do Project Charter e do Data Summary Report | marcações `edited 16-11-2026`; reavaliação do problema na seção 1.1 do Charter |
| **TP3** — scraping dinâmico com Selenium | avaliado e dispensado com justificativa: Data Summary Report, seção 1.4 |
| **TP3** — preparação para LLM | `3_modeling/plano_llm.md` e seção 6 do Data Summary Report |
| **TP4** — identificação e escolha do modelo LLM local | `3_modeling/modelo_llm.md`, seções 1 a 3: quatro candidatos carregados e medidos sobre o corpus, dois por tarefa, com desempenho, custo em CPU e acessibilidade |
| **TP4** — justificativa documentada da escolha | `modelo_llm.md` 2.3 (por que o mais leve foi descartado), 2.4 (por que o adotado passou), 2.5 e 3.1 (as duas dependências que barraram a carga), 3.2 (os dois candidatos a resumo) e 3.3 (feixe em vez de guloso, como contenção) |
| **TP4** — modelo da HuggingFace executado localmente | `modelo_llm.py` — `cardiffnlp/twitter-xlm-roberta-base-sentiment` por `pipeline` e `recogna-nlp/ptt5-base-summ-xlsum` por `AutoModelForSeq2SeqLM`, torch de CPU, pesos no cache local, sem chamada a serviço externo |
| **TP4** — rota FastAPI ligada ao modelo | `POST /processar_texto` em `api.py`, com `tarefa` em `sentimento` ou `resumo`, mais `GET /modelo`, `POST /modelo/carregar` e `POST /noticias/sentimento` |
| **TP4** — Response Models | as 14 rotas com `response_model`; 26 esquemas no `openapi.json`; cabeçalho comum mais um bloco por tarefa em `RespostaTexto`, com `Conferencia` dentro de `ResultadoResumo`; seção 6 da Referência da API |
| **TP4** — contenção do texto gerado | `texto.conferir_resumo`, anexada dentro de `modelo_llm.resumir`: números, datas e nomes próprios do resumo conferidos contra a fonte, em toda resposta e sem opção de desligar; seção 5.3 de `3_modeling/modelo_llm.md` |
| **TP4** — tratamento robusto de erros com exceções HTTP | *exception handlers* de `ModeloIndisponivel` → 503, `ErroDeInferencia` → 500 e `TarefaDesconhecida` → 422 em `api.py`; 422 na validação, 404 em filtro vazio; seção 7 da Referência da API |
| **TP4** — teste das novas funcionalidades | 108 verificações nas rotas de linguagem + 37 na indisponibilidade + a bateria do TP3 inteira + 3 casos de laboratório da conferência, nenhuma falha; seção 7 da Referência da API; 503 exercitado com cache vazio e sem rede |
| **TP4** — revisão da documentação | seção 1.2, metas 4.12–4.16 e riscos 8.12–8.14 do Charter; seção 7 do Data Summary Report; seção 5 do `plano_llm.md`; e a correção explícita do que a versão anterior afirmava sobre o risco 8.4 |
| **TP5** — Tarefa 1: artefatos do TDSP completos | Charter: seção 1.3 (dados, IA e prompt alinhados ao problema), objetivos 3.13–3.14, metas 4.17–4.19, riscos 8.15–8.17, ética, arquitetura e marcos; Data Summary Report: seção 8 (cada dado da coleta ao insight); `plano_llm.md` seção 6; `3_modeling/assistente_llm.md`; `api_reference.md` seções 3.5 e 8; e o estágio 5, `5_customer_acceptance/relatorio_final.md` |
| **TP5** — Tarefa 2: um caminho com LLM | Opção 1, memória conversacional, por modelo local: `llama3.1:8b` via Ollama; `assistente.py` (memória, contexto, prompt), `modelo_llm.conversar`, `POST /assistente` |
| **TP5** — engenharia de prompt | `assistente.PROMPT_SISTEMA` (9 regras, cada uma ligada a uma regra do Charter ou a uma falha) e o bloco DADOS com tudo calculado; seção 4 de `assistente_llm.md` |
| **TP5** — Tarefa 3: dashboard final com IA | página *Assistente ESG* (conversa, memória visível, gráficos, fontes, conferência) e *Do dado ao insight* na *Visão geral* |
| **TP5** — Tarefa 4: apresentação e argumentação | `5_customer_acceptance/relatorio_final.md`: ciclo etapa por etapa, insights com números, alinhamento ODS/ESG, roteiro de demonstração (seção 7) e de validação com usuário (seção 8) |
| **TP5** — teste extensivo | `avaliar_assistente.py` (10 perguntas × 4 condições, duas execuções), 53 verificações na API sem falha, testes na interface |
