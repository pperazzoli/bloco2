# api.py - servico HTTP do projeto, construido com FastAPI
# roda separado da aplicacao streamlit: "uvicorn api:app --reload" ou "python api.py"
# criado 16-11-2026 (TP3)
#
# A API nao tem logica propria: le os mesmos arquivos de data/ e chama as mesmas funcoes de
# nucleo.py que a aplicacao Streamlit chama. E deliberado - o indice que esta API devolve e,
# por construcao, o mesmo indice que o painel mostra.
#
# Documentacao interativa, gerada pelo proprio FastAPI a partir deste arquivo:
#   http://127.0.0.1:8000/docs      (Swagger UI)
#   http://127.0.0.1:8000/redoc     (ReDoc)
# A referencia escrita das rotas esta em 4_deployment/api_reference.md.

import json
from datetime import datetime
from functools import lru_cache

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

import nucleo as nc

app = FastAPI(
    title="Bússola ESG Educação — API",
    version="1.0.0",
    description=(
        "Serviço de consulta aos indicadores oficiais de monitoramento da ODS 4 por Unidade "
        "da Federação, ao Índice de Prioridade de Investimento derivado deles e ao corpus de "
        "notícias coletado por raspagem web.\n\n"
        "Toda resposta carrega a proveniência do dado: as colunas `fonte` e `fonte_url` "
        "acompanham cada observação, que é o que sustenta a meta de rastreabilidade de 100% "
        "declarada no Project Charter.\n\n"
        "As observações enviadas por `POST /indicadores` são **voláteis**: vivem na memória do "
        "processo, nunca são gravadas no repositório e desaparecem quando o serviço reinicia. "
        "É a mesma regra do upload de CSV na aplicação Streamlit."
    ),
)

# observacoes recebidas por POST nesta execucao do servico. mesma semantica do
# st.session_state.dados_extras da aplicacao: volatil, marcada e distinguivel do dado oficial.
ENVIADOS: list[dict] = []


# ---------------------------------------------------------------- leitura em cache

# lru_cache faz aqui o papel que @st.cache_data faz na aplicacao: o CSV e lido uma vez por
# processo, nao a cada requisicao. Para reler do disco, reinicie o servico.

@lru_cache(maxsize=1)
def indicadores_oficiais():
    return nc.ler_indicadores()


@lru_cache(maxsize=1)
def fontes():
    return nc.ler_fontes()


@lru_cache(maxsize=1)
def noticias():
    return nc.ler_noticias()


def dados_ativos(incluir_enviados=True):
    # indicadores oficiais mais o que chegou por POST nesta execucao
    base = indicadores_oficiais()
    if not incluir_enviados or not ENVIADOS:
        return base
    return pd.concat([base, pd.DataFrame(ENVIADOS)], ignore_index=True)


def registros(tabela):
    # to_json resolve o que json.dumps nao resolve: NaN vira null e data vira texto ISO
    return json.loads(tabela.to_json(orient="records", date_format="iso"))


# ---------------------------------------------------------------- modelo de entrada

class Observacao(BaseModel):
    """Uma observação de indicador para um território em um ano."""

    indicador: str = Field(..., min_length=3, examples=["Cobertura do programa de reforço"])
    uf: str = Field(..., min_length=2, max_length=2, examples=["BA"])
    ano: int = Field(..., ge=2000, le=2100, examples=[2026])
    valor: float = Field(..., examples=[38.0])
    indicador_ods: str = Field("personalizado", examples=["4.1.2"])
    regiao: str = Field("Não informada", examples=["Nordeste"])
    unidade: str = Field("%", examples=["%"])
    fonte: str = Field("Enviado pela API", examples=["Instituto X"])
    fonte_url: str = Field("", examples=["https://institutox.org.br/relatorio"])

    @field_validator("uf")
    @classmethod
    def uf_em_maiusculas(cls, valor):
        return valor.strip().upper()


# ---------------------------------------------------------------- rotas de servico

