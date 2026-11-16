# Referência da API — Bússola ESG Educação

**Estágio TDSP:** 4. Deployment · **Data:** 2026-11-16

Serviço HTTP construído com **FastAPI** que expõe os dados do projeto — indicadores da
ODS 4, Índice de Prioridade de Investimento e corpus de notícias — a consumidores que não
são o painel: outro sistema, um notebook de análise, ou a própria aplicação Streamlit pelas
páginas *Serviço de API* e *Análise de linguagem*.

*Atualizado em 2026-11-16 (TP4): entrou o grupo de rotas de **linguagem natural**, que
processa texto com modelos carregados localmente — um de classificação de sentimento e um de
resumo; toda rota passou a declarar `response_model`; o tratamento de erro ganhou seção
própria. A justificativa de cada modelo está em `3_modeling/modelo_llm.md`.*

---

## 1. Como subir o serviço

Na raiz do projeto, com o ambiente virtual ativo:

```bash
uvicorn api:app --reload
```

Ou, equivalente, `python api.py`. O serviço sobe em `http://127.0.0.1:8000`.

**1.1 Documentação interativa** — gerada pelo próprio FastAPI a partir das anotações de
tipo e das docstrings de `api.py`, sem arquivo de especificação mantido à mão:

| Endereço | O que é |
| --- | --- |
| `http://127.0.0.1:8000/docs` | Swagger UI — permite executar cada rota do navegador |
| `http://127.0.0.1:8000/redoc` | ReDoc — leitura linear da especificação |
| `http://127.0.0.1:8000/openapi.json` | Especificação OpenAPI em JSON |

**1.2 Relação com a aplicação Streamlit** — são dois processos independentes. O painel
(`streamlit run app.py`) lê os arquivos de `data/` diretamente e **não depende** da API: só
as páginas *Serviço de API* e *Análise de linguagem* a consultam, e ambas avisam na tela
quando o serviço está fora do ar. Para ver as duas coisas funcionando juntas, use dois
terminais.

**1.3 Os modelos de linguagem** — as rotas do grupo `linguagem natural` precisam de
`transformers`, `torch` e `sentencepiece`, todos no `requirements.txt`. O `torch` do projeto
é a build de CPU; não há dependência de GPU em nenhum ponto.

```bash
pip install -r requirements.txt
```

São **dois modelos, um por tarefa**, carregados em separado:

| Tarefa | Modelo | Pesos | Por item, em CPU |
| --- | --- | --- | --- |
| `sentimento` | `cardiffnlp/twitter-xlm-roberta-base-sentiment` | 1,1 GB | 0,08 s |
| `resumo` | `recogna-nlp/ptt5-base-summ-xlsum` | 892 MB | ~3 s |

O serviço sobe normalmente **sem** modelo carregado: a carga é preguiçosa e só acontece na
primeira chamada que precisa daquele modelo, ou quando `POST /modelo/carregar` é chamado para
ele. Quem usa só uma das tarefas nunca paga o custo da outra. Na primeira vez os pesos são
baixados do HuggingFace Hub para o cache local (`~/.cache/huggingface/hub`); dali em diante a
carga é offline. Se um modelo não puder ser carregado, as rotas que dependem dele respondem
**503** e todas as demais continuam atendendo normalmente — ver a seção 7.

---

## 2. Decisão de arquitetura: o núcleo compartilhado

A entrada da API criou um segundo consumidor dos mesmos dados. Se cada um calculasse o
índice por conta própria, o número devolvido pela rota `/ranking` poderia divergir do número
exibido na página *Índice de prioridade* — o que, neste projeto, não é inconsistência de
tela, e sim falha de rastreabilidade, que é o pilar de Governança declarado no Project
Charter (seção 5.7).

Por isso a leitura dos arquivos e os cálculos saíram de `utils.py` e foram para
**`nucleo.py`**, em pandas puro, sem dependência de Streamlit:

```
data/  →  nucleo.py  →  utils.py  →  app.py + paginas/     (painel Streamlit)
                    ↘  api.py                              (serviço HTTP FastAPI)
                       ↑
            modelo_llm.py                                  (modelos de linguagem locais)
```

Cada camada acrescenta só o cache que lhe cabe: `utils.py` usa `@st.cache_data`, que é
por sessão de navegador; `api.py` usa `functools.lru_cache`, que é por processo. As
assinaturas públicas de `utils.py` foram preservadas, e nenhuma página da aplicação mudou
por causa da API.

**`modelo_llm.py` segue a mesma regra** (TP4): não importa `fastapi` nem `streamlit`, porque
os modelos são recurso do projeto e não do servidor web. Quem os carrega é o processo do
FastAPI, uma vez cada por execução. A página *Análise de linguagem* **não** carrega modelo
nenhum: consome as rotas, como qualquer outro cliente. A razão é de ciclo de vida — o
Streamlit reexecuta o script inteiro a cada interação do usuário, e modelos de centenas de
milhões de parâmetros não podem ser carregados nesse ritmo.

Dentro de `modelo_llm.py` há um **registro por tarefa**: cada entrada declara o modelo, a
janela de contexto e se é `gerativo`, e cada uma carrega, falha e é relatada em separado. Se
o modelo de resumo não carregar, a classificação continua respondendo 200.

