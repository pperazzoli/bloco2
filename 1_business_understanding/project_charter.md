# Project Charter — Bússola ESG Educação

**Estágio TDSP:** 1. Business Understanding · **Data:** 2026-08-24
**edited 21-09-2026:** escopo, riscos, arquitetura e marcos revisados. O que entrou nesta
revisão está indicado no início de cada seção.
**edited 16-11-2026:** problema de negócio reavaliado à luz das novas ferramentas (FastAPI e
Selenium), escopo estendido ao serviço HTTP e à preparação para LLM, riscos e arquitetura
revisados. O que entrou nesta revisão está marcado *edited 16-11-2026*.

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

**2.2 Não inclui** — dados nominais de escolas individuais; dados pessoais de estudantes ou
docentes; avaliação jurídica de entidades beneficiadas; recomendação de investimento
financeiro. *edited 21-09-2026:* também está fora de escopo qualquer modelo preditivo — o
índice é composição determinística de indicadores observados, não previsão. *edited
16-11-2026:* também está fora de escopo a persistência do dado enviado pelo usuário — nem o
upload de CSV nem a rota de escrita da API gravam em disco, por decisão registrada no risco
8.8; e está fora de escopo publicar o serviço HTTP em rede aberta, que exigiria autenticação,
limite de requisições e CORS restrito, conforme a seção 4.1 da Referência da API.

**2.3 Restrição** — os indicadores 4.a.1 e 4.c.1 do IBGE só descem até o nível de UF. A
descida ao nível municipal depende dos microdados do INEP.

---

## 3. Objetivos

*Objetivos 3.5 e 3.6 adicionados em setembro — TP2. Objetivos 3.7 e 3.8 adicionados em
novembro — TP3.*

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

---

## 4. Metas e indicadores de sucesso

*Metas 4.8 e 4.9 adicionadas em setembro — TP2. Metas 4.10 e 4.11 adicionadas em
novembro — TP3.*

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
rotas, com ao menos uma de consulta e uma de escrita. **Situação atual: 10 rotas, 8 de
consulta e 2 de escrita, todas com documentação interativa gerada pelo FastAPI.**

**4.11 Paridade entre canais** — indicador: diferença entre o índice devolvido pela rota
`/ranking` e o índice exibido na página de prioridade, com os mesmos pesos e método. Alvo:
zero. Garantido por construção — os dois chamam a mesma função de `nucleo.py`, e não há
segunda implementação do cálculo no projeto.

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
novembro — TP3.*

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

**8.5 Quebra do seletor de raspagem** — os sites de origem podem mudar de HTML.
Mitigação: `scraping.py` isola cada fonte em sua própria função, registra aviso e segue com
as demais; os dados já coletados permanecem em `data/raw/`.

**8.6 Viés de cobertura da imprensa** — a contagem de menções por UF reflete a
atenção editorial, não a carência do território. Mitigação: a menção nunca entra no cálculo
do índice; aparece apenas como camada de contexto, e a aplicação declara isso na própria tela.

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
degrada a funcionalidade de texto e não derruba o painel.

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

---

## 10. Arquitetura da solução

*Adicionado em setembro — TP2.* *edited 16-11-2026: entraram as camadas de núcleo e de
serviço HTTP; a interface passou a sete páginas.*

| Camada | Componente | Responsabilidade |
| --- | --- | --- |
| Coleta | `coleta.py` | APIs do IBGE: indicadores da ODS 4 e malha territorial |
| Coleta | `scraping.py` | Beautiful Soup sobre 4 fontes de conteúdo em educação |
| Texto | `texto.py` | Stopwords, tokenização, menções de UF e classificação temática |
| Dados | `data/raw`, `data/processed` | Camada bruta e camada tratada, ambas versionadas |
| Núcleo | `nucleo.py` | Leitura dos arquivos e cálculo do índice, em pandas puro |
| Serviço | `utils.py` | Cache do Streamlit, estado de sessão e reporte ESG |
| Serviço | `api.py` | Serviço HTTP em FastAPI: 10 rotas sobre o mesmo núcleo |
| Interface | `app.py` + `paginas/` | Sete páginas de navegação, filtros e downloads |

A coleta roda fora da aplicação, por decisão de projeto: o painel não depende de rede,
sobe em segundos e pode ser publicado sem credenciais.

*edited 16-11-2026* — `nucleo.py` foi extraído de `utils.py` quando a API passou a ser um
segundo consumidor dos mesmos dados. É a peça que garante a meta 4.11 e mitiga o risco 8.9:

```
data/  →  nucleo.py  →  utils.py  →  app.py + paginas/     (painel Streamlit)
                    ↘  api.py                              (serviço HTTP FastAPI)
```

O painel e o serviço são processos independentes, e o painel não depende do serviço. A
Referência da API, em [`../4_deployment/api_reference.md`](../4_deployment/api_reference.md),
documenta as rotas, os parâmetros e os limites de cada uma.

---

## 11. Marcos

*Adicionado em setembro — TP2.* *edited 16-11-2026: acrescentados os marcos do TP3.*

| Marco | Estágio TDSP | Situação |
| --- | --- | --- |
| Project Charter e definição do problema | Business Understanding | Concluído |
| Coleta via API e Data Summary Report | Data Acquisition | Concluído |
| Extração de conteúdo web e corpus textual | Data Acquisition | Concluído |
| Índice de prioridade e interface interativa | Modeling | Concluído |
| Núcleo de dados sem dependência de interface | Modeling | Concluído |
| Serviço HTTP em FastAPI e sua referência | Deployment | Concluído |
| Especificação das tarefas de LLM | Modeling | Concluído |
| Implementação das tarefas de LLM | Modeling | Previsto — próxima entrega |
| Validação com usuário de Sustentabilidade | Customer Acceptance | Previsto |