@app.get("/", tags=["serviço"], summary="Índice do serviço")
def raiz():
    """Apresenta o serviço e lista as rotas disponíveis, com a documentação interativa."""
    return {
        "projeto": "Bússola ESG Educação",
        "versao": app.version,
        "documentacao_interativa": {"swagger": "/docs", "redoc": "/redoc"},
        "rotas": {
            "GET /saude": "verifica se o serviço está no ar e se os arquivos de dados existem",
            "GET /estatisticas": "números gerais da base: UFs, indicadores, notícias",
            "GET /fontes": "catálogo das fontes de dados do projeto",
            "GET /indicadores": "consulta os indicadores da ODS 4, com filtros",
            "GET /ranking": "Índice de Prioridade de Investimento por UF",
            "GET /noticias": "consulta o corpus de notícias coletado por raspagem",
            "POST /indicadores": "envia novas observações para a base volátil da sessão",
            "GET /indicadores/enviados": "lista o que foi enviado nesta execução",
            "DELETE /indicadores/enviados": "descarta o que foi enviado nesta execução",
        },
    }


@app.get("/saude", tags=["serviço"], summary="Verificação de saúde")
def saude():
    """Diz se o serviço responde e se cada arquivo de dados esperado está no lugar.

    É a rota que a página *Serviço de API* da aplicação Streamlit consulta para mostrar se a
    API está no ar. Não lê o conteúdo dos arquivos, só confere a existência — por isso
    responde rápido e serve para monitoramento.
    """
    esperados = {
        "ods4_uf.csv": nc.TRATADO / "ods4_uf.csv",
        "fontes.csv": nc.TRATADO / "fontes.csv",
        "noticias_educacao.csv": nc.BRUTO / "noticias_educacao.csv",
    }
    arquivos = {nome: caminho.exists() for nome, caminho in esperados.items()}
    return {
        "situacao": "no ar" if all(arquivos.values()) else "dados incompletos",
        "momento": datetime.now().isoformat(timespec="seconds"),
        "arquivos": arquivos,
        "observacoes_enviadas_nesta_execucao": len(ENVIADOS),
    }


@app.get("/estatisticas", tags=["serviço"], summary="Números gerais da base")
def estatisticas():
    """Resume a base em números: cobertura territorial, profundidade do dado e corpus de texto."""
    dados = dados_ativos()
    corpus = noticias()
    resumo = nc.estatisticas_noticias(corpus)
    return {
        "indicadores": {
            "ufs_cobertas": int(dados["uf"].nunique()),
            "indicadores_distintos": int(dados["indicador"].nunique()),
            "observacoes": int(len(dados)),
            "observacoes_enviadas": len(ENVIADOS),
            "ano_mais_recente": int(dados["ano"].max()),
        },
        "noticias": {
            "materias": resumo["noticias"],
            "fontes": resumo["fontes"],
            "palavras": resumo["palavras"],
            "media_palavras_por_materia": resumo["media_palavras"],
            "primeira": resumo["primeira"].date().isoformat() if pd.notna(resumo["primeira"]) else None,
            "ultima": resumo["ultima"].date().isoformat() if pd.notna(resumo["ultima"]) else None,
        },
    }


@app.get("/fontes", tags=["dados"], summary="Catálogo de fontes")
def listar_fontes():
    """Devolve o catálogo de fontes do projeto, com tipo de dado, forma de acesso e situação.

    É a tabela que sustenta a seção de rastreabilidade do reporte ESG.
    """
    tabela = fontes()
    return {"total": len(tabela), "dados": registros(tabela)}


# ---------------------------------------------------------------- rotas de consulta

@app.get("/indicadores", tags=["dados"], summary="Consulta os indicadores da ODS 4")
def listar_indicadores(
    uf: list[str] | None = Query(None, description="Sigla da UF. Repita o parâmetro para várias: `?uf=BA&uf=PI`."),
    indicador: str | None = Query(None, description="Trecho do nome do indicador, sem diferenciar maiúsculas."),
    indicador_ods: str | None = Query(None, description="Código da meta da ODS 4, por exemplo `4.1.2`."),
    regiao: list[str] | None = Query(None, description="Região geográfica, por exemplo `Nordeste`."),
    ano: int | None = Query(None, description="Ano de referência da observação."),
    incluir_enviados: bool = Query(True, description="Inclui as observações recebidas por POST nesta execução."),
    limite: int = Query(200, ge=1, le=1000, description="Número máximo de linhas na resposta."),
):
    """Consulta as observações de indicadores da ODS 4 por Unidade da Federação.

    Sem filtro, devolve a base inteira até o `limite`. Os filtros se combinam por E lógico:
    `?uf=BA&ano=2025` traz só as observações da Bahia em 2025. Cada linha vem com `fonte` e
    `fonte_url`, de modo que o consumidor possa citar a origem do número que usou.
    """
    dados = dados_ativos(incluir_enviados)

    if uf:
        siglas = [s.strip().upper() for s in uf]
        dados = dados[dados["uf"].isin(siglas)]
    if regiao:
        alvos = [r.strip().casefold() for r in regiao]
        dados = dados[dados["regiao"].str.casefold().isin(alvos)]
    if indicador:
        dados = dados[dados["indicador"].str.contains(indicador, case=False, na=False)]
    if indicador_ods:
        dados = dados[dados["indicador_ods"].astype(str) == indicador_ods]
    if ano is not None:
        dados = dados[dados["ano"] == ano]

    return {
        "total": int(len(dados)),
        "retornados": int(min(len(dados), limite)),
        "filtros": {"uf": uf, "indicador": indicador, "indicador_ods": indicador_ods,
                    "regiao": regiao, "ano": ano, "incluir_enviados": incluir_enviados},
        "dados": registros(dados.head(limite)),
    }


