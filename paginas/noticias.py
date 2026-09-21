# paginas/noticias.py - conteudo raspado da web: estatisticas e nuvem de palavras
# criado 21-09-2026

import pandas as pd
import plotly.express as px
import streamlit as st

import utils

noticias = utils.carregar_noticias()
dados = utils.dados_ativos()

st.title("📰 Notícias e nuvem de palavras")
st.caption(
    "Conteúdo extraído com Beautiful Soup por `scraping.py` e gravado em "
    "`data/raw/noticias_educacao.csv` e `data/raw/noticias_corpus.txt`."
)

robots = utils.carregar_tabela("robots_verificacao.csv")
with st.expander("🤖 Verificação de robots.txt dos sites de origem"):
    if robots.empty:
        st.info("Ainda sem registro. Rode `python scraping.py` para gerar a verificação.")
    else:
        st.markdown(
            "Nenhuma página é baixada antes de consultar o `robots.txt` do host. O intervalo "
            "entre requisições respeita o `Crawl-delay` declarado por cada site."
        )
        st.dataframe(
            robots,
            hide_index=True,
            width="stretch",
            column_config={
                "host": "Host",
                "robots_url": st.column_config.LinkColumn("robots.txt", display_text="abrir"),
                "status_http": st.column_config.NumberColumn("HTTP", format="%d"),
                "politica": "Política aplicada",
                "crawl_delay_s": st.column_config.NumberColumn("Intervalo (s)", format="%.1f"),
                "verificado_em": "Verificado em",
            },
        )

with st.sidebar:
    st.markdown("### Filtros das notícias")
    fontes_escolhidas = st.multiselect(
        "Fontes",
        sorted(noticias["fonte"].unique()),
        default=sorted(noticias["fonte"].unique()),
        key="noticias_fontes",
    )
    temas = sorted({t for linha in noticias["temas_ods4"].fillna("") for t in str(linha).split(";") if t})
    tema_escolhido = st.selectbox("Tema da ODS 4", ["todos"] + temas, key="noticias_tema")
    busca = st.text_input("Buscar no texto", key="noticias_busca", placeholder="ex.: fundeb, creche, evasão")

recorte = noticias[noticias["fonte"].isin(fontes_escolhidas)]
if tema_escolhido != "todos":
    recorte = recorte[recorte["temas_ods4"].fillna("").str.contains(tema_escolhido, regex=False)]
if busca.strip():
    alvo = recorte["conteudo"].map(lambda t: busca.strip().lower() in str(t).lower())
    recorte = recorte[alvo]

if recorte.empty:
    st.warning("Nenhuma notícia atende aos filtros. Relaxe a busca ou reative fontes.")
    st.stop()

estatisticas = utils.estatisticas_noticias(recorte)
colunas = st.columns(5)
colunas[0].metric("Notícias", estatisticas["noticias"])
colunas[1].metric("Fontes", estatisticas["fontes"])
colunas[2].metric("Palavras", f"{estatisticas['palavras']:,}".replace(",", "."))
colunas[3].metric("Média por matéria", estatisticas["media_palavras"])
colunas[4].metric(
    "Período",
    f"{estatisticas['primeira']:%d/%m/%y}" if pd.notna(estatisticas["primeira"]) else "-",
    f"até {estatisticas['ultima']:%d/%m/%y}" if pd.notna(estatisticas["ultima"]) else None,
)

aba_nuvem, aba_estatisticas, aba_territorio, aba_lista = st.tabs(
    ["Nuvem de palavras", "Estatísticas", "Territórios citados", "Lista de notícias"]
)

with aba_nuvem:
    controles = st.columns(4)
    max_palavras = controles[0].slider("Palavras na nuvem", 30, 250, 120, 10, key="nuvem_max")
    paleta = controles[1].selectbox("Paleta", utils.PALETAS_NUVEM, key="nuvem_paleta")
    campo = controles[2].selectbox("Campo analisado", ["título + resumo + texto", "só título"], key="nuvem_campo")
    manter = controles[3].toggle(
        "Manter termos genéricos",
        key="nuvem_dominio",
        help="Quando desligado, remove palavras como educação, escola e aluno, que aparecem em quase toda matéria.",
    )

    extras = st.text_input(
        "Stopwords adicionais (separadas por vírgula)",
        key="nuvem_extras",
        placeholder="ex.: exame, edital, programa",
    )
    st.session_state.stopwords_extras = [p.strip() for p in extras.split(",") if p.strip()]

    conteudos = recorte["titulo"] if campo == "só título" else recorte["conteudo"]
    pares = utils.frequencias(
        tuple(conteudos),
        limite=max_palavras,
        extras=tuple(st.session_state.stopwords_extras),
        manter_dominio=manter,
    )

    if not pares:
        st.info("Nenhum termo sobrou depois das stopwords.")
    else:
        imagem = utils.nuvem_png(tuple(pares), paleta=paleta, max_palavras=max_palavras)
        st.image(imagem, width="stretch")
        baixar = st.columns(2)
        baixar[0].download_button(
            "⬇️ Nuvem em PNG", data=imagem, file_name="nuvem_palavras.png",
            mime="image/png", width="stretch",
        )
        baixar[1].download_button(
            "⬇️ Frequências em CSV",
            data=utils.para_csv(pd.DataFrame(pares, columns=["termo", "frequencia"])),
            file_name="frequencia_termos.csv",
            mime="text/csv",
            width="stretch",
        )

        st.subheader("Termos mais frequentes")
        top = pd.DataFrame(pares[:25], columns=["termo", "frequencia"])
        barras = px.bar(
            top.sort_values("frequencia"), x="frequencia", y="termo", orientation="h", height=560
        )
        barras.update_layout(margin=dict(l=0, r=0, t=10, b=0), yaxis_title="")
        st.plotly_chart(barras, width="stretch")