---

## 3. Rotas

Quatorze rotas em quatro grupos. Todas respondem JSON e todas declaram `response_model`,
de modo que a forma da resposta está na especificação OpenAPI e não só na documentação
escrita (ver a seção 6). As de consulta devolvem um envelope com `total`, os `filtros`
aplicados e a lista `dados`.

### 3.1 Grupo `serviço`

**`GET /`** — índice do serviço: nome do projeto, versão, endereços da documentação
interativa e a relação de rotas com uma linha de descrição cada. É a rota de entrada para
quem recebeu o endereço e não tem a documentação.

**`GET /saude`** — diz se o serviço responde e se cada arquivo de dados esperado existe no
disco do servidor. Não lê o conteúdo dos arquivos, por isso responde rápido e serve para
monitoramento. É a rota que a página *Serviço de API* consulta a cada carregamento para
mostrar o indicador de situação.

```bash
curl http://127.0.0.1:8000/saude
```

**`GET /estatisticas`** — números gerais da base em um só lugar: UFs cobertas, indicadores
distintos, total de observações, ano mais recente, e do corpus de notícias as matérias,
fontes, palavras e o intervalo de datas.

### 3.2 Grupo `dados` (consulta)

**`GET /fontes`** — catálogo das fontes do projeto, com tipo de dado, forma de acesso,
granularidade, objetivo de uso e situação (`Coletado` ou `Previsto`). É a tabela que
sustenta a seção de rastreabilidade do reporte ESG.

**`GET /indicadores`** — consulta as observações de indicadores da ODS 4 por UF.

| Parâmetro | Tipo | Padrão | Função |
| --- | --- | --- | --- |
| `uf` | texto, repetível | — | Sigla da UF. `?uf=BA&uf=PI` traz as duas |
| `indicador` | texto | — | Trecho do nome do indicador, sem diferenciar maiúsculas |
| `indicador_ods` | texto | — | Código da meta, por exemplo `4.1.2` |
| `regiao` | texto, repetível | — | Região geográfica |
| `ano` | inteiro | — | Ano de referência |
| `incluir_enviados` | booleano | `true` | Inclui as observações recebidas por POST |
| `limite` | inteiro 1–1000 | `200` | Máximo de linhas na resposta |

Os filtros se combinam por E lógico. Cada linha vem com `fonte` e `fonte_url`, para que o
consumidor possa citar a origem do número que usou.

```bash
curl "http://127.0.0.1:8000/indicadores?uf=BA&ano=2025"
```

**`GET /ranking`** — calcula o Índice de Prioridade de Investimento e devolve o ranking
das UFs, da mais carente para a menos.

| Parâmetro | Tipo | Padrão | Função |
| --- | --- | --- | --- |
| `metodo` | texto | `min-max entre UFs` | Normalização. O outro valor aceito é `distancia de 100%` |
| `indicador` | texto, repetível | — | Restringe o cálculo a estes indicadores (nome exato) |
| `regiao` | texto, repetível | — | Filtra as UFs devolvidas, **sem** alterar o cálculo |
| `incluir_enviados` | booleano | `true` | Inclui as observações recebidas por POST |
| `limite` | inteiro 1–100 | `27` | Máximo de UFs na resposta |

Os indicadores entram com **peso igual**. Para ponderá-los de forma diferente, use a página
*Índice de prioridade* da aplicação, que expõe um controle de peso por indicador; pelo
serviço, `indicador` permite restringir o cálculo a um subconjunto, o que equivale a dar
peso zero aos demais.

O filtro `regiao` é aplicado **depois** do cálculo, de propósito: a posição devolvida
continua sendo a posição nacional, não a posição dentro da região.

A resposta traz ainda `indicadores_no_calculo`, com a lista do que entrou, e a `ressalva`
de que o índice é medida de prioridade de investimento, nunca de mérito do território — a
mesma ressalva que a aplicação imprime na tela e no reporte ESG.

```bash
curl "http://127.0.0.1:8000/ranking?metodo=distancia%20de%20100%25&limite=5"
```

Um `metodo` desconhecido responde **422**; um `indicador` inexistente responde **404** com
a lista dos disponíveis no corpo do erro.

**`GET /noticias`** — consulta o corpus coletado por raspagem, da matéria mais recente para
a mais antiga.

| Parâmetro | Tipo | Padrão | Função |
| --- | --- | --- | --- |
| `fonte` | texto, repetível | — | Nome da fonte |
| `uf` | texto | — | **Sigla** da UF citada, por exemplo `BA`. A coluna `ufs_citadas` guarda siglas, não o nome por extenso |
| `tema` | texto | — | Tema da ODS 4 atribuído na coleta, por exemplo `4.5 equidade` ou só `4.5` |
| `busca` | texto | — | Trecho a procurar no título, resumo e corpo |
| `com_texto` | booleano | `false` | Inclui o corpo integral da matéria |
| `limite` | inteiro 1–200 | `20` | Máximo de matérias na resposta |

O corpo integral fica fora da resposta por padrão: são 59 mil palavras no corpus, e quase
todo consumidor quer a lista, não o texto. É o campo `texto`, obtido com `com_texto=true`,
que alimentará as tarefas de LLM previstas em
[`../3_modeling/plano_llm.md`](../3_modeling/plano_llm.md). Toda matéria vem com `fonte` e
`url` do original.

