# Data Summary Report — Bússola ESG Educação

**Estágio TDSP:** 2. Data Acquisition & Understanding
**edited 21-09-2026:** acrescentadas as fontes de conteúdo web, o corpus textual e as
tabelas derivadas. Os caminhos dos arquivos mudaram para `data/`. O que entrou nesta revisão
está indicado no início de cada seção.
**edited 16-11-2026:** acrescentada a avaliação das fontes dinâmicas e a decisão sobre
Selenium (seção 1.4), o canal de entrada por API (seção 4.2) e a avaliação do corpus como
insumo para tarefas de LLM (seção 6). O que entrou nesta revisão está marcado
*edited 16-11-2026*.

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

**1.1.3 IBGE — API de Malhas Territoriais**
*Adicionado em setembro — TP2.*
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

### 1.2 Fontes não estruturadas (extração web)

*Adicionado em setembro — TP2.*

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

### 1.4 Páginas dinâmicas: avaliação e decisão sobre Selenium

*Adicionado em novembro — TP3.*

As quatro fontes da seção 1.2 foram reexaminadas para determinar se alguma exige automação de
navegador. O critério aplicado foi único: **o conteúdo que o projeto precisa existe no HTML
que o servidor entrega, ou só aparece depois da execução de JavaScript no cliente?**

| Fonte | Conteúdo depende de JavaScript? | Ponto de entrada usado | Selenium resolveria algo? |
| --- | --- | --- | --- |
| Agência Brasil | Não. A listagem da editoria vem no HTML, paginada por `?page=N` | HTML da listagem | Não — o dado já está na resposta |
| Todos Pela Educação | **Sim**, a listagem é renderizada no cliente (Elementor) | XML de sindicação | Não — o feed entrega o mesmo conteúdo |
| GIFE | **Sim**, idem | XML de sindicação | Não — idem |
| Observatório do Terceiro Setor | **Sim**, idem | XML de sindicação | Não — idem |

**1.4.1 O caso dinâmico existe, e já estava resolvido.** Três das quatro fontes são WordPress
atrás do construtor Elementor: a página de listagem chega praticamente vazia e é montada no
navegador, o que torna inviável raspar a listagem com Beautiful Soup sobre o HTML servido.
Essa é exatamente a situação que motiva o uso de Selenium. A alternativa adotada na etapa
anterior foi o XML de sindicação que cada um dos três sites publica — interface estável,
mantida pelo próprio site para consumo automatizado, que entrega título, data, resumo e link
de cada item em **uma** requisição, contra a sequência de carregamento de navegador, espera
por elemento e rolagem que a listagem dinâmica exigiria. O corpo de cada matéria, nos quatro
casos, vem de HTML servido pelo servidor e é lido com Beautiful Soup.

**1.4.2 Decisão: não adotar Selenium.** Adotá-lo acrescentaria ao projeto a dependência de um
binário externo — navegador e *driver* compatíveis, que o Streamlit Community Cloud não
provê —, tempo de execução por matéria uma ordem de grandeza maior, e uma superfície de falha
nova, a de esperar por elemento que mudou de seletor. Em troca, zero dado novo: o conteúdo
obtido seria o mesmo que o feed já entrega. A decisão segue o princípio de manter a
simplicidade quando a ferramenta mais complexa não acrescenta resultado.

**1.4.3 Condição de reabertura.** A decisão vale para as fontes atuais e fica registrada como
reversível. Ela se reabre se alguma fonte futura apresentar: formulário de consulta cujo
resultado não tenha URL própria; filtro aplicado somente no cliente; rolagem infinita sem
feed ou endpoint equivalente; ou conteúdo atrás de interação obrigatória. O candidato mais
provável é o INEP (seção 1.1.4), cujo acesso aos microdados é previsto e hoje se dá por
download de arquivo — se a navegação até o arquivo passar a depender de interação, é ali que
o Selenium entra.

---

## 2. Dados estruturados coletados

*Item 2.10 adicionado em setembro — TP2.*

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

**2.10 Malha territorial** —
[`../data/raw/malha_uf.geojson`](../data/raw/malha_uf.geojson), 27 feições, 106 KB.
Tratamento aplicado na coleta: o IBGE entrega os anéis dos polígonos no sentido
anti-horário, que o motor de mapas do Plotly interpreta como "todo o globo menos o
polígono"; `coleta.py` inverte o sentido dos anéis antes de gravar.

---

## 3. Dados não estruturados coletados

*Adicionado em setembro — TP2.*

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

## 4. Dados fornecidos pelo usuário

*Adicionado em setembro — TP2.* *edited 16-11-2026: o canal por API entrou como seção 4.2.*

### 4.1 Upload de CSV na aplicação

A aplicação aceita CSV pela página de upload. Colunas obrigatórias: `indicador`, `uf`, `ano`
e `valor`; as demais recebem valor padrão. As linhas sem valor numérico são descartadas com
aviso na tela, e as aceitas recebem `origem = usuário` para permanecerem distinguíveis dos
dados oficiais em toda a aplicação. Esses dados vivem apenas no estado da sessão: não são
gravados no repositório e desaparecem ao fim da sessão.

### 4.2 Envio por API

