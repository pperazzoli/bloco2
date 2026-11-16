# api.py - servico HTTP do projeto, construido com FastAPI
# roda separado da aplicacao streamlit: "uvicorn api:app --reload" ou "python api.py"
# criado 16-11-2026 (TP3)
# edited 16-11-2026 (TP4): entrou o grupo de rotas de linguagem natural, que usa o modelo
# local de modelo_llm.py; toda rota passou a declarar response_model, de modo que o FastAPI
# valide a saida antes de serializar; a falha de carga do modelo virou um handler de excecao
# que responde 503 sem derrubar as rotas de dados.
#
# A API nao tem logica propria: le os mesmos arquivos de data/ e chama as mesmas funcoes de
# nucleo.py que a aplicacao Streamlit chama. E deliberado - o indice que esta API devolve e,
# por construcao, o mesmo indice que o painel mostra.
#
# Documentacao interativa, gerada pelo proprio FastAPI a partir deste arquivo:
#   http://127.0.0.1:8000/docs      (Swagger UI)
#   http://127.0.0.1:8000/redoc     (ReDoc)
# A referencia escrita das rotas esta em 4_deployment/api_reference.md, e a justificativa do
# modelo de linguagem em 3_modeling/modelo_llm.md.

import json
import time
from datetime import datetime
from functools import lru_cache
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

import modelo_llm as ml
import nucleo as nc

# descricao de cada grupo de rotas, exibida no /docs acima das rotas do grupo
ETIQUETAS = [
    {"name": "serviço", "description": "Situação do serviço e números gerais da base."},
    {"name": "dados", "description": "Consulta aos indicadores, ao índice de prioridade e ao corpus de notícias."},
    {"name": "envio", "description": "Envio de observações para a base volátil desta execução do serviço."},
    {
        "name": "linguagem natural",
        "description": (
            "Processamento de texto por modelos que rodam **nesta máquina**, sem chamada a "
            "serviço externo. Há um modelo por tarefa — sentimento e resumo —, cada um "
            "carregado sob demanda e em separado: a primeira chamada de cada tarefa leva "
            "alguns segundos, as seguintes respondem mais rápido.\n\n"
            "Quando um modelo não pode ser carregado, as rotas que dependem dele respondem "
            "**503** com o motivo e o que fazer, e as rotas de dados continuam funcionando."
        ),
    },
]