### 3.3 Grupo `envio` (escrita)

**`POST /indicadores`** — recebe observações de indicadores e as incorpora à base da
execução. Atende ao objetivo 3.6 do Project Charter: o instituto que tem dado próprio de
cobertura de programa e quer vê-lo no ranking junto dos indicadores oficiais, sem acesso ao
repositório.

Corpo da requisição: **lista** de objetos, mesmo que de um único item.

| Campo | Obrigatório | Padrão | Validação |
| --- | --- | --- | --- |
| `indicador` | sim | — | Ao menos 3 caracteres |
| `uf` | sim | — | Exatamente 2 caracteres, convertidos para maiúsculas |
| `ano` | sim | — | Entre 2000 e 2100 |
| `valor` | sim | — | Número |
| `indicador_ods` | não | `personalizado` | — |
| `regiao` | não | `Não informada` | — |
| `unidade` | não | `%` | — |
| `fonte` | não | `Enviado pela API` | — |
| `fonte_url` | não | `""` | — |

```bash
curl -X POST http://127.0.0.1:8000/indicadores \
  -H "Content-Type: application/json" \
  -d '[{"indicador":"Cobertura do programa de reforco","uf":"BA","ano":2026,"valor":38.0}]'
```

Responde **201** com as linhas aceitas. Campo fora da validação responde **422** apontando
o campo e o motivo — validação feita pelo Pydantic a partir do modelo declarado em `api.py`,
não por verificação escrita à mão.

As linhas recebidas são marcadas com `origem = "api"`, o que as mantém distinguíveis do dado
oficial do IBGE em toda consulta, e recebem `cod_uf = null`, de modo que não entrem no mapa
coroplético. Elas passam a aparecer em `GET /indicadores` e a entrar no cálculo de
`GET /ranking`, salvo se a consulta pedir `incluir_enviados=false`.

**Persistência: nenhuma.** Os dados vivem na memória do processo. Nada é gravado em `data/`,
e ao reiniciar o serviço a base volta a ser só a oficial. É a mesma regra do upload de CSV na
aplicação (risco 8.8 do Project Charter): dado de terceiro não contamina o repositório.

**`GET /indicadores/enviados`** — lista o que foi recebido nesta execução.

**`DELETE /indicadores/enviados`** — esvazia a base volátil e devolve o serviço ao estado em
que só há dado oficial.

### 3.4 Grupo `linguagem natural`

As quatro rotas acrescentadas no TP4. São as únicas que dependem dos modelos locais descritos
em `3_modeling/modelo_llm.md`, e respondem **503** quando o modelo da tarefa pedida não pode
ser carregado.

**`GET /modelo`** — ficha dos dois modelos e situação de cada carga. **Não carrega nada**, por
isso responde em milissegundos e serve para a interface decidir o que oferecer ao usuário.

A resposta traz o ambiente (`execucao`, `cache_local`, `bibliotecas`,
`parametros_de_geracao`) e a lista `modelos`, com uma entrada por tarefa:

| Campo de cada entrada | O que traz |
| --- | --- |
| `tarefa`, `descricao` | `sentimento` ou `resumo`, e o que a tarefa faz |
| `modelo` | identificador no HuggingFace Hub |
| `gerativo` | se o modelo produz texto novo em vez de escolher entre rótulos fixos |
| `carregado` | se os pesos já estão na memória deste processo |
| `ja_baixado` | se os pesos estão no cache local, caso em que a carga não precisa de rede |
| `arquitetura`, `parametros`, `dispositivo` | só preenchidos após a carga |
| `limite_de_tokens` | janela de contexto do modelo: 512 nos dois |
| `rotulos` | os rótulos possíveis; vazio nas tarefas gerativas |
| `erro` | motivo da última falha de carga daquele modelo, se houve |

`gerativo` não é informativo apenas: é ele que decide quais regras de contenção do risco 8.4
do Project Charter se aplicam ao resultado.

**`POST /modelo/carregar`** — carrega os pesos de **um** modelo na memória, ou tenta de novo
depois de uma falha. Devolve a ficha daquele modelo.

| Parâmetro | Padrão | O que faz |
| --- | --- | --- |
| `tarefa` | `sentimento` | qual modelo carregar: `sentimento` ou `resumo` |

Existe por dois motivos. O primeiro é tirar o custo da carga da primeira análise: a interface
põe isso num botão, o usuário espera uma vez e as análises seguintes respondem rápido. O
segundo é a nova tentativa — uma falha de carga fica registrada no processo para não ser
repetida a cada requisição, e esta é a rota que força outra tentativa quando a causa da falha
tiver sido removida. A tarefa é parâmetro porque carregar os dois de uma vez ocuparia memória
que talvez ninguém vá usar, e quem precisa de um não deve esperar pelo outro.

**`POST /processar_texto`** — a rota de processamento de texto pedida pelo enunciado do TP4.
Recebe um texto e devolve o resultado da tarefa pedida.

Corpo da requisição:

```json
{"texto": "A evasão escolar no ensino médio voltou a crescer no estado.", "tarefa": "resumo"}
```

