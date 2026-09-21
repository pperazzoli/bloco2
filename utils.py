# utils.py - camada de dados da aplicacao
# concentra leitura em cache, estado de sessao e os calculos derivados
# criado 21-09-2026

import io
import json
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from wordcloud import WordCloud

import texto as tx

RAIZ = Path(__file__).parent
BRUTO = RAIZ / "data" / "raw"
TRATADO = RAIZ / "data" / "processed"
DOCS = {
    "Project Charter": RAIZ / "1_business_understanding" / "project_charter.md",
    "Data Summary Report": RAIZ / "2_data_acquisition" / "data_summary_report.md",
}

COLUNAS_INDICADORES = ["indicador_ods", "indicador", "uf", "regiao", "ano", "valor", "unidade", "fonte"]
CORES_REGIAO = {
    "Norte": "#1f77b4", "Nordeste": "#ff7f0e", "Centro-Oeste": "#2ca02c",
    "Sudeste": "#d62728", "Sul": "#9467bd",
}
PALETAS_NUVEM = ["viridis", "plasma", "cividis", "magma", "Blues", "YlGnBu", "copper"]


# ---------------------------------------------------------------- leitura em cache

@st.cache_data(ttl=3600, show_spinner="carregando indicadores")
def carregar_indicadores():
    dados = pd.read_csv(TRATADO / "ods4_uf.csv")
    dados["origem"] = "IBGE"
    return dados


@st.cache_data(ttl=3600)
def carregar_fontes():
    return pd.read_csv(TRATADO / "fontes.csv")


@st.cache_data(ttl=3600, show_spinner="carregando noticias")
def carregar_noticias():
    noticias = pd.read_csv(BRUTO / "noticias_educacao.csv").fillna({"texto": "", "resumo": "", "editoria": ""})
    noticias["data"] = pd.to_datetime(noticias["data"], errors="coerce")
    noticias["mes"] = noticias["data"].dt.to_period("M").astype(str)
    noticias["conteudo"] = noticias["titulo"] + " " + noticias["resumo"] + " " + noticias["texto"]
    return noticias.sort_values("data", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=3600)
def carregar_termos():
    return pd.read_csv(TRATADO / "noticias_termos.csv")


@st.cache_data(ttl=3600)
def carregar_tabela(nome):
    caminho = TRATADO / nome
    return pd.read_csv(caminho) if caminho.exists() else pd.DataFrame()


@st.cache_data(ttl=3600)
def carregar_malha():
    caminho = BRUTO / "malha_uf.geojson"
    if not caminho.exists():
        return None
    return json.loads(caminho.read_text(encoding="utf-8"))


@st.cache_data(ttl=600)
def carregar_documento(nome):
    caminho = DOCS.get(nome)
    if caminho is None or not caminho.exists():
        return f"documento nao encontrado: {nome}"
    return caminho.read_text(encoding="utf-8")


# ---------------------------------------------------------------- estado de sessao

PADROES = {
    "cesta": [],            # ufs marcadas pelo usuario, viajam entre as paginas
    "pesos": {},            # peso de cada indicador no indice de prioridade
    "metodo_indice": "min-max entre UFs",
    "dados_extras": None,   # csv enviado pelo usuario e incorporado aos indicadores
    "stopwords_extras": [],
    "historico": [],
}


def iniciar_estado():
    for chave, valor in PADROES.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor.copy() if isinstance(valor, (list, dict)) else valor


def registrar(acao):
    st.session_state.historico.append(f"{pd.Timestamp.now():%H:%M:%S} · {acao}")
    st.session_state.historico = st.session_state.historico[-30:]


def alternar_cesta(uf):
    if uf in st.session_state.cesta:
        st.session_state.cesta.remove(uf)
        registrar(f"removeu {uf} da cesta")
    else:
        st.session_state.cesta.append(uf)
        registrar(f"adicionou {uf} a cesta")


def dados_ativos():
    # indicadores oficiais mais o que o usuario enviou nesta sessao
    base = carregar_indicadores()
    extras = st.session_state.get("dados_extras")
    if extras is None or extras.empty:
        return base
    return pd.concat([base, extras], ignore_index=True)


# ---------------------------------------------------------------- calculos

@st.cache_data(show_spinner=False)
def indicadores_disponiveis(dados):
    return sorted(dados["indicador"].unique())


@st.cache_data(show_spinner=False)
def matriz_uf_indicador(dados):
    # indexada so por uf: se o upload trouxer outra regiao, a uf nao se parte em duas
    return dados.pivot_table(index="uf", columns="indicador", values="valor", aggfunc="mean")


@st.cache_data(show_spinner=False)
def regiao_por_uf(dados):
    # a regiao vinda do ibge tem precedencia sobre a que veio no upload
    ordenado = dados.assign(ordem=(dados["origem"] != "IBGE").astype(int))
    return ordenado.sort_values("ordem").drop_duplicates("uf").set_index("uf")["regiao"]


