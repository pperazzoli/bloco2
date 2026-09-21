# paginas/indicadores.py - exploracao interativa dos indicadores da ods 4
# criado 21-09-2026

import pandas as pd
import plotly.express as px
import streamlit as st

import utils

dados = utils.dados_ativos()
malha = utils.carregar_malha()

st.title("📊 Indicadores da ODS 4")
st.caption(
    f"{len(dados)} observações · {dados['indicador'].nunique()} indicadores · "
    f"{dados['uf'].nunique()} UFs · coleta pela API do IBGE (`coleta.py`)"
)

with st.sidebar:
    st.markdown("### Filtros")
    regioes = st.multiselect(
        "Regiões",
        sorted(dados["regiao"].unique()),
        default=sorted(dados["regiao"].unique()),
        key="filtro_regioes",
    )
    indicador = st.selectbox(
        "Indicador",
        utils.indicadores_disponiveis(dados),
        key="filtro_indicador",
    )
    ordem = st.radio("Ordenar por", ["Menor valor primeiro", "Maior valor primeiro"], key="filtro_ordem")
    apenas_cesta = st.toggle("Mostrar só a cesta", key="filtro_cesta")

recorte = dados[(dados["indicador"] == indicador) & (dados["regiao"].isin(regioes))]

if recorte.empty:
    st.warning("Nenhum dado para os filtros escolhidos. Amplie a seleção de regiões.")
    st.stop()

piso, teto = float(recorte["valor"].min()), float(recorte["valor"].max())
faixa = st.slider(
    "Faixa de valor (%)",
    min_value=round(piso, 1),
    max_value=round(teto, 1),
    value=(round(piso, 1), round(teto, 1)),
    step=0.1,
    key="filtro_faixa",
)
recorte = recorte[recorte["valor"].between(*faixa)]
if apenas_cesta and st.session_state.cesta:
    recorte = recorte[recorte["uf"].isin(st.session_state.cesta)]
recorte = recorte.sort_values("valor", ascending=ordem == "Menor valor primeiro")

if recorte.empty:
    st.warning("Nenhum dado sobrou depois dos filtros.")
    st.stop()

media = recorte["valor"].mean()
colunas = st.columns(4)
colunas[0].metric("UFs exibidas", len(recorte))
colunas[1].metric("Média do recorte", f"{media:.1f}%")
colunas[2].metric("Pior UF", f"{recorte['valor'].min():.1f}%", recorte.loc[recorte['valor'].idxmin(), "uf"])
colunas[3].metric("Melhor UF", f"{recorte['valor'].max():.1f}%", recorte.loc[recorte['valor'].idxmax(), "uf"])

aba_grafico, aba_mapa, aba_tabela, aba_comparar = st.tabs(
    ["Ranking", "Mapa", "Tabela", "Comparar indicadores"]
)

with aba_grafico:
    mostrar_media = st.checkbox("Marcar a média do recorte", value=True, key="grafico_media")
    grafico = px.bar(
        recorte,
        x="valor",
        y="uf",
        orientation="h",
        color="regiao",
        color_discrete_map=utils.CORES_REGIAO,
        labels={"valor": f"% · {int(recorte['ano'].max())}", "uf": "", "regiao": "Região"},
        height=max(420, 18 * len(recorte)),
        hover_data=["indicador_ods", "ano", "fonte"],
    )
    if mostrar_media:
        grafico.add_vline(x=media, line_dash="dash", line_color="#555",
                          annotation_text=f"média {media:.1f}%")
    grafico.update_layout(margin=dict(l=0, r=0, t=10, b=0), yaxis=dict(autorange="reversed"))
    st.plotly_chart(grafico, width="stretch")

with aba_mapa:
    if malha is None:
        st.info("Malha territorial ausente. Rode `python coleta.py` para baixá-la.")
    elif "cod_uf" not in recorte.columns:
        st.info("O recorte atual nao traz o codigo da UF, necessario para o mapa.")
    else:
        # o geojson do ibge guarda o codigo como texto, o csv como inteiro
        mapeavel = recorte.copy()
        mapeavel["cod_uf"] = pd.to_numeric(mapeavel["cod_uf"], errors="coerce")
        mapeavel = mapeavel.dropna(subset=["cod_uf"])
        mapeavel["cod_uf"] = mapeavel["cod_uf"].astype(int).astype(str)
        mapa = px.choropleth(
            mapeavel,
            geojson=malha,
            locations="cod_uf",
            featureidkey="properties.codarea",
            color="valor",
            color_continuous_scale="RdYlGn",
            hover_name="uf",
            hover_data={"cod_uf": False, "valor": ":.1f", "regiao": True},
            labels={"valor": "%"},
        )
        mapa.update_geos(fitbounds="locations", visible=False)
        mapa.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=520)
        st.plotly_chart(mapa, width="stretch")
        st.caption("Vermelho indica maior carência no indicador selecionado.")

with aba_tabela:
    st.dataframe(
        recorte[["uf", "regiao", "indicador_ods", "ano", "valor", "unidade", "fonte"]],
        hide_index=True,
        width="stretch",
        height=460,
        column_config={
            "valor": st.column_config.ProgressColumn("valor", min_value=0, max_value=100, format="%.1f"),
            "ano": st.column_config.NumberColumn("ano", format="%d"),
        },
    )
    st.download_button(
        "⬇️ Baixar este recorte em CSV",
        data=utils.para_csv(recorte),
        file_name=f"recorte_{indicador[:30].replace(' ', '_').lower()}.csv",
        mime="text/csv",
    )

with aba_comparar:
    disponiveis = utils.indicadores_disponiveis(dados)
    eixo_x = st.selectbox("Eixo X", disponiveis, index=0, key="comparar_x")
    eixo_y = st.selectbox("Eixo Y", disponiveis, index=min(1, len(disponiveis) - 1), key="comparar_y")
    matriz = utils.matriz_uf_indicador(dados[dados["regiao"].isin(regioes)]).reset_index()
    matriz["regiao"] = matriz["uf"].map(utils.regiao_por_uf(dados))
    if eixo_x in matriz.columns and eixo_y in matriz.columns:
        dispersao = px.scatter(
            matriz,
            x=eixo_x,
            y=eixo_y,
            color="regiao",
            color_discrete_map=utils.CORES_REGIAO,
            text="uf",
            height=520,
        )
        dispersao.update_traces(textposition="top center")
        dispersao.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(dispersao, width="stretch")
        correlacao = matriz[[eixo_x, eixo_y]].corr().iloc[0, 1]
        st.caption(f"Correlação de Pearson entre os dois indicadores: **{correlacao:.2f}**")
    else:
        st.info("Escolha dois indicadores presentes no recorte.")

st.divider()

st.subheader("Levar territórios para a cesta")
escolhidas = st.multiselect(
    "UFs da cesta de priorização",
    sorted(dados["uf"].unique()),
    default=st.session_state.cesta,
    key="cesta_indicadores",
)
if escolhidas != st.session_state.cesta:
    st.session_state.cesta = escolhidas
    utils.registrar(f"cesta agora com {len(escolhidas)} UF(s)")
    st.rerun()