@app.get("/ranking", tags=["dados"], summary="Índice de Prioridade de Investimento")
def ranking(
    metodo: str = Query("min-max entre UFs", description="Normalização: `min-max entre UFs` ou `distancia de 100%`."),
    indicador: list[str] | None = Query(None, description="Restringe o índice a estes indicadores (nome exato). Repita o parâmetro."),
    regiao: list[str] | None = Query(None, description="Devolve só as UFs destas regiões, sem alterar o cálculo."),
    incluir_enviados: bool = Query(True, description="Inclui as observações recebidas por POST nesta execução."),
    limite: int = Query(27, ge=1, le=100, description="Número máximo de UFs na resposta."),
):
    """Calcula o Índice de Prioridade de Investimento por UF e devolve o ranking.

    O índice mede a **carência** do território nos indicadores da ODS 4: quanto maior, mais
    distante o território está da meta. Os indicadores entram com peso igual — para ponderá-los
    de forma diferente, use a página *Índice de prioridade* da aplicação Streamlit, que expõe
    um controle de peso por indicador. O parâmetro `indicador` permite restringir o cálculo a
    um subconjunto, o que equivale a dar peso zero aos demais.

    O filtro `regiao` é aplicado **depois** do cálculo, de propósito: a posição no ranking
    continua sendo a posição nacional, não a posição dentro da região.
    """
    if metodo not in nc.METODOS_INDICE:
        raise HTTPException(status_code=422, detail=f"metodo deve ser um de {nc.METODOS_INDICE}")

    dados = dados_ativos(incluir_enviados)
    disponiveis = nc.indicadores_disponiveis(dados)

    if indicador:
        desconhecidos = [i for i in indicador if i not in disponiveis]
        if desconhecidos:
            raise HTTPException(
                status_code=404,
                detail={"mensagem": "indicador não encontrado", "desconhecidos": desconhecidos,
                        "disponiveis": disponiveis},
            )
        pesos = {i: (1.0 if i in indicador else 0.0) for i in disponiveis}
    else:
        pesos = {i: 1.0 for i in disponiveis}

    tabela = nc.calcular_indice(dados, pesos, metodo)
    if tabela.empty:
        raise HTTPException(status_code=422, detail="nenhum indicador ativo, o índice não pode ser calculado")

    if regiao:
        alvos = [r.strip().casefold() for r in regiao]
        tabela = tabela[tabela["regiao"].str.casefold().isin(alvos)]

    return {
        "metodo": metodo,
        "indicadores_no_calculo": [i for i, p in pesos.items() if p > 0],
        "total": int(len(tabela)),
        "ressalva": "O índice é medida de prioridade de investimento, nunca de mérito do território.",
        "dados": registros(tabela.head(limite)),
    }


