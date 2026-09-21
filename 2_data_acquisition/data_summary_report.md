# Data Summary Report — Bússola ESG Educação

**Estágio TDSP:** 2. Data Acquisition & Understanding
**edited 21-09-2026 (TP2):** acrescentadas as fontes de conteúdo web, o corpus textual e as
tabelas derivadas. Os caminhos dos arquivos mudaram para `data/`. As seções novas estão
marcadas com *(TP2)*.

---

## 1. Fontes de dados

### 1.1 Fontes estruturadas (API)

**1.1.1 IBGE — API de Agregados (SIDRA)**
Tipo de dado: quantitativo contínuo, percentuais.
Acesso: API REST, sem chave.
Granularidade: Unidade da Federação.
Objetivo de uso: fonte principal do projeto. Fornece os indicadores oficiais de monitoramento
da ODS 4 que compõem o índice de prioridade de investimento.

**1.1.2 IBGE — API de Localidades**
Tipo de dado: categórico nominal, códigos e nomes.
Acesso: API REST, sem chave.
Granularidade: UF e região.
Objetivo de uso: tabela de domínio territorial. Fornece a chave de junção entre as fontes e o
agrupamento por região usado nas visualizações.

**1.1.3 IBGE — API de Malhas Territoriais** *(TP2)*
Tipo de dado: geoespacial, polígonos em GeoJSON.
Acesso: API REST, sem chave.
Granularidade: Unidade da Federação.
Objetivo de uso: base do mapa coroplético da aplicação. A chave `codarea` do GeoJSON casa com
a coluna `cod_uf` da tabela de indicadores.

**1.1.4 INEP — Censo Escolar e IDEB**
Tipo de dado: misto. Binário na infraestrutura por escola, quantitativo nas matrículas e
docentes, ordinal no IDEB.
Acesso: download de arquivo CSV em ZIP, sem API REST pública.
Granularidade: escola e município.
Objetivo de uso: descer a análise ao nível municipal, que a API do IBGE não cobre, e trazer o
IDEB como medida de resultado de aprendizagem. **Status: previsto.**

**1.1.5 Banco Mundial — World Development Indicators**
Tipo de dado: quantitativo contínuo, percentuais.
Acesso: API REST, sem chave.
Granularidade: país.
Objetivo de uso: benchmark internacional para dimensionar o problema brasileiro na narrativa
do reporte ESG. **Status: previsto.**

### 1.2 Fontes não estruturadas (extração web) *(TP2)*

Todas extraídas com **Beautiful Soup** pelo script `scraping.py`, executado fora da
aplicação. O tipo de dado é o mesmo nas quatro: **texto não estruturado** em português —
título, data de publicação, resumo e corpo da matéria.

Antes de qualquer download, o script consulta o `robots.txt` do host e só prossegue se a URL
for permitida ao agente `bussola-esg-educacao`. O resultado dessa conferência fica registrado
em [`../data/processed/robots_verificacao.csv`](../data/processed/robots_verificacao.csv) e
é exibido na própria aplicação. Situação das quatro fontes:

| Host | HTTP | Política | Intervalo respeitado |
| --- | --- | --- | --- |
| agenciabrasil.ebc.com.br | 200 | regras aplicadas; bloqueia `/includes/`, `/misc/`, `/modules/`, `/profiles/`, `/scripts/`, `/themes/` | 10 s (`Crawl-delay` do site) |
| todospelaeducacao.org.br | 200 | regras aplicadas; bloqueia `/wordpress/wp-admin/` | 0,4 s |
| gife.org.br | 200 | regras aplicadas; sem caminho bloqueado | 0,4 s |
| observatorio3setor.org.br | 200 | regras aplicadas; bloqueia `/dlm_uploads/` | 0,4 s |

Nenhum dos caminhos usados pelo projeto está entre os bloqueados, e nenhuma URL foi recusada
na coleta. Se um host passar a proibir o caminho, ou se o `robots.txt` ficar inacessível ou
responder 401, 403 ou erro de servidor, o script suspende a coleta daquele host e registra a
recusa — a postura padrão é não raspar.

**1.2.1 Agência Brasil — editoria de Educação**
Acesso: raspagem do HTML da listagem paginada (`/educacao?page=N`, 5 páginas), seguida da
visita a cada matéria para captura do corpo. Seletores usados: `div.ultima-noticia`,
`a.titulo-noticia`, `span.data`, `a.editoria`.
Granularidade: matéria jornalística.
Objetivo de uso: agenda pública oficial da educação. É a fonte mais volumosa e a única cujo
HTML é raspado diretamente da listagem.

