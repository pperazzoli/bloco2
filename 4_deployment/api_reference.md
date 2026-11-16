# Referência da API — Bússola ESG Educação

**Estágio TDSP:** 4. Deployment · **Data:** 2026-11-16

Serviço HTTP construído com **FastAPI** que expõe os dados do projeto — indicadores da
ODS 4, Índice de Prioridade de Investimento e corpus de notícias — a consumidores que não
são o painel: outro sistema, um notebook de análise, ou a própria aplicação Streamlit pela
página *Serviço de API*.

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
a página *Serviço de API* a consulta, e ela avisa na tela quando o serviço está fora do ar.
Para ver as duas coisas funcionando juntas, use dois terminais.

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
```

Cada camada acrescenta só o cache que lhe cabe: `utils.py` usa `@st.cache_data`, que é
por sessão de navegador; `api.py` usa `functools.lru_cache`, que é por processo. As
assinaturas públicas de `utils.py` foram preservadas, e nenhuma página da aplicação mudou
por causa da API.

---

## 3. Rotas

Dez rotas em três grupos. Todas respondem JSON. As de consulta devolvem um envelope com
`total`, os `filtros` aplicados e a lista `dados`.

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

---

## 5. Teste aplicado

Executado em 2026-11-16, com o serviço no ar em `127.0.0.1:8000`. Vinte e seis verificações,
todas aprovadas.

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