| Campo | Regra |
| --- | --- |
| `texto` | obrigatório, de 20 a 20.000 caracteres, espaços nas pontas descartados |
| `tarefa` | opcional, `sentimento` (padrão) ou `resumo`; qualquer outro valor é 422 |

A resposta tem um **cabeçalho comum** às duas tarefas e **um bloco com o nome da tarefa**. Só
o bloco da tarefa pedida aparece: o outro é omitido, não vem nulo.

| Campo do cabeçalho | O que traz |
| --- | --- |
| `tarefa`, `modelo` | a tarefa executada e o modelo que a executou |
| `gerativo` | **verdadeiro no resumo**, falso no sentimento |
| `caracteres`, `tokens`, `limite_de_tokens` | o tamanho do texto e o que o modelo de fato leu |
| `texto_truncado` | verdadeiro quando o texto passou do limite e o excedente foi ignorado |
| `segundos`, `analisado_em` | rastreabilidade do resultado |
| `aviso` | a ressalva da tarefa, diferente em cada uma |

Bloco **`sentimento`** — traz o rótulo vencedor *e a pontuação dos três*. Isso é deliberado:
em texto institucional a diferença entre o primeiro e o segundo é muitas vezes pequena, e um
rótulo sozinho pareceria mais seguro do que é.

| Campo | O que traz |
| --- | --- |
| `rotulo`, `confianca` | o rótulo de maior pontuação e a pontuação dele |
| `distribuicao` | os três rótulos com sua pontuação, do maior ao menor, somando 1 |

Bloco **`resumo`** — traz o texto gerado e o quanto ele comprimiu a entrada.

| Campo | O que traz |
| --- | --- |
| `resumo` | o texto gerado; **não é recorte do original** |
| `palavras_entrada`, `palavras_resumo` | tamanho da entrada e da saída |
| `taxa_de_compressao` | palavras do resumo divididas pelas palavras da entrada |
| `conferencia` | a conferência automática do resumo contra o texto de origem |

> **O resumo é abstrativo: o modelo reescreve, e pode afirmar o que não está no original —
> inclusive números.** Na verificação ele produziu datas, estados, uma cidade boliviana e uma
> cifra ausentes do texto de entrada; os casos estão transcritos na seção 5.2 de
> `3_modeling/modelo_llm.md`. Nenhum valor usado pelo projeto vem daqui.

O bloco **`conferencia`** existe por causa disso, e vem em **todo** resumo — não é opcional
nem precisa ser pedido. Procura no resumo os três tipos de termo que um modelo gerativo
inventa com mais frequência e checa cada um no original:

| Campo | O que traz |
| --- | --- |
| `situacao` | `sem divergência` ou `revisar` — basta um termo ausente para ser `revisar` |
| `conferidos`, `ausentes` | quantos termos verificáveis há no resumo e quantos não estão no original |
| `itens` | cada termo com o seu `tipo` (`número`, `data`, `nome próprio`) e `no_original`, com os **ausentes primeiro** |
| `metodo`, `ressalva` | como a conferência foi feita e o que ela não cobre |

Um consumidor que integre a rota pode agir sobre isso sozinho — descartar todo resumo com
`situacao: "revisar"`, por exemplo, ou exibir só os termos com `no_original: false`.

A conferência é **léxica, não semântica**: diz se o termo aparece no texto de origem, não se
o resumo é fiel ao sentido dele. E erra de propósito para o lado de apontar demais — um termo
apontado que está no texto custa um olhar; um termo inventado que passa custa uma afirmação
falsa.

A truncagem merece atenção redobrada nesta tarefa: um rótulo truncado é um rótulo sobre o
começo do texto, mas **um resumo truncado parece um resumo do texto inteiro**. Por isso
`tokens` e `texto_truncado` vêm na resposta, e a interface traduz o número em proporção — "o
modelo viu 44% do texto".

**`POST /noticias/sentimento`** — aplica o modelo ao corpus já coletado e agrega o resultado.
O corpus é lido no servidor: o cliente manda o filtro e recebe o resultado, em vez de
trafegar 59 mil palavras para analisá-las do próprio lado.

| Parâmetro | Padrão | O que faz |
| --- | --- | --- |
| `fonte` | — | nome da fonte; repita o parâmetro para várias |
| `uf` | — | sigla da UF citada na matéria, por exemplo `BA` |
| `tema` | — | tema da ODS 4 atribuído na coleta, por exemplo `4.5` |
| `campo` | `titulo e resumo` | que parte da matéria vai ao modelo; o outro valor é `texto` |
| `limite` | 20 | matérias a analisar, de 1 a 105; cada uma custa cerca de 80 ms de CPU |

Os três primeiros são os mesmos filtros de `GET /noticias`, aplicados **pela mesma função** —
as duas rotas têm de entender `uf=BA` do mesmo jeito, senão o cliente filtraria uma coisa na
consulta e outra na análise.

`campo` escolhe o insumo. O padrão é o lead da matéria, que cabe inteiro na janela de 512
tokens e é onde o tom editorial se concentra. Com `campo=texto`, o corpo integral é enviado e
**truncado, não rejeitado**: cada linha da resposta traz `tokens` e `texto_truncado`.

A resposta traz `dados` com uma linha por matéria classificada, mais três agregados:

