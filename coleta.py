import json  # edited 21-09-2026: usado no tratamento da malha territorial
from pathlib import Path

import pandas as pd
import requests

IBGE = "https://servicodados.ibge.gov.br/api/v3/agregados"
# edited 21-09-2026: os dados passaram para data/, o diretorio tdsp guarda so a documentacao
DESTINO = Path(__file__).parent / "data" / "processed"
# edited 21-09-2026: malha das ufs para o mapa da aplicacao
BRUTO = Path(__file__).parent / "data" / "raw"
MALHA = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
    "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF"
)
AUSENTES = {"-", "..", "...", "X", "-1", ""}

INDICADORES = [
    ("4.a.1", "Escolas de ensino médio com internet para fins pedagógicos", 7783, 11086, "812[41117]"),
    ("4.a.1", "Escolas de ensino médio com computador para fins pedagógicos", 7783, 11086, "812[41118]"),
    ("4.a.1", "Escolas de ensino médio com infraestrutura acessível", 7783, 11086, "812[41119]"),
    ("4.1.2", "Taxa de conclusão do ensino médio (20 a 22 anos)", 4731, 4721, "582[59997]"),
    ("4.2.2", "Taxa de participação no ensino organizado (5 anos)", 4734, 4796, "2[6794]"),
    ("4.6.1", "Taxa de alfabetização (15 anos ou mais)", 10436, 2513, "58[95253]"),
    ("4.c.1", "Docentes do ensino médio com formação adequada", 6676, 9610, "2[6794]|813[41125]"),
]

FONTES = [
    {
        "fonte": "IBGE - API de Agregados (SIDRA)",
        "tipo_de_dado": "Quantitativo contínuo (percentuais)",
        "acesso": "API REST, sem chave",
        "granularidade": "Unidade da Federação",
        "objetivo_de_uso": "Fonte principal: indicadores oficiais de monitoramento da ODS 4 que compõem o índice de prioridade",
        "status": "Coletado",
    },
    {
        "fonte": "IBGE - API de Localidades",
        "tipo_de_dado": "Categórico nominal (códigos e nomes)",
        "acesso": "API REST, sem chave",
        "granularidade": "UF e região",
        "objetivo_de_uso": "Tabela de domínio territorial: chave de junção entre as fontes e agrupamento por região",
        "status": "Coletado",
    },
    # edited 21-09-2026: fontes de conteudo web raspadas com beautiful soup em scraping.py
    {
        "fonte": "Agencia Brasil - editoria de Educacao",
        "tipo_de_dado": "Texto nao estruturado (titulo, data, corpo da materia)",
        "acesso": "Raspagem de HTML paginado com Beautiful Soup",
        "granularidade": "Materia jornalistica",
        "objetivo_de_uso": "Agenda publica da educacao: nuvem de palavras, temas da ODS 4 e mencoes por UF",
        "status": "Coletado",
    },
    {
        "fonte": "Todos Pela Educacao",
        "tipo_de_dado": "Texto nao estruturado (titulo, resumo, corpo da materia)",
        "acesso": "Raspagem do XML de sindicacao com Beautiful Soup",
        "granularidade": "Materia e artigo de opiniao",
        "objetivo_de_uso": "Leitura do terceiro setor sobre as metas educacionais",
        "status": "Coletado",
    },
    {
        "fonte": "GIFE",
        "tipo_de_dado": "Texto nao estruturado (titulo, resumo, corpo da materia)",
        "acesso": "Raspagem do XML de sindicacao com Beautiful Soup",
        "granularidade": "Materia sobre investimento social privado",
        "objetivo_de_uso": "Pauta do investidor social privado, publico primario da aplicacao",
        "status": "Coletado",
    },
    {
        "fonte": "Observatorio do Terceiro Setor",
        "tipo_de_dado": "Texto nao estruturado (titulo, resumo, corpo da materia)",
        "acesso": "Raspagem do XML de sindicacao com Beautiful Soup",
        "granularidade": "Materia e chamada de projeto social",
        "objetivo_de_uso": "Projetos e organizacoes executoras em campo",
        "status": "Coletado",
    },
    {
        "fonte": "IBGE - API de Malhas Territoriais",
        "tipo_de_dado": "Geoespacial (poligonos das UFs em GeoJSON)",
        "acesso": "API REST, sem chave",
        "granularidade": "Unidade da Federacao",
        "objetivo_de_uso": "Base do mapa coropletico da aplicacao",
        "status": "Coletado",
    },
    {
        "fonte": "INEP - Censo Escolar e IDEB",
        "tipo_de_dado": "Misto: binário (infraestrutura por escola), quantitativo (matrículas), ordinal (IDEB)",
        "acesso": "Download de arquivo CSV/ZIP",
        "granularidade": "Escola e município",
        "objetivo_de_uso": "Descer a análise ao nível municipal, que a API do IBGE não cobre",
        "status": "Previsto",
    },
    {
        "fonte": "Banco Mundial - World Development Indicators",
        "tipo_de_dado": "Quantitativo contínuo (percentuais)",
        "acesso": "API REST, sem chave",
        "granularidade": "País",
        "objetivo_de_uso": "Benchmark internacional para dimensionar o problema no reporte ESG",
        "status": "Previsto",
    },
]