**1.2.2 Todos Pela Educação**
Acesso: raspagem do XML de sindicação do site, interpretado com Beautiful Soup no modo XML.
Granularidade: matéria e artigo de opinião.
Objetivo de uso: leitura do terceiro setor especializado sobre as metas educacionais.

**1.2.3 GIFE**
Acesso: idêntico ao anterior.
Granularidade: matéria sobre investimento social privado.
Objetivo de uso: pauta do investidor social privado, que é o público primário da aplicação.

**1.2.4 Observatório do Terceiro Setor**
Acesso: idêntico ao anterior.
Granularidade: matéria e chamada de projeto social.
Objetivo de uso: projetos e organizações executoras em campo.

Nas três últimas, o corpo da matéria é obtido pela visita à URL de cada item com a mesma
heurística aplicada à Agência Brasil: remoção de `script`, `style`, `nav`, `header`, `footer`,
`form` e `aside`, e retenção dos parágrafos com 80 caracteres ou mais.

### 1.3 Fontes avaliadas e descartadas

`dados.gov.br`, que retorna HTTP 401 e funciona apenas como catálogo das fontes já acessadas
diretamente; e QEdu, que responde HTTP 403 a requisições automatizadas e não documenta
contrato de API pública.

---

## 2. Dados estruturados coletados

Arquivo [`../data/processed/ods4_uf.csv`](../data/processed/ods4_uf.csv):
**189 observações, 7 indicadores, 27 UFs, zero nulos**.

Indicadores coletados, com o agregado, a variável e a classificação de origem na API do IBGE:

**2.1** Indicador 4.a.1 — escolas de ensino médio com internet para fins pedagógicos.
Agregado 7783, variável 11086, classificação 812[41117]. Ano 2024.

**2.2** Indicador 4.a.1 — escolas de ensino médio com computador para fins pedagógicos.
Agregado 7783, variável 11086, classificação 812[41118]. Ano 2024.

**2.3** Indicador 4.a.1 — escolas de ensino médio com infraestrutura acessível.
Agregado 7783, variável 11086, classificação 812[41119]. Ano 2024.

**2.4** Indicador 4.1.2 — taxa de conclusão do ensino médio, pessoas de 20 a 22 anos.
Agregado 4731, variável 4721, classificação 582[59997]. Ano 2025.

**2.5** Indicador 4.2.2 — taxa de participação no ensino organizado aos 5 anos.
Agregado 4734, variável 4796, classificação 2[6794]. Ano 2025.

**2.6** Indicador 4.6.1 — taxa de alfabetização das pessoas de 15 anos ou mais.
Agregado 10436, variável 2513, classificação 58[95253]. Ano 2025.

**2.7** Indicador 4.c.1 — docentes do ensino médio com formação adequada.
Agregado 6676, variável 9610, classificação 2[6794] e 813[41125]. Ano 2024.

**2.8 Colunas do arquivo** — `indicador_ods`, `indicador`, `cod_uf`, `uf`, `regiao`, `ano`,
`valor`, `unidade`, `fonte`, `fonte_url`. As duas últimas guardam a proveniência de cada
valor: são elas que sustentam a meta de rastreabilidade de 100% e o pilar de Governança do
ESG.

**2.9 Arquivo auxiliar** — [`../data/processed/fontes.csv`](../data/processed/fontes.csv)
traz a mesma relação de fontes da seção 1 em formato tabular, consumida pela aplicação e
pelo reporte ESG. *edited 21-09-2026:* passou de 4 para 9 linhas com a entrada das fontes
web e da malha territorial.

**2.10 Malha territorial** *(TP2)* —
[`../data/raw/malha_uf.geojson`](../data/raw/malha_uf.geojson), 27 feições, 106 KB.
Tratamento aplicado na coleta: o IBGE entrega os anéis dos polígonos no sentido
anti-horário, que o motor de mapas do Plotly interpreta como "todo o globo menos o
polígono"; `coleta.py` inverte o sentido dos anéis antes de gravar.

---

## 3. Dados não estruturados coletados *(TP2)*

Arquivo [`../data/raw/noticias_educacao.csv`](../data/raw/noticias_educacao.csv):
**105 matérias, 4 fontes, 59.185 palavras**, período de 05/08/2026 a 21/09/2026.

**3.1 Distribuição por fonte**