| Campo | O que traz |
| --- | --- |
| `por_rotulo` | contagem de matérias por rótulo |
| `por_uf` | por UF citada: matérias, contagem de cada rótulo e `saldo` = (positivas − negativas) / matérias |
| `analisadas`, `total_no_corpus`, `segundos` | o recorte analisado e o custo |

Uma matéria que cita três UFs conta para as três, por isso a soma de `materias` em `por_uf`
passa do total analisado.

É `POST` e não `GET` por duas razões: a chamada é computação sob demanda, não leitura de
recurso, e assim nenhum intermediário a trata como resposta cacheável.

> **O resultado não entra no cálculo do índice de prioridade, em nenhuma hipótese.** Mede o
> tom da cobertura de imprensa, que é atenção editorial, não situação do território — é a
> ressalva do risco 8.6 do Project Charter. O campo `aviso` repete isso em toda resposta, e a
> tela o exibe.

---

## 4. Decisões e limites

**4.1 Sem autenticação.** O serviço só expõe agregados públicos oficiais e material
jornalístico de acesso aberto, e roda em `127.0.0.1` para uso local e acadêmico. Publicá-lo
em rede aberta exigiria, antes: autenticação na rota de escrita, limite de requisições por
cliente e CORS restrito à origem do painel. Está registrado como pendência, não como
omissão.

**4.2 Escrita volátil, por escolha.** Gravar o POST em `data/` daria persistência e tiraria
a garantia que o Project Charter dá no risco 8.8 — a de que nenhum dado de terceiro altera os
arquivos do repositório. Entre as duas, a garantia vale mais; persistir exigiria banco de
dados com separação entre dado oficial e dado de usuário, que é escopo de outra entrega.

**4.3 Cache por processo.** `lru_cache` lê cada CSV uma vez por processo. Em troca, atualizar
os arquivos de `data/` exige reiniciar o serviço. Com `--reload` ativo isso é automático a
cada alteração de código, mas não a cada alteração de dado.

**4.4 Sem paginação por cursor.** As rotas de consulta têm `limite`, não `offset`. A base
tem 189 observações e 105 matérias: paginação de verdade seria estrutura sem demanda. O
`total` devolvido no envelope já avisa ao consumidor quando a resposta foi truncada.

**4.5 Modelos carregados sob demanda, não na subida.** `uvicorn api:app` continua subindo em
menos de um segundo; quem usa só as rotas de dados nunca paga carga nenhuma, e quem usa só
uma das tarefas de linguagem nunca carrega o modelo da outra. Em troca, a primeira chamada de
cada tarefa leva alguns segundos — por isso existe `POST /modelo/carregar`, para tirar essa
espera do caminho da primeira análise.

**4.6 Falha de carga memorizada, por tarefa.** Uma carga que falhou não é tentada de novo a
cada requisição: o motivo fica registrado no processo, por modelo, e as chamadas seguintes
àquele modelo recebem 503 imediatamente. Sem isso, toda requisição repetiria uma tentativa
impossível e ficaria lenta sem mudar de resultado. O registro é por tarefa de propósito: a
falha de um modelo não deve contaminar o outro. `POST /modelo/carregar` é o caminho explícito
da nova tentativa.

**4.7 Duas tarefas, dois modelos, nenhuma geração em lote.** O serviço carrega um modelo de
classificação e um de resumo. O resumo é oferecido **uma matéria por vez**, e isso é decisão,
não limitação de implementação: resumir as 105 matérias do corpus levaria perto de sete
minutos de CPU para produzir texto que só vale alguma coisa lido um a um. `POST
/noticias/sentimento` é a rota em lote, e é só de classificação.

A narrativa do reporte ESG, prevista em `3_modeling/plano_llm.md`, continua fora — por um
motivo que a verificação tornou mais forte que o custo: um modelo que inventa cifras ao
resumir não pode redigir um relatório que cita cifras.

**4.8 Resultado não persistido.** Nem a classificação nem o resumo são gravados em `data/` ou
em qualquer outro lugar: vivem na resposta HTTP e, na interface, na sessão do usuário e no
download em CSV. É a mesma regra da escrita volátil de 4.2, pelo mesmo motivo — resultado de
modelo não é dado apurado e não entra no repositório ao lado dos indicadores oficiais.

**4.9 Parâmetros de geração fixos.** A geração do resumo usa `num_beams=4` e um limite de 90
tokens novos, declarados em `modelo_llm.GERACAO` e expostos em `GET /modelo`. Não são
configuráveis pelo cliente, por duas razões: resumo que muda de forma a cada chamada não serve
a um reporte, e a busca em feixe foi escolhida sobre a gulosa justamente por **reduzir
invenção** — deixá-la ao gosto de quem chama devolveria o problema que ela resolve.

**4.10 Conferência obrigatória, não opcional.** Todo resumo vem com o bloco `conferencia`.
Não há parâmetro para desligá-la, e isso é decisão de projeto: a conferência custa
milissegundos, não usa modelo, e é a única contenção do risco 8.4 que não depende de o leitor
prestar atenção ao aviso. Ela é anexada dentro de `modelo_llm.resumir`, e não pela rota, para
que nenhum consumidor do projeto — rota, página ou script — receba um resumo sem ela.

---

## 5. Teste aplicado

