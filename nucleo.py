# nucleo.py - nucleo de dados do projeto, sem dependencia de streamlit
# criado 16-11-2026 (TP3)
#
# Por que este arquivo existe: com a entrada da API do FastAPI passaram a existir dois
# consumidores dos mesmos dados - a aplicacao Streamlit e o servico HTTP. O indice de
# prioridade nao pode ser calculado por dois codigos diferentes, senao o numero que a API
# devolve e o numero que o painel mostra podem divergir, e a rastreabilidade prometida no
# Project Charter cai. Entao a leitura dos arquivos e os calculos vivem aqui, em pandas
# puro, e cada consumidor por cima: utils.py embrulha tudo em cache do Streamlit, api.py
# embrulha em lru_cache.

import json
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).parent
BRUTO = RAIZ / "data" / "raw"
TRATADO = RAIZ / "data" / "processed"

DOCS = {
    "Project Charter": RAIZ / "1_business_understanding" / "project_charter.md",
    "Data Summary Report": RAIZ / "2_data_acquisition" / "data_summary_report.md",
    "Plano de uso de LLM": RAIZ / "3_modeling" / "plano_llm.md",
    "Referência da API": RAIZ / "4_deployment" / "api_reference.md",
}

METODOS_INDICE = ["min-max entre UFs", "distancia de 100%"]


# ---------------------------------------------------------------- leitura dos arquivos

def ler_indicadores():
    dados = pd.read_csv(TRATADO / "ods4_uf.csv")
    dados["origem"] = "IBGE"
    return dados


def ler_fontes():
    return pd.read_csv(TRATADO / "fontes.csv")


def ler_noticias():
    noticias = pd.read_csv(BRUTO / "noticias_educacao.csv").fillna({"texto": "", "resumo": "", "editoria": ""})
    noticias["data"] = pd.to_datetime(noticias["data"], errors="coerce")
    noticias["mes"] = noticias["data"].dt.to_period("M").astype(str)
    noticias["conteudo"] = noticias["titulo"] + " " + noticias["resumo"] + " " + noticias["texto"]
    return noticias.sort_values("data", ascending=False).reset_index(drop=True)


def ler_termos():
    return pd.read_csv(TRATADO / "noticias_termos.csv")


def ler_tabela(nome):
    caminho = TRATADO / nome
    return pd.read_csv(caminho) if caminho.exists() else pd.DataFrame()


def ler_malha():
    caminho = BRUTO / "malha_uf.geojson"
    if not caminho.exists():
        return None
    return json.loads(caminho.read_text(encoding="utf-8"))


def ler_documento(nome):
    caminho = DOCS.get(nome)
    if caminho is None or not caminho.exists():
        return f"documento nao encontrado: {nome}"
    return caminho.read_text(encoding="utf-8")


# ---------------------------------------------------------------- calculos

def indicadores_disponiveis(dados):
    return sorted(dados["indicador"].unique())


def matriz_uf_indicador(dados):
    # indexada so por uf: se o upload trouxer outra regiao, a uf nao se parte em duas
    return dados.pivot_table(index="uf", columns="indicador", values="valor", aggfunc="mean")


def regiao_por_uf(dados):
    # a regiao vinda do ibge tem precedencia sobre a que veio no upload
    ordenado = dados.assign(ordem=(dados["origem"] != "IBGE").astype(int))
    return ordenado.sort_values("ordem").drop_duplicates("uf").set_index("uf")["regiao"]


def calcular_indice(dados, pesos, metodo):
    # pesos: dicionario indicador -> peso. peso zero exclui o indicador do calculo.
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


def estatisticas_noticias(noticias):
    return {
        "noticias": len(noticias),
        "fontes": noticias["fonte"].nunique(),
        "palavras": int(noticias["n_palavras"].sum()),
        "media_palavras": int(noticias["n_palavras"].mean()) if len(noticias) else 0,
        "primeira": noticias["data"].min(),
        "ultima": noticias["data"].max(),
    }


def contagem_por_coluna(noticias, coluna, nomes):
    # as colunas ufs_citadas e temas_ods4 guardam listas separadas por ponto e virgula
    contagem = {}
    for celula in noticias[coluna].fillna(""):
        for item in str(celula).split(";"):
            if item:
                contagem[item] = contagem.get(item, 0) + 1
    return pd.DataFrame(sorted(contagem.items(), key=lambda p: -p[1]), columns=nomes)