| Fonte | Matérias | Forma de extração |
| --- | --- | --- |
| Agência Brasil | 65 | HTML da listagem paginada + corpo de cada matéria |
| Observatório do Terceiro Setor | 20 | XML de sindicação + corpo de cada matéria |
| Todos Pela Educação | 10 | XML de sindicação + corpo de cada matéria |
| GIFE | 10 | XML de sindicação + corpo de cada matéria |

**3.2 Colunas do arquivo**

| Coluna | Tipo | Origem |
| --- | --- | --- |
| `fonte` | categórico nominal | atribuído na coleta |
| `data` | data (ISO) | normalizada de dois formatos: `dd/mm/aaaa` e RFC 822 |
| `titulo` | texto | extraído da página |
| `resumo` | texto | do XML quando existe, senão os 300 primeiros caracteres do corpo |
| `editoria` | categórico nominal | extraído da página |
| `ufs_citadas` | lista, separada por `;` | derivado do texto por `texto.mencoes_uf` |
| `temas_ods4` | lista, separada por `;` | derivado do texto por `texto.temas_do_texto` |
| `n_palavras` | quantitativo discreto | contagem sobre título + resumo + corpo |
| `url` | texto | endereço da matéria original |
| `coletado_em` | data | carimbo da execução do script |
| `texto` | texto longo | corpo da matéria |

**3.3 Estatísticas descritivas do corpus** — média de 563 palavras por matéria, mediana de
549. 56 das 105 matérias citam ao menos uma UF; 98 receberam ao menos um tema da ODS 4.

**3.4 Cobertura temática** — a classificação é por dicionário de termos, declarado em
`texto.TEMAS_ODS4`. Uma matéria pode receber mais de um tema.

| Tema da ODS 4 | Matérias |
| --- | --- |
| 4.5 equidade | 69 |
| 4.3 técnico e superior | 64 |
| 4.1 conclusão e aprendizagem | 37 |
| 4.a infraestrutura | 19 |
| financiamento | 17 |
| 4.c docentes | 15 |
| 4.2 primeira infância | 8 |

**3.5 Corpus em texto puro** —
[`../data/raw/noticias_corpus.txt`](../data/raw/noticias_corpus.txt), 387 KB. Uma matéria por
bloco, blocos separados por linha em branco. É o insumo direto da nuvem de palavras.

**3.6 Registro de conformidade** —
[`robots_verificacao.csv`](../data/processed/robots_verificacao.csv), uma linha por host
consultado, com o endereço do `robots.txt`, o código HTTP da resposta, a política aplicada,
o intervalo respeitado entre requisições e o carimbo de data e hora da verificação.

**3.7 Tabelas derivadas** — gravadas em `data/processed/` pelo próprio `scraping.py`:
[`noticias_termos.csv`](../data/processed/noticias_termos.csv), os 300 termos mais
frequentes com sua contagem; [`noticias_por_uf.csv`](../data/processed/noticias_por_uf.csv),
menções por Unidade da Federação; e
[`noticias_por_tema.csv`](../data/processed/noticias_por_tema.csv), matérias por tema da
ODS 4.

**3.8 Tratamento de texto aplicado** — normalização para minúsculas sem acento; tokens de
mais de três caracteres; remoção de duas listas de stopwords, uma geral do português e outra
do domínio (`educação`, `escola`, `aluno`, `professor`, `Brasil`), esta última desligável na
interface. As menções de UF casam o nome por extenso e a sigla entre parênteses ou barras;
`Pará` exige a forma acentuada, sem o que colidiria com a preposição `para`.

---

## 4. Dados fornecidos pelo usuário *(TP2)*

A aplicação aceita CSV pela página de upload. Colunas obrigatórias: `indicador`, `uf`, `ano`
e `valor`; as demais recebem valor padrão. As linhas sem valor numérico são descartadas com
aviso na tela, e as aceitas recebem `origem = usuário` para permanecerem distinguíveis dos
dados oficiais em toda a aplicação. Esses dados vivem apenas no estado da sessão: não são
gravados no repositório e desaparecem ao fim da sessão.

---

## 5. Ética

Todas as fontes estruturadas são agregados públicos oficiais. O projeto não trata dados
pessoais de estudantes ou docentes, portanto não realiza operação sujeita à LGPD.

*edited 21-09-2026* — a extração de conteúdo web coleta material jornalístico publicado em
acesso aberto, com pausa de 0,4 segundo entre requisições e identificação do agente. O texto
é usado como corpus de análise linguística, e toda exibição na aplicação traz a fonte e o
link para o original.
