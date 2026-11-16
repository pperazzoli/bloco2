# utils.py - camada de dados da aplicacao
# concentra leitura em cache, estado de sessao e os calculos derivados
# criado 21-09-2026
# edited 16-11-2026: a leitura dos arquivos e os calculos sairam daqui e foram para
# nucleo.py, que nao depende de streamlit e por isso tambem serve a api do fastapi.
# Este arquivo passou a ser so a camada de cache e de estado de sessao por cima do nucleo:
# a assinatura de todas as funcoes publicas foi preservada, nenhuma pagina mudou.
# edited 16-11-2026 (TP4): entrou chamar_api, que estava dentro de paginas/servico_api.py.
# Com a segunda pagina cliente da api - a de analise de linguagem - as duas passaram a
# precisar da mesma funcao, e duas copias divergiriam no tratamento de erro.

import io
from datetime import date

import pandas as pd
import requests
import streamlit as st
from wordcloud import WordCloud

import nucleo as nc
import texto as tx

RAIZ = nc.RAIZ
BRUTO = nc.BRUTO
TRATADO = nc.TRATADO
DOCS = nc.DOCS

COLUNAS_INDICADORES = ["indicador_ods", "indicador", "uf", "regiao", "ano", "valor", "unidade", "fonte"]
CORES_REGIAO = {
    "Norte": "#1f77b4", "Nordeste": "#ff7f0e", "Centro-Oeste": "#2ca02c",
    "Sudeste": "#d62728", "Sul": "#9467bd",
}
PALETAS_NUVEM = ["viridis", "plasma", "cividis", "magma", "Blues", "YlGnBu", "copper"]


# ---------------------------------------------------------------- leitura em cache

@st.cache_data(ttl=3600, show_spinner="carregando indicadores")
def carregar_indicadores():
    return nc.ler_indicadores()


@st.cache_data(ttl=3600)
def carregar_fontes():
    return nc.ler_fontes()


@st.cache_data(ttl=3600, show_spinner="carregando noticias")
def carregar_noticias():
    return nc.ler_noticias()


@st.cache_data(ttl=3600)
def carregar_termos():
    return nc.ler_termos()


@st.cache_data(ttl=3600)
def carregar_tabela(nome):
    return nc.ler_tabela(nome)


@st.cache_data(ttl=3600)
def carregar_malha():
    return nc.ler_malha()


@st.cache_data(ttl=600)
def carregar_documento(nome):
    return nc.ler_documento(nome)


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
    return nc.indicadores_disponiveis(dados)


@st.cache_data(show_spinner=False)
def matriz_uf_indicador(dados):
    return nc.matriz_uf_indicador(dados)


@st.cache_data(show_spinner=False)
def regiao_por_uf(dados):
    return nc.regiao_por_uf(dados)


@st.cache_data(show_spinner="recalculando o indice")
def calcular_indice(dados, pesos, metodo):
    # pesos chega como tupla de pares para poder entrar no cache
    return nc.calcular_indice(dados, dict(pesos), metodo)


@st.cache_data(show_spinner=False)
def estatisticas_noticias(noticias):
    return nc.estatisticas_noticias(noticias)


@st.cache_data(show_spinner=False)
def frequencias(conteudos, limite, extras, manter_dominio):
    return tx.contar_termos(list(conteudos), limite=limite, extras=frozenset(extras), manter_dominio=manter_dominio)


@st.cache_data(show_spinner=False)
def contagem_por_coluna(noticias, coluna, nomes):
    return nc.contagem_por_coluna(noticias, coluna, nomes)


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


# ---------------------------------------------------------------- chamada a api

# as rotas de dados respondem em milissegundos; as de linguagem natural podem levar segundos
# na primeira carga do modelo, por isso o prazo e um parametro e nao uma constante.
TEMPO_LIMITE_API = 10


def chamar_api(base, caminho, metodo="GET", parametros=None, corpo=None, tempo_limite=TEMPO_LIMITE_API):
    """Unico ponto de saida para a rede nas paginas. Devolve (ok, resposta_ou_mensagem).

    Nenhuma excecao de rede escapa: a pagina recebe sempre um par, e decide o que mostrar.
    E o que permite a aplicacao continuar util com o servico fora do ar.
    """
    try:
        resposta = requests.request(
            metodo, f"{base.rstrip('/')}{caminho}",
            params=parametros, json=corpo, timeout=tempo_limite,
        )
    except requests.exceptions.RequestException as erro:
        return False, f"{type(erro).__name__}: {erro}"
    try:
        return resposta.ok, {"status": resposta.status_code, "corpo": resposta.json()}
    except ValueError:
        return False, f"resposta HTTP {resposta.status_code} não é JSON"


def detalhe_do_erro(resultado):
    """Extrai a mensagem legivel de uma resposta de erro da api, qualquer que seja a forma."""
    if isinstance(resultado, str):
        return resultado
    corpo = resultado.get("corpo", {})
    detalhe = corpo.get("detail", corpo) if isinstance(corpo, dict) else corpo
    if isinstance(detalhe, dict) and "motivo" in detalhe:
        return f"{detalhe.get('erro', 'erro')} — {detalhe['motivo']}"
    if isinstance(detalhe, list) and detalhe and isinstance(detalhe[0], dict):
        return "; ".join(f"{'.'.join(str(p) for p in d.get('loc', []))}: {d.get('msg', '')}" for d in detalhe)
    return str(detalhe)


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