Executado em 2026-11-16, com o serviço no ar em `127.0.0.1:8000`. Vinte e seis verificações,
todas aprovadas. As baterias acrescentadas no TP4 estão na seção 7.3.

### 5.1 Consulta

| Verificação | Resultado |
| --- | --- |
| `GET /` | 200, anuncia as outras 9 rotas |
| `GET /saude` | 200, `situacao: no ar`, os três arquivos de dados presentes |
| `GET /estatisticas` | 200, 27 UFs, 7 indicadores, 189 observações, ano mais recente 2025; 105 matérias, 4 fontes, 59.185 palavras, 05/08/2026 a 21/09/2026 |
| `GET /fontes` | 200, 9 fontes |
| `GET /indicadores` | 200, 189 observações, todas com `fonte_url` preenchida |
| `GET /indicadores?uf=BA&ano=2025` | 200, 3 observações, só `uf = BA` e só `ano = 2025` |
| `GET /noticias?limite=3` | 200, `total: 105`, 3 devolvidas, **sem** a coluna `texto` |
| `GET /noticias?com_texto=true&limite=1` | 200, coluna `texto` presente, 5.839 caracteres |
| `GET /noticias?uf=BA` | 200, 4 matérias |
| `GET /noticias?tema=4.5` | 200, 69 matérias — coincide com a tabela 3.4 do Data Summary Report |
| `GET /openapi.json` e `GET /docs` | 200, especificação e Swagger UI servidos |

### 5.2 Índice de prioridade

| Verificação | Resultado |
| --- | --- |
| `GET /ranking` | 200, 27 UFs, 7 indicadores no cálculo, ordem decrescente confirmada linha a linha. Topo: AC 81,1 · PA 56,4 · PB 55,6 |
| `GET /ranking?metodo=distancia de 100%` | 200, mesma ordem no topo com outra escala: AC 36,3 · PA 31,2 · PB 27,1 |
| `GET /ranking?metodo=invalido` | **422**, com a lista dos dois métodos aceitos |
| `GET /ranking?indicador=inexistente` | **404**, com a lista dos 7 indicadores disponíveis |
| `GET /ranking?indicador=<um só>` | 200, `indicadores_no_calculo` com um único item |
| `GET /ranking?regiao=Nordeste` | 200, 9 UFs, todas do Nordeste, posições 3, 5, 7, 9, 10, 11, 13, 14 e 15 — **nacionais**, como especificado na seção 3.2 |

### 5.3 Escrita e isolamento do dado enviado

| Verificação | Resultado |
| --- | --- |
| `POST /indicadores` com linha válida | **201**, 1 aceita. `uf: "ba"` normalizada para `"BA"`, `origem: "api"`, `cod_uf: null` |
| `POST /indicadores` com `uf` de 3 letras | **422**, aponta `["body", 0, "uf"]` e a regra violada |
| `POST /indicadores` com lista vazia | **422**, "envie ao menos uma observação" |
| `GET /indicadores/enviados` | 200, 1 observação |
| Ranking após o POST | BA passa de **46,9** para **41,0** — a observação enviada entrou no cálculo |
| `GET /ranking?incluir_enviados=false` | 200, ranking **idêntico** ao original, UF por UF |
| `GET /indicadores?incluir_enviados=false` | 200, 189 observações, o dado enviado não aparece |
| `DELETE /indicadores/enviados` | 200, 1 descartada, 0 restantes |
| Ranking após o DELETE | **idêntico** ao original, UF por UF |

### 5.4 Paridade entre canais

Verificação da meta 4.11 do Project Charter: o índice calculado localmente por
`nucleo.calcular_indice`, que é a função que a página *Índice de prioridade* chama, foi
comparado valor por valor com o devolvido por `GET /ranking` com pesos iguais. **Resultado:
dicionários idênticos nas 27 UFs.** Não poderia ser diferente — é a mesma função —, e é esse
o ponto da verificação: confirmar que não há segunda implementação do cálculo no projeto.

Essa bateria foi **reexecutada inteira** depois da entrada dos `response_model` no TP4, para
confirmar que nenhuma rota anterior mudou de forma. Todas continuam aprovadas, a paridade das
27 UFs incluída.

---

## 6. Response models

Toda rota declara `response_model`. O FastAPI valida a saída contra a classe declarada antes
de serializar, e o `/docs` passa a mostrar o formato exato da resposta, não só o da
requisição. São **26 esquemas** no `openapi.json`, contra os 5 que havia no TP3.

O ganho é de contrato. Se uma rota deixar de devolver uma chave prometida, o erro aparece no
servidor como falha de validação, em vez de chegar ao cliente como resposta silenciosamente
diferente da documentada. Numa aplicação cuja meta declarada é rastreabilidade de 100%, uma
resposta que muda de forma sem aviso é falha de governança, não inconveniente de integração.