app = FastAPI(
    title="Bússola ESG Educação — API",
    version="1.1.0",
    openapi_tags=ETIQUETAS,
    description=(
        "Serviço de consulta aos indicadores oficiais de monitoramento da ODS 4 por Unidade "
        "da Federação, ao Índice de Prioridade de Investimento derivado deles e ao corpus de "
        "notícias coletado por raspagem web.\n\n"
        "Toda resposta carrega a proveniência do dado: as colunas `fonte` e `fonte_url` "
        "acompanham cada observação, que é o que sustenta a meta de rastreabilidade de 100% "
        "declarada no Project Charter.\n\n"
        "As observações enviadas por `POST /indicadores` são **voláteis**: vivem na memória do "
        "processo, nunca são gravadas no repositório e desaparecem quando o serviço reinicia. "
        "É a mesma regra do upload de CSV na aplicação Streamlit.\n\n"
        "O grupo **linguagem natural** processa texto com modelos carregados localmente, "
        "descritos em `3_modeling/modelo_llm.md`: um de classificação de sentimento e um de "
        "resumo. O resultado desse processamento é camada de contexto — nunca entra no cálculo "
        "do índice, e toda resposta do grupo carrega o aviso correspondente. O resumo é texto "
        "**gerado**, e o campo `gerativo` da resposta o marca como tal."
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


def texto_ou_nulo(valor):
    # celula vazia do pandas e NaN, que e verdadeiro num teste booleano e quebraria o
    # response_model ao chegar onde se espera str ou None
    return None if pd.isna(valor) else str(valor)


def filtrar_noticias(corpus, fonte=None, uf=None, tema=None, busca=None):
    # edited 16-11-2026 (TP4): o filtro saiu de dentro da rota /noticias para que
    # /noticias/sentimento use exatamente o mesmo. As duas rotas tem de entender "uf=BA" do
    # mesmo jeito, senao o cliente filtra uma coisa na consulta e outra na analise.
    if fonte:
        alvos = [f.strip().casefold() for f in fonte]
        corpus = corpus[corpus["fonte"].str.casefold().isin(alvos)]
    if uf:
        corpus = corpus[corpus["ufs_citadas"].fillna("").str.contains(uf.strip(), case=False)]
    if tema:
        corpus = corpus[corpus["temas_ods4"].fillna("").str.contains(tema.strip(), case=False)]
    if busca:
        corpus = corpus[corpus["conteudo"].str.contains(busca, case=False, na=False)]
    return corpus


def agregar_por_uf(classificadas):
    # a coluna ufs_citadas guarda siglas separadas por ponto e virgula: uma materia que cita
    # tres UFs conta para as tres, e a soma de 'materias' por isso passa do total analisado
    contagem = {}
    for item in classificadas:
        for sigla in str(item["ufs_citadas"] or "").split(";"):
            sigla = sigla.strip()
            if not sigla:
                continue
            linha = contagem.setdefault(
                sigla, {"uf": sigla, "materias": 0, "positivo": 0, "neutro": 0, "negativo": 0}
            )
            linha["materias"] += 1
            if item["rotulo"] in linha:
                linha[item["rotulo"]] += 1
    saida = []
    for linha in contagem.values():
        linha["saldo"] = round((linha["positivo"] - linha["negativo"]) / linha["materias"], 2)
        saida.append(linha)
    return sorted(saida, key=lambda linha: (-linha["materias"], linha["uf"]))


# ---------------------------------------------------------------- modelos de entrada

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


class Texto(BaseModel):
    """Texto submetido ao modelo de linguagem local."""

    texto: str = Field(
        ...,
        min_length=20,
        max_length=20000,
        description=(
            "Texto a analisar, em português. Mínimo de 20 caracteres: abaixo disso a "
            "classificação não tem sinal suficiente para significar algo."
        ),
        examples=[
            "A rede estadual ampliou a oferta de vagas em creche e reduziu pela metade a fila "
            "de espera, segundo o balanço divulgado pela secretaria de educação."
        ],
    )
    tarefa: Literal["sentimento", "resumo"] = Field(
        "sentimento",
        description=(
            "Tarefa a executar. `sentimento` classifica o tom do texto em três rótulos; "
            "`resumo` reescreve o texto em uma versão curta. Cada tarefa tem o seu modelo, "
            "carregado em separado."
        ),
    )

    @field_validator("texto")
    @classmethod
    def sem_espaco_sobrando(cls, valor):
        limpo = valor.strip()
        if len(limpo) < 20:
            raise ValueError("o texto precisa ter ao menos 20 caracteres fora dos espaços")
        return limpo


# ---------------------------------------------------------------- modelos de resposta

# Response models. O FastAPI valida a saida de cada rota contra a classe declarada em
# response_model antes de serializar, e o /docs passa a mostrar o formato exato da resposta.
# O ganho e de contrato: se uma rota deixar de devolver uma chave prometida, o erro aparece
# no servidor como falha de validacao, em vez de chegar ao cliente como resposta silenciosa-
# mente diferente da documentada. Onde o conteudo da linha varia com o filtro - as tabelas de
# indicadores e de noticias - o tipo e list[dict], porque ali a forma do registro e a forma
# do CSV, e congelar coluna por coluna no modelo quebraria a rota a cada mudanca de fonte.

class RespostaRaiz(BaseModel):
    """Índice do serviço."""

    projeto: str
    versao: str
    documentacao_interativa: dict[str, str]
    rotas: dict[str, str]


class RespostaSaude(BaseModel):
    """Situação do serviço e presença dos arquivos de dados."""

    situacao: str = Field(..., examples=["no ar"])
    momento: str
    arquivos: dict[str, bool]
    observacoes_enviadas_nesta_execucao: int
    modelo_de_linguagem: dict[str, dict[str, bool]]


class EstatisticaIndicadores(BaseModel):
    ufs_cobertas: int
    indicadores_distintos: int
    observacoes: int
    observacoes_enviadas: int
    ano_mais_recente: int


class EstatisticaNoticias(BaseModel):
    materias: int
    fontes: int
    palavras: int
    media_palavras_por_materia: int
    primeira: str | None = None
    ultima: str | None = None


class RespostaEstatisticas(BaseModel):
    """Números gerais da base."""

    indicadores: EstatisticaIndicadores
    noticias: EstatisticaNoticias


class RespostaFontes(BaseModel):
    """Catálogo de fontes do projeto."""

    total: int
    dados: list[dict]


class RespostaTabela(BaseModel):
    """Envelope das consultas tabulares: contagem, filtros aplicados e linhas."""

    total: int = Field(..., description="Linhas que satisfazem o filtro, antes do limite.")
    retornados: int = Field(..., description="Linhas efetivamente devolvidas em `dados`.")
    filtros: dict = Field(..., description="Os filtros como o serviço os interpretou.")
    dados: list[dict]


class RespostaRanking(BaseModel):
    """Ranking do Índice de Prioridade de Investimento."""

    metodo: str
    indicadores_no_calculo: list[str]
    total: int
    ressalva: str
    dados: list[dict]


class RespostaEnvio(BaseModel):
    """Confirmação de recebimento das observações enviadas."""

    aceitas: int
    total_na_execucao: int
    aviso: str
    dados: list[dict]


class RespostaEnviados(BaseModel):
    """Conteúdo atual da base volátil."""

    total: int
    dados: list[dict]


class RespostaDescarte(BaseModel):
    """Resultado do descarte da base volátil."""

    descartadas: int
    total_na_execucao: int


class Pontuacao(BaseModel):
    """Pontuação atribuída pelo modelo a um dos rótulos possíveis."""

    rotulo: str = Field(..., examples=["positivo"])
    pontuacao: float = Field(..., ge=0, le=1, examples=[0.6626])


class FichaModelo(BaseModel):
    """Ficha de um dos modelos locais e situação da sua carga."""

    tarefa: str = Field(..., examples=["sentimento"])
    descricao: str = Field(..., examples=["classificação de sentimento"])
    modelo: str = Field(..., description="Identificador do modelo no HuggingFace Hub.")
    tarefa_huggingface: str
    gerativo: bool = Field(..., description="Se o modelo produz texto novo em vez de escolher entre rótulos fixos.")
    carregado: bool = Field(..., description="Se o modelo já está na memória deste processo.")
    ja_baixado: bool = Field(..., description="Se os pesos já estão no cache local, caso em que a carga não precisa de rede.")
    arquitetura: str | None = None
    parametros: int | None = Field(None, description="Número de parâmetros, conhecido só depois da carga.")
    dispositivo: str | None = Field(None, examples=["cpu"])
    limite_de_tokens: int
    rotulos: list[str] = Field(..., description="Rótulos possíveis; vazio nas tarefas gerativas.")
    segundos_de_carga: float | None = None
    carregado_em: str | None = None
    erro: str | None = Field(None, description="Motivo da última falha de carga, se houve.")
    aviso: str


class RespostaModelos(BaseModel):
    """Os modelos de linguagem do serviço e o ambiente local em que rodam."""

    execucao: str
    cache_local: str
    bibliotecas: dict[str, str | None]
    parametros_de_geracao: dict = Field(..., description="Parâmetros fixos usados nas tarefas gerativas.")
    modelos: list[FichaModelo]


class ResultadoSentimento(BaseModel):
    """O que a tarefa `sentimento` devolve."""

    rotulo: str = Field(..., description="Rótulo de maior pontuação.", examples=["negativo"])
    confianca: float = Field(..., ge=0, le=1)
    distribuicao: list[Pontuacao] = Field(..., description="Pontuação de todos os rótulos, do maior ao menor.")


class ItemConferido(BaseModel):
    """Um termo do resumo procurado no texto de origem."""

    tipo: str = Field(..., examples=["nome próprio"], description="`número`, `data` ou `nome próprio`.")
    termo: str = Field(..., examples=["Rio Grande do Sul"])
    no_original: bool = Field(..., description="Falso quando o termo **não** aparece no texto de origem.")


class Conferencia(BaseModel):
    """Conferência automática do resumo contra o texto que o originou.

    Não usa modelo: procura no resumo os três tipos de termo que um modelo gerativo inventa
    com mais frequência — número, data e nome próprio — e checa cada um no original.
    """

    situacao: str = Field(..., examples=["revisar"], description="`sem divergência` ou `revisar`.")
    conferidos: int = Field(..., description="Termos verificáveis encontrados no resumo.")
    ausentes: int = Field(..., description="Quantos desses não aparecem no texto de origem.")
    itens: list[ItemConferido] = Field(..., description="Os termos conferidos, ausentes primeiro.")
    metodo: str
    ressalva: str


class ResultadoResumo(BaseModel):
    """O que a tarefa `resumo` devolve."""

    resumo: str = Field(..., description="Texto gerado pelo modelo. Não é recorte do original.")
    palavras_entrada: int
    palavras_resumo: int
    taxa_de_compressao: float = Field(..., ge=0, description="Palavras do resumo divididas pelas palavras da entrada.")
    conferencia: Conferencia


class RespostaTexto(BaseModel):
    """Resultado do processamento de um texto enviado pelo cliente.

    O cabeçalho é comum às tarefas; o bloco de resultado é o da tarefa pedida, e só ele vem
    na resposta — o outro é omitido em vez de vir nulo.
    """

    tarefa: str = Field(..., examples=["sentimento"])
    modelo: str
    gerativo: bool
    caracteres: int
    tokens: int = Field(..., description="Tokens que o texto gerou no tokenizador do modelo.")
    texto_truncado: bool = Field(..., description="Verdadeiro quando o texto passou de `limite_de_tokens` e o excedente foi ignorado.")
    limite_de_tokens: int
    segundos: float
    analisado_em: str
    aviso: str
    sentimento: ResultadoSentimento | None = None
    resumo: ResultadoResumo | None = None


class NoticiaClassificada(BaseModel):
    """Uma matéria do corpus com o rótulo atribuído pelo modelo."""

    data: str | None = None
    fonte: str
    titulo: str
    url: str | None = None
    ufs_citadas: str | None = None
    temas_ods4: str | None = None
    rotulo: str
    confianca: float = Field(..., ge=0, le=1)
    tokens: int
    texto_truncado: bool


class SentimentoPorUF(BaseModel):
    """Agregação dos rótulos por Unidade da Federação citada nas matérias."""

    uf: str
    materias: int
    positivo: int
    neutro: int
    negativo: int
    saldo: float = Field(
        ...,
        ge=-1,
        le=1,
        description="(positivas - negativas) / matérias. Mede o tom da cobertura, não a situação da UF.",
    )


class RespostaNoticias(BaseModel):
    """Resultado da aplicação do modelo ao corpus de notícias."""

    tarefa: str
    modelo: str
    campo_analisado: str
    analisadas: int
    total_no_corpus: int
    filtros: dict
    por_rotulo: dict[str, int]
    por_uf: list[SentimentoPorUF]
    segundos: float
    analisado_em: str
    aviso: str
    dados: list[NoticiaClassificada]


# ------------------------------------------------- tratamento de erro do modelo

# As duas excecoes de modelo_llm.py sao traduzidas aqui, em um lugar so, em vez de num
# try/except repetido por rota. A distincao importa para quem consome: 503 e o servico
# dizendo que o modelo nao esta disponivel - a requisicao pode ser repetida depois, e as
# rotas de dados continuam atendendo; 500 e falha ao processar aquele texto especifico.

@app.exception_handler(ml.ModeloIndisponivel)
def modelo_indisponivel(request: Request, erro: ml.ModeloIndisponivel):
    return JSONResponse(
        status_code=503,
        content={
            "detail": {
                "erro": "modelo de linguagem indisponível",
                "modelos": {t: ml.MODELOS[t]["modelo"] for t in ml.TAREFAS},
                "motivo": str(erro),
                "o_que_fazer": [
                    "confira se as dependências estão instaladas: pip install -r requirements.txt",
                    "a primeira carga baixa os pesos do HuggingFace Hub e precisa de rede",
                    "tente carregar de novo em POST /modelo/carregar?tarefa=<tarefa>",
                    "consulte GET /modelo para ver a situação de cada modelo",
                ],
                "rotas_nao_afetadas": (
                    "as rotas de /indicadores, /ranking, /noticias e /fontes não dependem do "
                    "modelo e continuam respondendo normalmente"
                ),
            }
        },
    )


@app.exception_handler(ml.TarefaDesconhecida)
def tarefa_desconhecida(request: Request, erro: ml.TarefaDesconhecida):
    # 422: o pedido e que esta errado, nao o serviço
    return JSONResponse(
        status_code=422,
        content={"detail": {"erro": "tarefa desconhecida", "motivo": str(erro),
                            "tarefas": ml.TAREFAS}},
    )


@app.exception_handler(ml.ErroDeInferencia)
def erro_de_inferencia(request: Request, erro: ml.ErroDeInferencia):
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "erro": "falha ao processar o texto",
                "motivo": str(erro),
                "o_que_fazer": (
                    "o modelo está carregado, a falha é no processamento deste texto; verifique "
                    "o conteúdo enviado e repita a chamada"
                ),
            }
        },
    )