@app.get("/noticias", tags=["dados"], summary="Consulta o corpus de notícias")
def listar_noticias(
    fonte: list[str] | None = Query(None, description="Nome da fonte, por exemplo `Agência Brasil`."),
    uf: str | None = Query(None, description="Sigla da UF citada na matéria, por exemplo `BA`. A coluna `ufs_citadas` guarda siglas, não o nome por extenso."),
    tema: str | None = Query(None, description="Tema da ODS 4 atribuído na coleta, por exemplo `4.5 equidade` ou só `4.5`."),
    busca: str | None = Query(None, description="Trecho a procurar no título, resumo e corpo da matéria."),
    com_texto: bool = Query(False, description="Inclui o corpo integral da matéria na resposta."),
    limite: int = Query(20, ge=1, le=200, description="Número máximo de matérias na resposta."),
):
    """Consulta as matérias coletadas por raspagem web, da mais recente para a mais antiga.

    O corpo integral fica fora da resposta por padrão: são 59 mil palavras no corpus, e quase
    todo consumidor quer a lista, não o texto. Peça `com_texto=true` quando precisar do texto —
    é esse campo que alimentará as tarefas de LLM previstas em `3_modeling/plano_llm.md`.
    Toda matéria vem com `fonte` e `url` do original; a aplicação não republica o texto como
    conteúdo próprio, usa-o como corpus de análise.
    """
    corpus = noticias()

    if fonte:
        alvos = [f.strip().casefold() for f in fonte]
        corpus = corpus[corpus["fonte"].str.casefold().isin(alvos)]
    if uf:
        corpus = corpus[corpus["ufs_citadas"].fillna("").str.contains(uf.strip(), case=False)]
    if tema:
        corpus = corpus[corpus["temas_ods4"].fillna("").str.contains(tema.strip(), case=False)]
    if busca:
        corpus = corpus[corpus["conteudo"].str.contains(busca, case=False, na=False)]

    colunas = ["fonte", "data", "titulo", "resumo", "editoria", "ufs_citadas",
               "temas_ods4", "n_palavras", "url"]
    if com_texto:
        colunas.append("texto")

    return {
        "total": int(len(corpus)),
        "retornados": int(min(len(corpus), limite)),
        "filtros": {"fonte": fonte, "uf": uf, "tema": tema, "busca": busca},
        "dados": registros(corpus.head(limite)[colunas]),
    }


# ---------------------------------------------------------------- rota de escrita

@app.post("/indicadores", tags=["envio"], status_code=201, summary="Envia novas observações")
def enviar_indicadores(observacoes: list[Observacao]):
    """Recebe observações de indicadores e as incorpora à base **volátil** desta execução.

    Serve ao caso de uso que o Project Charter prevê no objetivo 3.6: o instituto que tem
    dado próprio de cobertura de programa e quer vê-lo no ranking junto dos indicadores
    oficiais, sem acesso ao repositório. É o equivalente, por HTTP, ao upload de CSV da
    aplicação Streamlit.

    As linhas recebidas são marcadas com `origem = "api"`, de modo que permaneçam
    distinguíveis do dado oficial do IBGE em toda consulta. Elas passam a aparecer em
    `GET /indicadores` e a entrar no cálculo de `GET /ranking` — salvo se a consulta pedir
    `incluir_enviados=false`. Nada é gravado em disco: ao reiniciar o serviço, a base volta a
    ser só a oficial.

    Envie uma lista, mesmo que de um único item:

    ```json
    [{"indicador": "Cobertura do programa de reforço", "uf": "BA", "ano": 2026, "valor": 38.0}]
    ```
    """
    if not observacoes:
        raise HTTPException(status_code=422, detail="envie ao menos uma observação")

    recebido = datetime.now().isoformat(timespec="seconds")
    novas = []
    for obs in observacoes:
        linha = obs.model_dump()
        linha["cod_uf"] = None          # sem codigo do IBGE a linha nao entra no mapa, e esta certo
        linha["origem"] = "api"
        linha["recebido_em"] = recebido
        novas.append(linha)

    ENVIADOS.extend(novas)
    return {
        "aceitas": len(novas),
        "total_na_execucao": len(ENVIADOS),
        "aviso": "Dados voláteis: não são gravados no repositório e somem quando o serviço reinicia.",
        "dados": novas,
    }


@app.get("/indicadores/enviados", tags=["envio"], summary="Lista o que foi enviado")
def listar_enviados():
    """Devolve as observações recebidas por `POST /indicadores` nesta execução do serviço."""
    return {"total": len(ENVIADOS), "dados": ENVIADOS}


@app.delete("/indicadores/enviados", tags=["envio"], summary="Descarta o que foi enviado")
def descartar_enviados():
    """Esvazia a base volátil, devolvendo o serviço ao estado em que só há dado oficial."""
    descartadas = len(ENVIADOS)
    ENVIADOS.clear()
    return {"descartadas": descartadas, "total_na_execucao": 0}


# ---------------------------------------------------------------- execucao direta

if __name__ == "__main__":
    # permite "python api.py" sem decorar a linha de comando do uvicorn
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
