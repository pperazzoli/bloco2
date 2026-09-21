# paginas/visao_geral.py - apresentacao do projeto
# edited 21-09-2026: texto herdado do app.py do tp1, acrescido dos indicadores de
# cobertura no topo e do perfil rapido de uf no rodape

import pandas as pd
import plotly.express as px
import streamlit as st

import utils

dados = utils.dados_ativos()
fontes = utils.carregar_fontes()
noticias = utils.carregar_noticias()
estatisticas = utils.estatisticas_noticias(noticias)

st.title("🧭 Bússola ESG Educação")
st.caption("Priorização orientada a dados do investimento social privado em educação básica")

colunas = st.columns(5)
colunas[0].metric("UFs cobertas", f"{dados['uf'].nunique()}/27")
colunas[1].metric("Indicadores da ODS 4", dados["indicador"].nunique())
colunas[2].metric("Observações", len(dados))
colunas[3].metric("Notícias raspadas", estatisticas["noticias"])
colunas[4].metric("Palavras no corpus", f"{estatisticas['palavras']:,}".replace(",", "."))

st.divider()

st.header("Problema de negócio")
st.markdown(
    """
Empresas com agenda ESG investem em educação básica, mas decidem onde aplicar o recurso
por relacionamento, e não por evidência. O dado público existe — INEP e IBGE publicam
indicadores abertos — porém disperso entre microdados e APIs distintas, inacessível a quem
decide. No reporte de sustentabilidade, o impacto é descrito de forma qualitativa, sem
rastreabilidade até a fonte oficial, o que expõe a empresa a risco de *social washing*.

**Solução:** aplicação que ranqueia territórios por prioridade de investimento a partir dos
indicadores oficiais da ODS 4 e gera o reporte ESG com a fonte de cada número registrada.
"""
)

st.divider()

st.header("Objetivos")
st.markdown(
    """
1. Coletar via API os indicadores oficiais de monitoramento da ODS 4
2. Consolidá-los em um Índice de Prioridade de Investimento por território
3. Disponibilizar o ranking em painel interativo
4. Gerar o reporte ESG com rastreabilidade de fonte, ano e URL de cada valor
"""
)

st.subheader("Metas e indicadores de sucesso")
st.dataframe(
    pd.DataFrame(
        [
            ["Cobertura territorial", "% de UFs com índice calculado", "100% (27 UFs)"],
            ["Profundidade do dado", "Indicadores oficiais da ODS 4 integrados", "≥ 6"],
            ["Rastreabilidade", "% de valores com fonte, ano e URL registrados", "100%"],
            ["Atualidade", "Defasagem do dado mais recente exibido", "≤ 2 anos"],
            ["Esforço do usuário", "Tempo para produzir um diagnóstico territorial", "< 5 minutos"],
            ["Reporte ESG", "Tempo para gerar a minuta alinhada aos ODS", "< 1 minuto"],
        ],
        columns=["Meta", "Indicador", "Alvo"],
    ),
    hide_index=True,
    width="stretch",
)

st.divider()

st.header("ODS atendida")
st.markdown(
    """
**ODS 4 — Educação de Qualidade.** A justificativa é direta: os indicadores que alimentam o
índice são os próprios indicadores oficiais de monitoramento da ODS 4, publicados pelo
IBGE como custodiante nacional da Agenda 2030. O projeto atende à ODS 4 de duas formas:
direciona recurso privado para os territórios mais distantes de cumprir suas metas, e torna
visível a distância entre a situação atual e o compromisso do Brasil para 2030.

**ODS secundárias:** 10 (Redução das Desigualdades), por priorizar territórios historicamente
preteridos pelo investimento social; e 17 (Parcerias), por qualificar a relação entre setor
privado e poder público na educação.
"""
)
st.dataframe(
    pd.DataFrame(
        [
            ["4.1", "Concluir o ensino básico com qualidade", "Taxa de conclusão"],
            ["4.2", "Educação na primeira infância", "Participação aos 5 anos"],
            ["4.6", "Alfabetização de jovens e adultos", "Taxa de alfabetização 15+"],
            ["4.a", "Instalações educacionais adequadas e inclusivas", "Infraestrutura das escolas"],
            ["4.c", "Professores qualificados", "Docentes com formação adequada"],
        ],
        columns=["Meta da ODS 4", "Descrição", "Indicador oficial utilizado no projeto"],
    ),
    hide_index=True,
    width="stretch",
)