with aba_estatisticas:
    esquerda, direita = st.columns(2)

    por_fonte = recorte["fonte"].value_counts().reset_index()
    por_fonte.columns = ["fonte", "noticias"]
    with esquerda:
        st.markdown("**Notícias por fonte**")
        rosca = px.pie(por_fonte, names="fonte", values="noticias", hole=0.45, height=360)
        rosca.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(rosca, width="stretch")
        st.dataframe(por_fonte, hide_index=True, width="stretch")

    por_mes = recorte.groupby("mes").size().reset_index(name="noticias").sort_values("mes")
    with direita:
        st.markdown("**Notícias por mês de publicação**")
        linha = px.line(por_mes, x="mes", y="noticias", markers=True, height=360)
        linha.update_layout(margin=dict(l=0, r=0, t=10, b=0), xaxis_title="", yaxis_title="")
        st.plotly_chart(linha, width="stretch")
        st.dataframe(por_mes, hide_index=True, width="stretch")

    st.markdown("**Cobertura por tema da ODS 4**")
    por_tema = utils.contagem_por_coluna(recorte, "temas_ods4", ["tema_ods4", "noticias"])
    barras_tema = px.bar(por_tema.sort_values("noticias"), x="noticias", y="tema_ods4",
                         orientation="h", height=380)
    barras_tema.update_layout(margin=dict(l=0, r=0, t=10, b=0), yaxis_title="")
    st.plotly_chart(barras_tema, width="stretch")

    st.markdown("**Tamanho das matérias**")
    histograma = px.histogram(recorte, x="n_palavras", color="fonte", nbins=25, height=340)
    histograma.update_layout(margin=dict(l=0, r=0, t=10, b=0), xaxis_title="palavras por matéria")
    st.plotly_chart(histograma, width="stretch")

    st.download_button(
        "⬇️ Estatísticas por tema em CSV",
        data=utils.para_csv(por_tema),
        file_name="noticias_por_tema.csv",
        mime="text/csv",
    )

with aba_territorio:
    st.markdown(
        "Cruzamento entre a **atenção da imprensa** e a **carência medida**: territórios "
        "com índice alto e pouca menção são os candidatos menos disputados."
    )
    por_uf = utils.contagem_por_coluna(recorte, "ufs_citadas", ["uf", "mencoes"])
    if por_uf.empty:
        st.info("Nenhuma UF foi citada nas notícias filtradas.")
    else:
        media_uf = dados.groupby("uf")["valor"].mean().reset_index(name="media_indicadores")
        cruzamento = media_uf.merge(por_uf, on="uf", how="left").fillna({"mencoes": 0})
        cruzamento["mencoes"] = cruzamento["mencoes"].astype(int)
        cruzamento["regiao"] = cruzamento["uf"].map(utils.regiao_por_uf(dados))

        dispersao = px.scatter(
            cruzamento,
            x="media_indicadores",
            y="mencoes",
            color="regiao",
            color_discrete_map=utils.CORES_REGIAO,
            text="uf",
            labels={"media_indicadores": "Média dos indicadores da ODS 4 (%)", "mencoes": "Menções na imprensa"},
            height=520,
        )
        dispersao.update_traces(textposition="top center")
        dispersao.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(dispersao, width="stretch")

        st.dataframe(
            cruzamento.sort_values("mencoes", ascending=False),
            hide_index=True,
            width="stretch",
            height=340,
        )

with aba_lista:
    st.dataframe(
        recorte[["data", "fonte", "titulo", "editoria", "ufs_citadas", "n_palavras", "url"]],
        hide_index=True,
        width="stretch",
        height=520,
        column_config={
            "data": st.column_config.DateColumn("data", format="DD/MM/YYYY"),
            "url": st.column_config.LinkColumn("matéria", display_text="abrir"),
        },
    )
    st.download_button(
        "⬇️ Notícias filtradas em CSV",
        data=utils.para_csv(recorte.drop(columns=["conteudo"])),
        file_name="noticias_filtradas.csv",
        mime="text/csv",
    )

    st.subheader("Ler uma matéria")
    escolhida = st.selectbox("Título", recorte["titulo"].tolist(), key="noticia_escolhida")
    materia = recorte[recorte["titulo"] == escolhida].iloc[0]
    st.markdown(f"**{materia['fonte']}** · {materia['data']:%d/%m/%Y} · [link]({materia['url']})")
    st.write(materia["texto"][:3000] or materia["resumo"])