| Classe | Rotas | Observação |
| --- | --- | --- |
| `RespostaRaiz`, `RespostaSaude` | `/`, `/saude` | `saude` ganhou o bloco `modelo_de_linguagem` |
| `RespostaEstatisticas` | `/estatisticas` | dois modelos aninhados, um por bloco |
| `RespostaFontes` | `/fontes` | `total` e `dados`, sem envelope de filtro |
| `RespostaTabela` | `/indicadores`, `/noticias` | envelope `total` · `retornados` · `filtros` · `dados` |
| `RespostaRanking` | `/ranking` | inclui `indicadores_no_calculo` e a `ressalva` |
| `RespostaEnvio`, `RespostaEnviados`, `RespostaDescarte` | grupo `envio` | — |
| `RespostaModelos`, `FichaModelo` | `/modelo` | uma ficha por tarefa; campos de pós-carga nulos antes dela |
| `FichaModelo` | `/modelo/carregar` | a ficha do modelo que foi carregado |
| `RespostaTexto`, `ResultadoSentimento`, `ResultadoResumo`, `Pontuacao` | `/processar_texto` | cabeçalho comum mais um bloco por tarefa |
| `Conferencia`, `ItemConferido` | dentro de `ResultadoResumo` | a conferência faz parte do resultado, não é só tela |
| `RespostaNoticias`, `NoticiaClassificada`, `SentimentoPorUF` | `/noticias/sentimento` | `saldo` limitado a [−1, 1] |

Onde o conteúdo da linha varia com o filtro — as tabelas de indicadores e de notícias — o
tipo é `list[dict]`. Ali a forma do registro é a forma do CSV de origem, e congelar coluna
por coluna no modelo quebraria a rota a cada mudança de fonte de dados. O envelope em volta é
que está tipado, e é ele que o cliente usa para paginar e para saber o que foi filtrado. Nas
rotas de linguagem, onde a forma é conhecida e estável, os modelos são estritos.

`RespostaTexto` merece nota própria, porque é onde a segunda tarefa poderia ter quebrado o
contrato e não quebrou. O cabeçalho é comum; o resultado vem num bloco com o nome da tarefa,
e o bloco da tarefa não pedida é **omitido** da resposta, não enviado nulo — é o que
`response_model_exclude_none` faz. Quem já consumia a rota com a tarefa padrão continua
recebendo `tarefa`, `modelo` e o bloco `sentimento`; acrescentar uma terceira tarefa é
acrescentar um bloco, sem tocar nos outros dois.

---

## 7. Tratamento de erro

### 7.1 Códigos e o que cada um significa

O princípio é o da seção 10 do Project Charter, estendido aos modelos: **a indisponibilidade
de um modelo degrada a funcionalidade dele e não derruba o resto** — nem as rotas de dados,
nem a outra tarefa de linguagem.

| Situação | Código | A resposta traz |
| --- | --- | --- |
| Pesos ausentes, sem rede, `transformers` não instalado, memória insuficiente | **503** | motivo, os modelos do serviço, quatro passos do que fazer, e o que continua funcionando |
| Texto com menos de 20 caracteres úteis, ou só espaços | **422** | o campo apontado e a regra violada |
| `tarefa`, `campo` ou `metodo` com valor desconhecido | **422** | os valores aceitos |
| `tarefa` fora do registro em `/modelo/carregar` | **422** | as tarefas que existem |
| `limite` fora do intervalo | **422** | o limite e o valor recebido |
| Filtro que não casa com nenhuma matéria | **404** | os filtros como foram interpretados e o total do corpus |
| Indicador inexistente em `/ranking` | **404** | a lista dos indicadores disponíveis |
| Modelo carregado, falha ao processar o texto | **500** | o tipo da exceção e que o modelo está de pé |

As três exceções de `modelo_llm.py` — `ModeloIndisponivel`, `ErroDeInferencia` e
`TarefaDesconhecida` — são traduzidas por *exception handlers* registrados no `app`, **em um
lugar só**, em vez de um `try/except` repetido em cada rota. A distinção importa a quem
consome: **503** é o serviço dizendo que o modelo não está disponível e que a requisição pode
ser repetida depois; **500** é falha ao processar aquele texto específico, com o modelo
funcionando; **422** é o pedido que está errado, não o serviço.

Exemplo de resposta 503:

```json
{
  "detail": {
    "erro": "modelo de linguagem indisponível",
    "modelos": {
      "sentimento": "cardiffnlp/twitter-xlm-roberta-base-sentiment",
      "resumo": "recogna-nlp/ptt5-base-summ-xlsum"
    },
    "motivo": "falha ao carregar ... — OSError: We couldn't connect to 'https://huggingface.co' ...",
    "o_que_fazer": [
      "confira se as dependências estão instaladas: pip install -r requirements.txt",
      "a primeira carga baixa os pesos do HuggingFace Hub e precisa de rede",
      "tente carregar de novo em POST /modelo/carregar?tarefa=<tarefa>",
      "consulte GET /modelo para ver a situação de cada modelo"
    ],
    "rotas_nao_afetadas": "as rotas de /indicadores, /ranking, /noticias e /fontes não dependem do modelo e continuam respondendo normalmente"
  }
}
```

### 7.2 Verificação da indisponibilidade, sem simulação

O caminho do 503 foi exercitado **sem alterar o código**: um segundo processo do serviço foi
iniciado em `127.0.0.1:8001` com o cache do HuggingFace apontado para uma pasta vazia e o
acesso ao Hub desligado — a situação real de quem clona o repositório e roda a API sem rede.
**Trinta e sete verificações, nenhuma falha.**