@st.cache_data(show_spinner="recalculando o indice")
def calcular_indice(dados, pesos, metodo):
    # pesos chega como tupla de pares para poder entrar no cache
    matriz = matriz_uf_indicador(dados)
    pesos = dict(pesos)
    carencia = pd.DataFrame(index=matriz.index)

    for coluna in matriz.columns:
        serie = matriz[coluna]
        if metodo == "distancia de 100%":
            normalizada = (100 - serie) / 100
        else:
            amplitude = serie.max() - serie.min()
            normalizada = (serie.max() - serie) / amplitude if amplitude else serie * 0
        carencia[coluna] = normalizada.clip(0, 1)

    ativos = {c: pesos.get(c, 1.0) for c in matriz.columns if pesos.get(c, 1.0) > 0}
    if not ativos:
        return pd.DataFrame()

    # media ponderada ignorando buracos: uma uf sem certo indicador nao zera o indice
    colunas = list(ativos)
    peso = pd.Series(ativos)
    numerador = (carencia[colunas].fillna(0) * peso).sum(axis=1)
    denominador = (carencia[colunas].notna() * peso).sum(axis=1)
    indice = (numerador / denominador.replace(0, pd.NA) * 100).astype(float)

    resultado = matriz.copy()
    resultado["indice_prioridade"] = indice.round(1)
    resultado = resultado.dropna(subset=["indice_prioridade"]).reset_index()
    resultado.insert(1, "regiao", resultado["uf"].map(regiao_por_uf(dados)))
    resultado = resultado.sort_values("indice_prioridade", ascending=False)
    resultado.insert(0, "posicao", range(1, len(resultado) + 1))
    return resultado.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def estatisticas_noticias(noticias):
    return {
        "noticias": len(noticias),
        "fontes": noticias["fonte"].nunique(),
        "palavras": int(noticias["n_palavras"].sum()),
        "media_palavras": int(noticias["n_palavras"].mean()) if len(noticias) else 0,
        "primeira": noticias["data"].min(),
        "ultima": noticias["data"].max(),
    }


@st.cache_data(show_spinner=False)
def frequencias(conteudos, limite, extras, manter_dominio):
    return tx.contar_termos(list(conteudos), limite=limite, extras=frozenset(extras), manter_dominio=manter_dominio)


@st.cache_data(show_spinner=False)
def contagem_por_coluna(noticias, coluna, nomes):
    contagem = {}
    for celula in noticias[coluna].fillna(""):
        for item in str(celula).split(";"):
            if item:
                contagem[item] = contagem.get(item, 0) + 1
    tabela = pd.DataFrame(sorted(contagem.items(), key=lambda p: -p[1]), columns=nomes)
    return tabela


# ---------------------------------------------------------------- nuvem de palavras

@st.cache_resource(show_spinner=False)
def gerador_de_nuvem(largura, altura, paleta, max_palavras):
    # objeto reaproveitado entre execucoes, por isso cache_resource e nao cache_data
    return WordCloud(
        width=largura,
        height=altura,
        background_color="white",
        colormap=paleta,
        max_words=max_palavras,
        prefer_horizontal=0.9,
        relative_scaling=0.4,
        collocations=False,
    )


@st.cache_data(show_spinner="desenhando a nuvem")
def nuvem_png(pares, largura=1000, altura=500, paleta="viridis", max_palavras=120):
    if not pares:
        return None
    nuvem = gerador_de_nuvem(largura, altura, paleta, max_palavras)
    imagem = nuvem.generate_from_frequencies(dict(pares)).to_image()
    memoria = io.BytesIO()
    imagem.save(memoria, format="PNG")
    return memoria.getvalue()


# ---------------------------------------------------------------- saidas

def para_csv(tabela):
    return tabela.to_csv(index=False).encode("utf-8")


def gerar_reporte(ranking, cesta, pesos, metodo, noticias_por_uf, fontes):
    hoje = date.today().isoformat()
    linhas = [
        "# Reporte ESG — Bússola ESG Educação",
        "",
        f"**Gerado em:** {hoje} · **Método de normalização:** {metodo}",
        "",
        "## 1. Método",
        "",
        "O Índice de Prioridade de Investimento mede a carência do território nos indicadores",
        "oficiais de monitoramento da ODS 4. Quanto maior o índice, maior a distância entre a",
        "situação do território e a meta. Os pesos aplicados nesta execução foram:",
        "",
        "| Indicador da ODS 4 | Peso |",
        "| --- | --- |",
    ]
    for indicador, peso in sorted(pesos.items()):
        linhas.append(f"| {indicador} | {peso:g} |")

    linhas += ["", "## 2. Territórios priorizados", ""]
    if cesta:
        linhas += ["| Posição | UF | Região | Índice | Notícias que citam a UF |", "| --- | --- | --- | --- | --- |"]
        mencoes = dict(zip(noticias_por_uf.get("uf", []), noticias_por_uf.get("mencoes", [])))
        for _, linha in ranking[ranking["uf"].isin(cesta)].iterrows():
            linhas.append(
                f"| {linha['posicao']} | {linha['uf']} | {linha['regiao']} | "
                f"{linha['indice_prioridade']} | {mencoes.get(linha['uf'], 0)} |"
            )
    else:
        linhas.append("_Nenhuma UF foi selecionada na cesta de priorização._")

    linhas += ["", "## 3. Rastreabilidade", "", "Todo valor citado vem das fontes abaixo:", ""]
    for _, fonte in fontes.iterrows():
        linhas.append(f"- **{fonte['fonte']}** — {fonte['objetivo_de_uso']} (status: {fonte['status']})")

    linhas += [
        "",
        "## 4. Ressalva",
        "",
        "O índice é medida de prioridade de investimento, nunca de mérito do território.",
        "Os pesos são escolha explícita de quem gerou este reporte e estão declarados na seção 1.",
        "",
    ]
    return "\n".join(linhas)
