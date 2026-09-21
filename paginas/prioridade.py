# paginas/prioridade.py - indice de prioridade de investimento e reporte esg
# criado 21-09-2026

import plotly.express as px
import streamlit as st

import utils

dados = utils.dados_ativos()
fontes = utils.carregar_fontes()
noticias_por_uf = utils.carregar_tabela("noticias_por_uf.csv")

st.title("🎯 Índice de Prioridade de Investimento")
st.markdown(
    "O índice mede a **carência** do território nos indicadores da ODS 4: quanto maior, "
    "mais distante o território está da meta. Os pesos ficam à vista e sob controle do "
    "usuário — o Project Charter registra que um índice composto não pode embutir juízo "
    "de valor implícito."
)

indicadores = utils.indicadores_disponiveis(dados)
for nome in indicadores:
    st.session_state.pesos.setdefault(nome, 1.0)

with st.sidebar:
    st.markdown("### Pesos do índice")
    metodo = st.radio(
        "Normalização",
        ["min-max entre UFs", "distancia de 100%"],
        key="metodo_indice",
        help="min-max compara as UFs entre si; distância de 100% compara cada UF com a meta plena.",
    )
    for nome in indicadores:
        rotulo = nome if len(nome) <= 42 else nome[:39] + "..."
        st.session_state.pesos[nome] = st.slider(
            rotulo, 0.0, 3.0, float(st.session_state.pesos[nome]), 0.5,
            key=f"peso_{nome}", help=nome,
        )
    if st.button("Restaurar pesos iguais", width="stretch"):
        st.session_state.pesos = {nome: 1.0 for nome in indicadores}
        utils.registrar("restaurou os pesos")
        st.rerun()

pesos = {n: p for n, p in st.session_state.pesos.items() if n in indicadores}
ranking = utils.calcular_indice(dados, tuple(sorted(pesos.items())), metodo)

if ranking.empty:
    st.warning("Todos os pesos estão zerados. Suba ao menos um indicador na barra lateral.")
    st.stop()

ativos = [n for n, p in pesos.items() if p > 0]
colunas = st.columns(4)
colunas[0].metric("Indicadores no índice", f"{len(ativos)}/{len(indicadores)}")
colunas[1].metric("Maior prioridade", ranking.iloc[0]["uf"], f"{ranking.iloc[0]['indice_prioridade']:.1f}")
colunas[2].metric("Menor prioridade", ranking.iloc[-1]["uf"], f"{ranking.iloc[-1]['indice_prioridade']:.1f}")
colunas[3].metric("Amplitude do índice", f"{ranking['indice_prioridade'].max() - ranking['indice_prioridade'].min():.1f}")

quantos = st.slider("Quantas UFs exibir no gráfico", 5, len(ranking), min(15, len(ranking)), key="top_ranking")
topo = ranking.head(quantos)

grafico = px.bar(
    topo,
    x="indice_prioridade",
    y="uf",
    orientation="h",
    color="regiao",
    color_discrete_map=utils.CORES_REGIAO,
    labels={"indice_prioridade": "Índice de prioridade (0 a 100)", "uf": "", "regiao": "Região"},
    height=max(400, 26 * quantos),
    text="indice_prioridade",
)
grafico.update_layout(margin=dict(l=0, r=0, t=10, b=0), yaxis=dict(autorange="reversed"))
st.plotly_chart(grafico, width="stretch")

st.subheader("Ranking completo")
colunas_visiveis = ["posicao", "uf", "regiao", "indice_prioridade"] + ativos
st.dataframe(
    ranking[colunas_visiveis],
    hide_index=True,
    width="stretch",
    height=440,
    column_config={
        "posicao": st.column_config.NumberColumn("#", format="%d"),
        "indice_prioridade": st.column_config.ProgressColumn(
            "índice", min_value=0, max_value=100, format="%.1f"
        ),
    },
)

st.divider()

st.subheader("Cesta de priorização")
st.caption("A cesta atravessa as páginas e é o que entra no reporte ESG.")

escolhidas = st.multiselect(
    "UFs selecionadas",
    ranking["uf"].tolist(),
    default=st.session_state.cesta,
    key="cesta_prioridade",
)
if escolhidas != st.session_state.cesta:
    st.session_state.cesta = escolhidas
    utils.registrar(f"cesta agora com {len(escolhidas)} UF(s)")
    st.rerun()

atalho = st.columns(3)
if atalho[0].button("Levar o top 5 para a cesta", width="stretch"):
    st.session_state.cesta = ranking.head(5)["uf"].tolist()
    utils.registrar("cesta preenchida com o top 5")
    st.rerun()
if atalho[1].button("Levar o top 10 para a cesta", width="stretch"):
    st.session_state.cesta = ranking.head(10)["uf"].tolist()
    utils.registrar("cesta preenchida com o top 10")
    st.rerun()
if atalho[2].button("Esvaziar", width="stretch"):
    st.session_state.cesta = []
    utils.registrar("esvaziou a cesta")
    st.rerun()

if st.session_state.cesta:
    selecao = ranking[ranking["uf"].isin(st.session_state.cesta)]
    st.dataframe(selecao[colunas_visiveis], hide_index=True, width="stretch")

    perfil = selecao.melt(
        id_vars=["uf"], value_vars=ativos, var_name="indicador", value_name="valor"
    )
    radar = px.line_polar(
        perfil, r="valor", theta="indicador", color="uf", line_close=True, range_r=[0, 100], height=520
    )
    radar.update_layout(margin=dict(l=40, r=40, t=30, b=30), legend_title="UF")
    st.plotly_chart(radar, width="stretch")
    st.caption("No radar o valor é o indicador bruto: quanto menor a área, maior a carência.")

st.divider()

st.subheader("Saídas")
saidas = st.columns(2)
saidas[0].download_button(
    "⬇️ Ranking completo em CSV",
    data=utils.para_csv(ranking[colunas_visiveis]),
    file_name="indice_prioridade.csv",
    mime="text/csv",
    width="stretch",
)
reporte = utils.gerar_reporte(
    ranking, st.session_state.cesta, pesos, metodo, noticias_por_uf, fontes
)
saidas[1].download_button(
    "⬇️ Minuta do reporte ESG (Markdown)",
    data=reporte.encode("utf-8"),
    file_name="reporte_esg.md",
    mime="text/markdown",
    width="stretch",
)

with st.expander("Prévia do reporte ESG"):
    st.markdown(reporte)