def numero(valor):
    texto = str(valor).strip()
    if texto in AUSENTES:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def coletar_ufs():
    dados = requests.get(
        "https://servicodados.ibge.gov.br/api/v1/localidades/estados", timeout=60
    ).json()
    return pd.DataFrame(
        [
            {"cod_uf": str(uf["id"]), "uf": uf["sigla"], "regiao": uf["regiao"]["nome"]}
            for uf in dados
        ]
    )


def coletar_indicador(codigo, titulo, agregado, variavel, classificacao):
    url = (
        f"{IBGE}/{agregado}/periodos/-1/variaveis/{variavel}"
        f"?localidades=N3[all]&classificacao={classificacao}"
    )
    bruto = requests.get(url, timeout=60).json()
    return pd.DataFrame(
        [
            {
                "indicador_ods": codigo,
                "indicador": titulo,
                "cod_uf": str(serie["localidade"]["id"]),
                "ano": int(ano),
                "valor": numero(valor),
                "unidade": "%",
                "fonte": "IBGE - API de Agregados",
                "fonte_url": url,
            }
            for item in bruto
            for resultado in item["resultados"]
            for serie in resultado["series"]
            for ano, valor in serie["serie"].items()
        ]
    )


# edited 21-09-2026
def area_assinada(anel):
    return sum(
        anel[i][0] * anel[i + 1][1] - anel[i + 1][0] * anel[i][1]
        for i in range(len(anel) - 1)
    ) / 2


# edited 21-09-2026
def sentido_horario(geometria):
    # o ibge entrega aneis antihorarios, e o motor de mapas do plotly le esse
    # sentido como "todo o globo menos o poligono"; aqui o sentido e invertido
    def anel(pontos, externo):
        area = area_assinada(pontos)
        inverter = (externo and area > 0) or (not externo and area < 0)
        return pontos[::-1] if inverter else pontos

    if geometria["type"] == "Polygon":
        geometria["coordinates"] = [
            anel(r, i == 0) for i, r in enumerate(geometria["coordinates"])
        ]
    elif geometria["type"] == "MultiPolygon":
        geometria["coordinates"] = [
            [anel(r, i == 0) for i, r in enumerate(poligono)]
            for poligono in geometria["coordinates"]
        ]
    return geometria


# edited 21-09-2026
def coletar_malha():
    resposta = requests.get(MALHA, timeout=60)
    resposta.raise_for_status()
    malha = resposta.json()
    for feicao in malha["features"]:
        sentido_horario(feicao["geometry"])
    return json.dumps(malha)


def main():
    ufs = coletar_ufs()
    dados = pd.concat([coletar_indicador(*i) for i in INDICADORES], ignore_index=True)
    dados = dados.merge(ufs, on="cod_uf")

    # edited 21-09-2026: parents=True porque o destino ganhou um nivel
    DESTINO.mkdir(parents=True, exist_ok=True)
    BRUTO.mkdir(parents=True, exist_ok=True)
    dados.to_csv(DESTINO / "ods4_uf.csv", index=False, encoding="utf-8")
    pd.DataFrame(FONTES).to_csv(DESTINO / "fontes.csv", index=False, encoding="utf-8")
    (BRUTO / "malha_uf.geojson").write_text(coletar_malha(), encoding="utf-8")
    print(f"{len(dados)} linhas | {dados['indicador'].nunique()} indicadores | {dados['uf'].nunique()} UFs")


if __name__ == "__main__":
    main()