# respostas de erro declaradas no /docs para as rotas que dependem do modelo
ERRO_DE_CARGA = {
    503: {"description": "O modelo de linguagem não pôde ser carregado. A resposta diz o motivo e o que fazer."},
}
ERROS_DO_MODELO = {
    **ERRO_DE_CARGA,
    500: {"description": "O modelo está carregado mas falhou ao processar o texto."},
}


# ---------------------------------------------------------------- rotas de servico

@app.get("/", tags=["serviço"], response_model=RespostaRaiz, summary="Índice do serviço")
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
            "GET /modelo": "ficha dos modelos de linguagem locais e situação de cada carga",
            "POST /modelo/carregar": "carrega um modelo na memória, ou tenta de novo após falha",
            "POST /processar_texto": "processa um texto com um modelo local: sentimento ou resumo",
            "POST /noticias/sentimento": "aplica o modelo ao corpus de notícias coletado",
        },
    }


@app.get("/saude", tags=["serviço"], response_model=RespostaSaude, summary="Verificação de saúde")
def saude():
    """Diz se o serviço responde e se cada arquivo de dados esperado está no lugar.

    É a rota que a página *Serviço de API* da aplicação Streamlit consulta para mostrar se a
    API está no ar. Não lê o conteúdo dos arquivos, só confere a existência — por isso
    responde rápido e serve para monitoramento.

    O bloco `modelo_de_linguagem` informa se os pesos já estão no cache local e se o modelo
    já foi carregado neste processo, **sem** carregá-lo: a rota tem de continuar barata.
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
        "modelo_de_linguagem": {
            tarefa: {
                "pesos_no_cache_local": ml.ja_baixado(tarefa),
                "carregado_neste_processo": ml.ficha(tarefa)["carregado"],
            }
            for tarefa in ml.TAREFAS
        },
    }


@app.get("/estatisticas", tags=["serviço"], response_model=RespostaEstatisticas, summary="Números gerais da base")
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


@app.get("/fontes", tags=["dados"], response_model=RespostaFontes, summary="Catálogo de fontes")
def listar_fontes():
    """Devolve o catálogo de fontes do projeto, com tipo de dado, forma de acesso e situação.

    É a tabela que sustenta a seção de rastreabilidade do reporte ESG.
    """
    tabela = fontes()
    return {"total": len(tabela), "dados": registros(tabela)}


# ---------------------------------------------------------------- rotas de consulta

@app.get("/indicadores", tags=["dados"], response_model=RespostaTabela, summary="Consulta os indicadores da ODS 4")
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


@app.get("/ranking", tags=["dados"], response_model=RespostaRanking, summary="Índice de Prioridade de Investimento")
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


@app.get("/noticias", tags=["dados"], response_model=RespostaTabela, summary="Consulta o corpus de notícias")
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
    corpus = filtrar_noticias(noticias(), fonte=fonte, uf=uf, tema=tema, busca=busca)

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

@app.post("/indicadores", tags=["envio"], status_code=201, response_model=RespostaEnvio, summary="Envia novas observações")
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


@app.get("/indicadores/enviados", tags=["envio"], response_model=RespostaEnviados, summary="Lista o que foi enviado")
def listar_enviados():
    """Devolve as observações recebidas por `POST /indicadores` nesta execução do serviço."""
    return {"total": len(ENVIADOS), "dados": ENVIADOS}


@app.delete("/indicadores/enviados", tags=["envio"], response_model=RespostaDescarte, summary="Descarta o que foi enviado")
def descartar_enviados():
    """Esvazia a base volátil, devolvendo o serviço ao estado em que só há dado oficial."""
    descartadas = len(ENVIADOS)
    ENVIADOS.clear()
    return {"descartadas": descartadas, "total_na_execucao": 0}


# ---------------------------------------------------------------- rotas de linguagem natural

# criado 16-11-2026 (TP4). Estas quatro rotas sao as unicas que dependem do modelo de
# linguagem. A separacao e proposital: se o modelo nao carregar, elas respondem 503 e todo o
# resto do servico continua funcionando - a mesma postura que o Project Charter registra para
# a ausencia de rede na secao 10.

@app.get("/modelo", tags=["linguagem natural"], response_model=RespostaModelos,
         summary="Ficha dos modelos de linguagem")
def ficha_dos_modelos():
    """Descreve os modelos de linguagem locais e diz em que estado está a carga de cada um.

    **Não carrega nada.** É a rota que a página *Análise de linguagem* consulta ao abrir,
    para saber que tarefas vale oferecer e para avisar que a primeira chamada vai demorar.
    Por isso responde em milissegundos mesmo com os dois modelos ainda em disco.

    Há um modelo por tarefa, carregado em separado: quem só usa o sentimento nunca paga o
    custo de carregar o de resumo. Os campos `arquitetura`, `parametros` e `dispositivo` só
    vêm preenchidos depois de uma carga bem-sucedida — antes dela o processo não tem como
    sabê-los. `ja_baixado` diz se os pesos estão no cache local, caso em que a carga não
    precisa de rede; `erro` guarda o motivo da última falha daquele modelo, se houve.

    `gerativo` separa o modelo que escolhe entre rótulos fixos daquele que produz texto novo.
    A distinção não é informativa apenas: é ela que decide quais regras de contenção do risco
    8.4 do Project Charter se aplicam ao resultado.
    """
    return ml.informacoes()


@app.post("/modelo/carregar", tags=["linguagem natural"], response_model=FichaModelo,
          responses=ERRO_DE_CARGA, summary="Carrega um modelo na memória")
def carregar_modelo(
    tarefa: str = Query("sentimento", description="Qual modelo carregar: `sentimento` ou `resumo`."),
):
    """Carrega os pesos de um modelo na memória, ou tenta de novo depois de uma falha.

    Serve a dois propósitos. O primeiro é tirar o custo da carga da primeira análise: a
    interface chama esta rota num botão explícito, o usuário vê o tempo passar uma vez e as
    análises seguintes respondem rápido. O segundo é a nova tentativa — uma falha de carga
    fica registrada no processo para que não seja repetida a cada requisição, e esta rota é
    o caminho para tentar outra vez depois de, por exemplo, a rede voltar.

    A tarefa é obrigatória na prática: carregar os dois modelos de uma vez ocuparia memória
    que talvez ninguém vá usar, e quem precisa só de um não deve esperar pelo outro.

    Responde **422** se a tarefa não existir e **503** se o modelo não puder ser carregado,
    com o motivo e o que fazer.
    """
    ml.carregar(tarefa, forcar=True)
    return ml.ficha(tarefa)


@app.post("/processar_texto", tags=["linguagem natural"], response_model=RespostaTexto,
          response_model_exclude_none=True, responses=ERROS_DO_MODELO,
          summary="Processa um texto com um modelo local")
def processar_texto(entrada: Texto):
    """Processa um texto em português com o modelo que roda nesta máquina.

    Nenhum dado sai do computador: os modelos foram baixados uma vez para o cache local e a
    inferência acontece neste processo.

    Duas tarefas, escolhidas no campo `tarefa` do corpo:

    - **`sentimento`** classifica o tom do texto. A resposta traz a distribuição completa — a
      pontuação dos três rótulos, não só a do vencedor. Isso é deliberado: em texto
      institucional a diferença entre o primeiro e o segundo rótulo é muitas vezes pequena, e
      quem consome a resposta precisa poder ver isso em vez de receber um rótulo seco que
      parece mais seguro do que é.
    - **`resumo`** reescreve o texto numa versão curta. É resumo **abstrativo**: o modelo
      redige, não recorta, e pode afirmar o que não está no original. A resposta traz a taxa
      de compressão, o campo `gerativo` verdadeiro — para que nenhum consumidor confunda
      texto produzido por modelo com dado apurado pelo projeto — e o bloco `conferencia`,
      que lista cada número, data e nome próprio do resumo dizendo se aparece no texto de
      origem. `situacao: "revisar"` significa que pelo menos um não aparece.

    O cabeçalho da resposta é o mesmo nas duas; o bloco de resultado é o da tarefa pedida, e
    só ele aparece. Os campos `tokens`, `limite_de_tokens` e `texto_truncado` declaram o que o
    modelo de fato leu: texto acima do limite é cortado, não rejeitado, e a resposta diz que
    foi cortado — num resumo isso importa mais ainda, porque o resumo de meio texto parece um
    resumo do texto inteiro.

    ```json
    {"texto": "A evasão escolar no ensino médio voltou a crescer no estado.", "tarefa": "resumo"}
    ```

    Erros: **422** se o texto tiver menos de 20 caracteres úteis ou a tarefa for desconhecida,
    **503** se o modelo da tarefa não estiver disponível, **500** se a inferência falhar.
    """
    config = ml.MODELOS[entrada.tarefa]
    resultado = ml.processar(entrada.tarefa, [entrada.texto])[0]
    comuns = ("caracteres", "tokens", "texto_truncado", "limite_de_tokens", "segundos")
    return {
        "tarefa": entrada.tarefa,
        "modelo": config["modelo"],
        "gerativo": config["gerativo"],
        "analisado_em": datetime.now().isoformat(timespec="seconds"),
        "aviso": ml.AVISOS[entrada.tarefa],
        **{chave: resultado[chave] for chave in comuns},
        # o nome da tarefa e o nome do bloco de resultado, por construcao
        entrada.tarefa: {c: v for c, v in resultado.items() if c not in comuns},
    }


@app.post("/noticias/sentimento", tags=["linguagem natural"], response_model=RespostaNoticias,
          responses=ERROS_DO_MODELO, summary="Aplica o modelo ao corpus de notícias")
def sentimento_das_noticias(
    fonte: list[str] | None = Query(None, description="Nome da fonte, por exemplo `Agência Brasil`. Repita o parâmetro para várias."),
    uf: str | None = Query(None, description="Sigla da UF citada na matéria, por exemplo `BA`."),
    tema: str | None = Query(None, description="Tema da ODS 4 atribuído na coleta, por exemplo `4.5`."),
    campo: str = Query("titulo e resumo", description="Que parte da matéria vai ao modelo: `titulo e resumo` ou `texto`."),
    limite: int = Query(20, ge=1, le=105, description="Número de matérias a analisar. Cada uma custa cerca de 80 ms de CPU."),
):
    """Aplica o modelo de linguagem ao corpus de notícias já coletado e agrega o resultado.

    É a tarefa 2.3 de `3_modeling/plano_llm.md`. O corpus é lido no servidor: o cliente não
    precisa trafegar as 59 mil palavras para analisá-las, manda o filtro e recebe o resultado.
    Os filtros `fonte`, `uf` e `tema` são os mesmos de `GET /noticias`, pela mesma função.

    `campo` escolhe o que vai ao modelo. O padrão, `titulo e resumo`, é o lead da matéria: cabe
    inteiro na janela de 512 tokens e é onde o tom editorial está concentrado. Com `texto`, o
    corpo integral é enviado e truncado no limite — a resposta marca cada linha truncada.

    `por_uf` cruza o rótulo com as UFs citadas na matéria. Uma matéria que cita três UFs conta
    para as três, por isso a soma de `materias` em `por_uf` passa do total analisado. O campo
    `saldo` é `(positivas − negativas) / matérias`.

    **O resultado não entra no cálculo do índice de prioridade, em nenhuma hipótese.** Mede o
    tom da cobertura de imprensa, que é atenção editorial, não situação do território — é a
    ressalva do risco 8.6 do Project Charter, e vem repetida no campo `aviso` de cada resposta.

    É POST, não GET, por duas razões: a chamada é computação sob demanda, não leitura de
    recurso, e assim nenhum intermediário a trata como resposta cacheável.

    Erros: **422** se `campo` for desconhecido, **404** se o filtro não casar com nenhuma
    matéria, **503** se o modelo não estiver disponível.
    """
    if campo not in nc.CAMPOS_ANALISE:
        raise HTTPException(status_code=422, detail=f"campo deve ser um de {nc.CAMPOS_ANALISE}")

    corpus = noticias()
    filtrado = filtrar_noticias(corpus, fonte=fonte, uf=uf, tema=tema)
    if filtrado.empty:
        raise HTTPException(
            status_code=404,
            detail={"mensagem": "nenhuma matéria satisfaz o filtro, não há o que analisar",
                    "filtros": {"fonte": fonte, "uf": uf, "tema": tema},
                    "total_no_corpus": int(len(corpus))},
        )

    recorte = filtrado.head(limite)
    inicio = time.perf_counter()
    resultados = ml.classificar(nc.texto_para_analise(recorte, campo).tolist())
    decorrido = round(time.perf_counter() - inicio, 2)

    classificadas = []
    por_rotulo = {}
    for (_, materia), analise in zip(recorte.iterrows(), resultados):
        classificadas.append({
            "data": materia["data"].date().isoformat() if pd.notna(materia["data"]) else None,
            "fonte": materia["fonte"],
            "titulo": materia["titulo"],
            "url": texto_ou_nulo(materia["url"]),
            "ufs_citadas": texto_ou_nulo(materia["ufs_citadas"]),
            "temas_ods4": texto_ou_nulo(materia["temas_ods4"]),
            "rotulo": analise["rotulo"],
            "confianca": analise["confianca"],
            "tokens": analise["tokens"],
            "texto_truncado": analise["texto_truncado"],
        })
        por_rotulo[analise["rotulo"]] = por_rotulo.get(analise["rotulo"], 0) + 1

    return {
        "tarefa": ml.MODELOS["sentimento"]["descricao"],
        "modelo": ml.MODELOS["sentimento"]["modelo"],
        "campo_analisado": campo,
        "analisadas": len(classificadas),
        "total_no_corpus": int(len(corpus)),
        "filtros": {"fonte": fonte, "uf": uf, "tema": tema, "campo": campo, "limite": limite},
        "por_rotulo": por_rotulo,
        "por_uf": agregar_por_uf(classificadas),
        "segundos": decorrido,
        "analisado_em": datetime.now().isoformat(timespec="seconds"),
        "aviso": ml.AVISOS["sentimento"],
        "dados": classificadas,
    }


# ---------------------------------------------------------------- execucao direta

if __name__ == "__main__":
    # permite "python api.py" sem decorar a linha de comando do uvicorn
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