| Verificação | Resultado |
| --- | --- |
| `GET /saude` | 200, `situacao: "no ar"`, `pesos_no_cache_local: false` nas duas tarefas |
| `GET /ranking`, `GET /indicadores`, `GET /noticias`, `GET /fontes` | 200, com 27 UFs, 189 observações, 105 matérias e 9 fontes — **intactas sem os modelos** |
| `POST /processar_texto` (sentimento) | **503**, com motivo, os quatro passos e a lista do que não foi afetado |
| `POST /processar_texto` (resumo) | **503**, mesma forma de erro |
| `POST /noticias/sentimento` | **503**, mesma forma de erro |
| `POST /modelo/carregar` nas duas tarefas | **503**, mesma forma de erro |
| `POST /processar_texto` com texto de 4 caracteres | **422**, não 503 — a validação de entrada tem precedência |
| `POST /modelo/carregar?tarefa=traducao` | **422**, não 503 — o pedido é que está errado |
| `GET /modelo` | **200**, relatando `carregado: false`, `ja_baixado: false` e o motivo da falha **em cada um dos dois** |

As duas penúltimas linhas são as que mais importam: não faz sentido reclamar da
indisponibilidade de um modelo para um pedido que seria inválido de qualquer forma.

### 7.3 Verificação das rotas de linguagem

**Cento e oito verificações com o serviço normal, nenhuma falha.**

| Verificação | Resultado |
| --- | --- |
| `GET /modelo` antes de qualquer carga | 200, as **duas** tarefas, nenhuma carregada, pesos em cache, três rótulos no classificador e nenhum no gerativo |
| `gerativo` por tarefa | `false` no sentimento, `true` no resumo |
| `GET /saude` | 200, relata os dois modelos **sem** carregá-los |
| `POST /modelo/carregar?tarefa=sentimento` | 200 em **7,9 s**: `XLMRobertaForSequenceClassification`, **278.045.955** parâmetros, `cpu` |
| `GET /modelo` logo depois | 200, **resumo continua descarregado** — a carga é por tarefa |
| `POST /modelo/carregar?tarefa=resumo` | 200 em **1,5 s**: `T5ForConditionalGeneration`, **223 milhões** de parâmetros, `cpu` |
| `POST /modelo/carregar?tarefa=traducao` | **422**, com a lista das tarefas que existem |
| `POST /processar_texto`, denúncia direta | 200, `negativo` 0,864 |
| `POST /processar_texto`, divulgação institucional | 200, `neutro` 0,876 |
| `POST /processar_texto`, avanço anunciado | 200, `positivo` 0,823 |
| `POST /processar_texto`, fato negativo com moldura de relato | 200, `neutro` 0,537 com `negativo` em segundo — o limite documentado na seção 5.1 de `modelo_llm.md` |
| Distribuição devolvida | três rótulos, ordenada, somando **1,000** |
| Tempo por classificação após a carga | **0,08 s** |
| `POST /processar_texto` com `tarefa: resumo`, texto de 194 palavras | 200 em **2,2 s**, resumo de 29 palavras, compressão de **14,9%** |
| `POST /processar_texto` com `tarefa: resumo`, texto curto | 200, resumo devolvido |
| Bloco da tarefa não pedida | **ausente** da resposta nas duas direções |
| `conferencia` em todo resumo | presente, com contagem batendo com a lista, ausentes primeiro, `situacao` coerente e tipos dentro dos três previstos |
| Conferência num resumo que inventa | apontou os termos sem respaldo |
| Conferência num termo que está no original | `Itaú Social` reconhecido como presente |
| Texto de 4 caracteres · só espaços · `tarefa` desconhecida · corpo sem `texto` | **422** nos quatro, apontando o campo |
| Texto de 722 tokens, nas **duas** tarefas | 200, `texto_truncado: true` nas duas |
| `POST /noticias/sentimento?limite=10` | 200, 10 de 105 em **0,85 s**, soma dos rótulos fechando em 10 |
| `POST /noticias/sentimento?campo=texto&limite=5` | 200, **5 de 5 truncadas**, de 726 a 1.238 tokens |
| `POST /noticias/sentimento?tema=4.5` | 200, todas as linhas do tema pedido, conferidas uma a uma |
| `POST /noticias/sentimento?uf=AM` | 200, 4 matérias, todas citando AM |
| `campo` inválido · `limite=500` | **422** nos dois, com os valores aceitos |
| `uf=ZZZZ` | **404**, com os filtros interpretados e o total do corpus |
| `saldo` de `por_uf` | dentro de [−1, 1] em todas as linhas |

### 7.4 Verificação da especificação

| Verificação | Resultado |
| --- | --- |
| Esquema de resposta no código de sucesso | presente nas **14 operações**, nenhuma pendente |
| Caminhos e esquemas no `openapi.json` | 12 caminhos, **26 esquemas** |
| Blocos de resultado no esquema | `ResultadoSentimento` e `ResultadoResumo` presentes |
| Conferência no esquema | `Conferencia` e `ItemConferido` presentes |
| Ficha de modelo no esquema | `FichaModelo` presente |
| 503 declarado em `/processar_texto` | sim — a rota documenta 200, 422, 500 e 503 |
| Descrição por grupo de rotas | os quatro grupos descritos: `serviço`, `dados`, `envio`, `linguagem natural` |
| `GET /docs` e `GET /redoc` | 200 |