st.divider()

st.header("Público-alvo")
st.markdown(
    """
**Usuário primário:** analista de Sustentabilidade. Decide onde alocar o orçamento anual em
educação e precisa reportá-lo. Usa planilha e BI, não programa.

**Usuários secundários:** institutos, fundações e ONGs de educação.

**Beneficiários finais:** estudantes da educação básica pública.
"""
)

st.divider()

st.header("Perfil rápido de um território")
st.caption("Atalho para inspecionar uma UF sem sair desta página.")

uf_escolhida = st.selectbox("Unidade da Federação", sorted(dados["uf"].unique()), key="uf_visao_geral")
recorte = dados[dados["uf"] == uf_escolhida].sort_values("valor", ascending=False)
media_nacional = dados.groupby("indicador")["valor"].mean()

perfil = recorte[["indicador_ods", "indicador", "ano", "valor"]].copy()
perfil["media_nacional"] = [round(media_nacional.get(i, 0), 1) for i in perfil["indicador"]]
perfil["diferenca"] = (perfil["valor"] - perfil["media_nacional"]).round(1)

esquerda, direita = st.columns([3, 2])
with esquerda:
    st.dataframe(
        perfil,
        hide_index=True,
        width="stretch",
        column_config={
            "indicador_ods": "Meta",
            "indicador": "Indicador",
            "ano": st.column_config.NumberColumn("Ano", format="%d"),
            "valor": st.column_config.ProgressColumn("Valor (%)", min_value=0, max_value=100, format="%.1f"),
            "media_nacional": st.column_config.NumberColumn("Média BR", format="%.1f"),
            "diferenca": st.column_config.NumberColumn("Diferença", format="%+.1f"),
        },
    )
with direita:
    grafico = px.bar(
        perfil,
        x="diferenca",
        y="indicador_ods",
        orientation="h",
        color=perfil["diferenca"] > 0,
        color_discrete_map={True: "#2ca02c", False: "#d62728"},
        labels={"diferenca": "Diferença para a média nacional (p.p.)", "indicador_ods": ""},
        height=360,
    )
    grafico.update_layout(showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(grafico, width="stretch")

marcada = uf_escolhida in st.session_state.cesta
if st.button(
    f"{'Remover' if marcada else 'Adicionar'} {uf_escolhida} {'da' if marcada else 'à'} cesta de priorização",
    type="secondary" if marcada else "primary",
):
    utils.alternar_cesta(uf_escolhida)
    st.rerun()

st.divider()

st.subheader("Fontes de dados do projeto")
st.dataframe(fontes, hide_index=True, width="stretch")

st.divider()

st.header("Links úteis")
st.markdown(
    """
**Iniciativas e inspiração**
- [Conecta Brasil](https://conectabrasil.org/home) — conecta doadores a projetos sociais
- [Observatório do Terceiro Setor](https://observatorio3setor.org.br/carrossel/lista-conheca-projetos-sociais-de-15-causas-diferentes/) — projetos sociais por causa
- [GIFE](https://gife.org.br/) — panorama do investimento social privado no Brasil
- [Todos Pela Educação](https://todospelaeducacao.org.br/) — monitoramento das metas educacionais
- [QEdu](https://qedu.org.br/) — referência de apresentação de dados educacionais

**Agenda 2030**
- [ONU Brasil — ODS](https://brasil.un.org/pt-br/sdgs)
- [ODS Brasil — IBGE](https://odsbrasil.gov.br/) — indicadores oficiais brasileiros

**Fontes de dados**
- [IBGE — API de Agregados](https://servicodados.ibge.gov.br/api/docs/agregados)
- [IBGE — API de Localidades](https://servicodados.ibge.gov.br/api/docs/localidades)
- [INEP — Microdados](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados)
- [Banco Mundial — WDI](https://datahelpdesk.worldbank.org/knowledgebase/topics/125589)
"""
)