*Adicionado em novembro — TP3.*

A rota `POST /indicadores` do serviço HTTP é o segundo canal de entrada, equivalente ao
upload para quem consome o projeto por programa em vez de pela interface. As mesmas quatro
colunas são obrigatórias, e a validação é feita pelo modelo Pydantic declarado em `api.py`,
não por verificação escrita à mão: `uf` tem de ter exatamente dois caracteres e é convertida
para maiúsculas, `ano` tem de estar entre 2000 e 2100, `valor` tem de ser número, e
`indicador` tem de ter ao menos três caracteres. Entrada fora disso responde HTTP 422
apontando o campo e o motivo.

As linhas aceitas recebem `origem = api` — distinta de `usuário`, para que a procedência de
cada observação permaneça identificável por canal — e `cod_uf = null`, o que as mantém fora
do mapa coroplético. Como no upload, **não há persistência**: vivem na memória do processo do
serviço e desaparecem ao reiniciá-lo. Qualquer consulta pode pedir `incluir_enviados=false`
para ver apenas o dado oficial, e `DELETE /indicadores/enviados` esvazia a base volátil.

A relação completa de parâmetros e respostas está na Referência da API,
[`../4_deployment/api_reference.md`](../4_deployment/api_reference.md).

---

## 5. Ética

Todas as fontes estruturadas são agregados públicos oficiais. O projeto não trata dados
pessoais de estudantes ou docentes, portanto não realiza operação sujeita à LGPD.

*edited 21-09-2026* — a extração de conteúdo web coleta material jornalístico publicado em
acesso aberto, com pausa de 0,4 segundo entre requisições e identificação do agente. O texto
é usado como corpus de análise linguística, e toda exibição na aplicação traz a fonte e o
link para o original.

*edited 16-11-2026* — o serviço HTTP mantém a mesma regra: toda matéria devolvida pela rota
`/noticias` acompanha a fonte e a URL do original, inclusive quando a resposta inclui o corpo
do texto. Nenhum consumidor recebe conteúdo desacompanhado de procedência.

---

## 6. Adequação do dado às tarefas de LLM

*Adicionado em novembro — TP3.*

Avaliação dos dados já coletados como insumo para as tarefas de modelo de linguagem previstas
para a próxima entrega. A especificação das tarefas está em
[`../3_modeling/plano_llm.md`](../3_modeling/plano_llm.md); aqui fica registrado apenas o que
diz respeito ao dado.

**6.1 Volume e dimensionamento.** O corpus tem 105 matérias e 59.185 palavras, o que equivale
a cerca de 90 mil *tokens* para processá-lo integralmente uma vez. A matéria média tem 563
palavras e a mediana 549, de modo que qualquer matéria individual cabe com folga na janela de
contexto de qualquer modelo atual, e mesmo lotes de dezenas de matérias cabem. Consequência
prática registrada: **não é necessário banco vetorial nem RAG com *embeddings*** nesta escala.
A seleção pelos filtros que já existem — fonte, UF, tema, busca textual, todos disponíveis em
`GET /noticias` — reduz o conjunto a poucas matérias, que vão inteiras no prompt.

**6.2 Qualidade do texto para processamento.** O corpo das matérias já está limpo: o HTML foi
removido na coleta, com descarte de `script`, `style`, `nav`, `header`, `footer`, `form` e
`aside`, e retenção dos parágrafos de 80 caracteres ou mais. A data está normalizada em ISO a
partir de dois formatos de origem, e cada registro traz fonte e URL. É texto pronto para
entrar em prompt sem etapa intermediária de limpeza.

**6.3 Referência para avaliação.** Duas colunas derivadas dão linha de base determinística
contra a qual medir o ganho de um modelo, em vez de avaliá-lo por impressão: `temas_ods4`,
atribuída por dicionário de termos declarado em `texto.TEMAS_ODS4`, cobre 98 das 105 matérias;
e `ufs_citadas`, obtida por casamento de nome acentuado e sigla delimitada, cobre 56. A
coluna `resumo` acrescenta uma referência humana para a tarefa de sumarização: nas três fontes
de sindicação é o resumo escrito pela própria redação, o que dispensa anotação manual.

**6.4 Dado tabular para geração de texto.** As 189 observações de `ods4_uf.csv` e o ranking
derivado delas são o insumo da tarefa de redação do reporte ESG. A regra que o Project Charter
fixa no risco 8.4 condiciona o formato desse insumo: o modelo recebe números **já apurados**
por `nucleo.py` e injetados no prompt, e em nenhuma hipótese calcula, estima ou interpola
valor. A limitação aceita é consequência disso — o texto gerado não pode afirmar nada que não
esteja na tabela que lhe foi entregue.

**6.5 Lacuna identificada.** O corpus cobre 05/08/2026 a 21/09/2026, cerca de sete semanas.
É suficiente para resumo, classificação e Q&A sobre o período, e **insuficiente** para
qualquer afirmação sobre tendência temporal. Nenhuma tarefa de LLM prevista depende de série
histórica; se alguma passar a depender, a coleta precisa ser reexecutada periodicamente para
acumular histórico, o que `scraping.py` já suporta — ele reaproveita as matérias presentes no
CSV e busca apenas as novas.
