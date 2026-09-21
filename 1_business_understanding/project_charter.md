# Project Charter — Bússola ESG Educação

**Estágio TDSP:** 1. Business Understanding · **Data:** 2026-08-24
**edited 21-09-2026:** escopo, riscos, arquitetura e marcos revisados. O que entrou nesta
revisão está indicado no início de cada seção.

---

## 1. Problema de negócio

Empresas com agenda ESG investem em educação básica, mas decidem onde aplicar o recurso
por relacionamento, e não por evidência. O dado público existe — INEP e IBGE publicam
indicadores abertos — porém disperso entre microdados e APIs distintas, inacessível a quem
decide. No reporte de sustentabilidade, o impacto é descrito de forma qualitativa, sem
rastreabilidade até a fonte oficial, o que expõe a empresa a risco de *social washing*.

**Solução.** Aplicação que ranqueia territórios por prioridade de investimento a partir dos
indicadores oficiais da ODS 4 e gera o reporte ESG com a fonte de cada número registrada.

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

**2.2 Não inclui** — dados nominais de escolas individuais; dados pessoais de estudantes ou
docentes; avaliação jurídica de entidades beneficiadas; recomendação de investimento
financeiro. *edited 21-09-2026:* também está fora de escopo qualquer modelo preditivo — o
índice é composição determinística de indicadores observados, não previsão.

**2.3 Restrição** — os indicadores 4.a.1 e 4.c.1 do IBGE só descem até o nível de UF. A
descida ao nível municipal depende dos microdados do INEP.

---

## 3. Objetivos

*Objetivos 3.5 e 3.6 adicionados em setembro — TP2.*

**3.1** Coletar via API os indicadores oficiais de monitoramento da ODS 4.

**3.2** Consolidá-los em um Índice de Prioridade de Investimento por território.

**3.3** Disponibilizar o ranking em painel interativo.

**3.4** Gerar o reporte ESG com rastreabilidade de fonte, ano e URL de cada valor.

**3.5** Monitorar a agenda pública da educação por extração de conteúdo web, para
que o diagnóstico quantitativo venha acompanhado do contexto qualitativo do período.

**3.6** Abrir a base à contribuição do usuário por upload de CSV, sem exigir acesso
ao código nem ao repositório.

---

## 4. Metas e indicadores de sucesso

*Metas 4.8 e 4.9 adicionadas em setembro — TP2.*

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

*Riscos 8.5 a 8.8 adicionados em setembro — TP2.*

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
produziram dados, apenas consultas.

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
fim da sessão. Nenhum upload altera os arquivos do repositório.

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

---

## 10. Arquitetura da solução

*Adicionado em setembro — TP2.*

| Camada | Componente | Responsabilidade |
| --- | --- | --- |
| Coleta | `coleta.py` | APIs do IBGE: indicadores da ODS 4 e malha territorial |
| Coleta | `scraping.py` | Beautiful Soup sobre 4 fontes de conteúdo em educação |
| Texto | `texto.py` | Stopwords, tokenização, menções de UF e classificação temática |
| Dados | `data/raw`, `data/processed` | Camada bruta e camada tratada, ambas versionadas |
| Serviço | `utils.py` | Cache, estado de sessão, índice de prioridade e reporte |
| Interface | `app.py` + `paginas/` | Seis páginas de navegação, filtros e downloads |

A coleta roda fora da aplicação, por decisão de projeto: o painel não depende de rede,
sobe em segundos e pode ser publicado sem credenciais.

---

## 11. Marcos

*Adicionado em setembro — TP2.*

| Marco | Estágio TDSP | Situação |
| --- | --- | --- |
| Project Charter e definição do problema | Business Understanding | Concluído |
| Coleta via API e Data Summary Report | Data Acquisition | Concluído |
| Extração de conteúdo web e corpus textual | Data Acquisition | Concluído |
| Índice de prioridade e interface interativa | Modeling | Concluído |
