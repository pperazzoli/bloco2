# scraping.py - extracao de conteudo da web com beautiful soup
# roda separado da aplicacao: "python scraping.py"
# grava os resultados em data/raw (bruto) e data/processed (tratado)
# criado 21-09-2026
# edited 21-09-2026: nenhuma pagina e baixada antes de consultar o robots.txt do host

import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import pandas as pd
import requests
from bs4 import BeautifulSoup

import texto as tx

RAIZ = Path(__file__).parent
BRUTO = RAIZ / "data" / "raw"
TRATADO = RAIZ / "data" / "processed"

AGENTE = "bussola-esg-educacao"
CABECALHO = {"User-Agent": f"Mozilla/5.0 (compatible; {AGENTE}/1.0; trabalho academico)"}
PAUSA = 0.4          # intervalo minimo, usado quando o host nao pede um maior
TEMPO_LIMITE = 30

# fonte 1: raspagem do html paginado da editoria de educacao
AGENCIA = "https://agenciabrasil.ebc.com.br"
PAGINAS_AGENCIA = 5

# fontes 2 a 4: raspagem do xml de sindicacao das proprias paginas
FEEDS = [
    ("Todos Pela Educacao", "https://todospelaeducacao.org.br/feed/"),
    ("GIFE", "https://gife.org.br/feed/"),
    ("Observatorio do Terceiro Setor", "https://observatorio3setor.org.br/feed/"),
]

MESES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# ------------------------------------------------------------------ robots.txt

REGRAS = {}          # host -> RobotFileParser ja lido
ULTIMO_ACESSO = {}   # host -> instante da ultima requisicao ao host
AUDITORIA = []       # uma linha por host consultado, vira csv no fim
RECUSADAS = []       # urls que o robots.txt proibiu


def host_de(url):
    partes = urlparse(url)
    return f"{partes.scheme}://{partes.netloc}"


def ler_robots(host):
    # busca com o nosso proprio user-agent, o que o RobotFileParser.read() nao faz
    leitor = RobotFileParser()
    leitor.set_url(f"{host}/robots.txt")
    endereco = f"{host}/robots.txt"
    try:
        resposta = requests.get(endereco, headers=CABECALHO, timeout=TEMPO_LIMITE)
    except Exception as erro:
        # sem resposta, a postura conservadora e nao raspar
        leitor.disallow_all = True
        politica = f"robots.txt inacessivel ({type(erro).__name__}), coleta suspensa"
        status = 0
    else:
        status = resposta.status_code
        if status in (401, 403):
            leitor.disallow_all = True
            politica = "acesso ao robots.txt negado, coleta suspensa"
        elif 400 <= status < 500:
            leitor.allow_all = True
            politica = "sem robots.txt publicado, coleta liberada"
        elif status >= 500:
            leitor.disallow_all = True
            politica = "erro no servidor do robots.txt, coleta suspensa"
        else:
            leitor.parse(resposta.text.splitlines())
            politica = "regras do robots.txt aplicadas"

    espera = leitor.crawl_delay(AGENTE) if status == 200 else None
    AUDITORIA.append(
        {
            "host": host,
            "robots_url": endereco,
            "status_http": status,
            "politica": politica,
            "crawl_delay_s": espera if espera is not None else PAUSA,
            "verificado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )
    return leitor


def regras_de(url):
    host = host_de(url)
    if host not in REGRAS:
        REGRAS[host] = ler_robots(host)
    return REGRAS[host]


def permitido(url):
    return regras_de(url).can_fetch(AGENTE, url)


def intervalo(url):
    pedido = regras_de(url).crawl_delay(AGENTE)
    return max(PAUSA, float(pedido)) if pedido else PAUSA


def aguardar(url):
    host = host_de(url)
    desde = time.monotonic() - ULTIMO_ACESSO.get(host, 0.0)
    resto = intervalo(url) - desde
    if resto > 0:
        time.sleep(resto)
    ULTIMO_ACESSO[host] = time.monotonic()


# ------------------------------------------------------------------ coleta


def baixar(url, parser="html.parser"):
    # ponto unico de saida para a rede: tudo passa pelo robots.txt e pelo intervalo
    if not permitido(url):
        RECUSADAS.append(url)
        return None
    aguardar(url)
    resposta = requests.get(url, headers=CABECALHO, timeout=TEMPO_LIMITE)
    resposta.raise_for_status()
    resposta.encoding = "utf-8"
    return BeautifulSoup(resposta.text, parser)


def limpar(valor):
    return re.sub(r"\s+", " ", str(valor)).strip()


def corpo_do_artigo(url):
    # heuristica unica para os quatro sites: paragrafos longos do documento ja limpo
    try:
        pagina = baixar(url)
    except Exception:
        return ""
    if pagina is None:
        return ""
    for lixo in pagina(["script", "style", "nav", "footer", "header", "form", "aside"]):
        lixo.decompose()
    paragrafos = [limpar(p.get_text(" ")) for p in pagina.find_all("p")]
    return " ".join(p for p in paragrafos if len(p) >= 80)


def data_agencia(bruta):
    # formato do site: "ter, 08/09/2026 - 06:30"
    achado = re.search(r"(\d{2})/(\d{2})/(\d{4})", bruta or "")
    if not achado:
        return None
    dia, mes, ano = achado.groups()
    return f"{ano}-{mes}-{dia}"


def data_feed(bruta):
    # formato rfc 822: "Mon, 21 Sep 2026 13:30:00 +0000"
    achado = re.search(r"(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})", bruta or "")
    if not achado:
        return None
    dia, mes, ano = achado.groups()
    return f"{ano}-{MESES.get(mes.lower(), 1):02d}-{int(dia):02d}"


def coletar_agencia_brasil():
    coletadas = []
    for pagina in range(PAGINAS_AGENCIA):
        endereco_lista = f"{AGENCIA}/educacao?page={pagina}"
        try:
            lista = baixar(endereco_lista)
        except Exception as erro:
            print(f"  aviso: pagina {pagina} da Agencia Brasil falhou ({erro})")
            continue
        if lista is None:
            print(f"  aviso: robots.txt proibe {endereco_lista}")
            continue
        for bloco in lista.select("div.ultima-noticia"):
            titulo = bloco.select_one("a.titulo-noticia")
            if not titulo:
                continue
            endereco = titulo.get("href", "")
            endereco = endereco if endereco.startswith("http") else AGENCIA + endereco
            data = bloco.select_one("span.data")
            editoria = bloco.select_one("a.editoria")
            coletadas.append(
                {
                    "fonte": "Agencia Brasil",
                    "titulo": limpar(titulo.get_text(" ")),
                    "data": data_agencia(data.get_text() if data else ""),
                    "editoria": limpar(editoria.get_text(" ")) if editoria else "",
                    "resumo": "",
                    "url": endereco,
                }
            )
    return coletadas


def coletar_feed(nome, endereco):
    try:
        canal = baixar(endereco, parser="xml")
    except Exception as erro:
        print(f"  aviso: feed de {nome} falhou ({erro})")
        return []
    if canal is None:
        print(f"  aviso: robots.txt proibe {endereco}")
        return []
    coletadas = []
    for item in canal.find_all("item"):
        descricao = item.description.get_text() if item.description else ""
        coletadas.append(
            {
                "fonte": nome,
                "titulo": limpar(item.title.get_text() if item.title else ""),
                "data": data_feed(item.pubDate.get_text() if item.pubDate else ""),
                "editoria": limpar(item.category.get_text()) if item.category else "",
                "resumo": limpar(BeautifulSoup(descricao, "html.parser").get_text(" ")),
                "url": limpar(item.link.get_text() if item.link else ""),
            }
        )
    return coletadas


def textos_ja_coletados():
    # reaproveita o corpo das materias que ja estao no csv: menos carga no site
    arquivo = BRUTO / "noticias_educacao.csv"
    if not arquivo.exists():
        return {}
    anterior = pd.read_csv(arquivo).fillna({"texto": ""})
    return {u: t for u, t in zip(anterior["url"], anterior["texto"]) if str(t).strip()}


def enriquecer(noticias):
    # visita cada materia para trazer o texto integral, que alimenta a nuvem de palavras
    conhecidos = textos_ja_coletados()
    novas = [n for n in noticias if n["url"] not in conhecidos]
    print(f"  {len(noticias) - len(novas)} ja no arquivo, {len(novas)} a baixar")
    if novas:
        segundos = sum(intervalo(n["url"]) for n in novas)
        estimativa = f"{segundos:.0f}s" if segundos < 90 else f"{segundos / 60:.0f} min"
        print(f"  respeitando o crawl-delay de cada host: ~{estimativa}")
    for posicao, noticia in enumerate(noticias, start=1):
        noticia["texto"] = conhecidos.get(noticia["url"]) or corpo_do_artigo(noticia["url"])
        if posicao % 20 == 0 or posicao == len(noticias):
            print(f"  {posicao}/{len(noticias)} materias resolvidas")
    return noticias


def montar_tabela(noticias):
    tabela = pd.DataFrame(noticias).drop_duplicates(subset="url").reset_index(drop=True)
    tabela["texto"] = tabela["texto"].fillna("")
    tabela["resumo"] = [
        resumo or corpo[:300] for resumo, corpo in zip(tabela["resumo"], tabela["texto"])
    ]
    conteudo = tabela["titulo"] + " " + tabela["resumo"] + " " + tabela["texto"]
    tabela["n_palavras"] = conteudo.str.split().str.len()
    tabela["ufs_citadas"] = [";".join(tx.mencoes_uf(t)) for t in conteudo]
    tabela["temas_ods4"] = [";".join(tx.temas_do_texto(t)) for t in conteudo]
    tabela["coletado_em"] = datetime.now(timezone.utc).date().isoformat()
    colunas = [
        "fonte", "data", "titulo", "resumo", "editoria", "ufs_citadas",
        "temas_ods4", "n_palavras", "url", "coletado_em", "texto",
    ]
    return tabela[colunas]


def contagem_para_tabela(coluna, nomes):
    contagem = Counter()
    for celula in coluna:
        contagem.update(item for item in str(celula).split(";") if item)
    return pd.DataFrame(list(contagem.most_common()), columns=nomes)


def main():
    BRUTO.mkdir(parents=True, exist_ok=True)
    TRATADO.mkdir(parents=True, exist_ok=True)

    print("1/5 conferindo o robots.txt de cada host")
    for endereco in [AGENCIA + "/educacao"] + [u for _, u in FEEDS]:
        marca = "permitido" if permitido(endereco) else "PROIBIDO"
        print(f"  {marca:10} {endereco}  (intervalo {intervalo(endereco):g}s)")

    print("2/5 listando materias")
    noticias = coletar_agencia_brasil()
    for nome, endereco in FEEDS:
        noticias += coletar_feed(nome, endereco)
    print(f"  {len(noticias)} materias listadas")

    print("3/5 lendo o texto de cada materia")
    noticias = enriquecer(noticias)

    print("4/5 montando as tabelas")
    tabela = montar_tabela(noticias)
    corpus = tabela["titulo"] + " " + tabela["resumo"] + " " + tabela["texto"]

    print("5/5 gravando arquivos")
    tabela.to_csv(BRUTO / "noticias_educacao.csv", index=False, encoding="utf-8")
    (BRUTO / "noticias_corpus.txt").write_text("\n\n".join(corpus), encoding="utf-8")

    termos = pd.DataFrame(tx.contar_termos(corpus, limite=300), columns=["termo", "frequencia"])
    termos.to_csv(TRATADO / "noticias_termos.csv", index=False, encoding="utf-8")
    contagem_para_tabela(tabela["ufs_citadas"], ["uf", "mencoes"]).to_csv(
        TRATADO / "noticias_por_uf.csv", index=False, encoding="utf-8"
    )
    contagem_para_tabela(tabela["temas_ods4"], ["tema_ods4", "noticias"]).to_csv(
        TRATADO / "noticias_por_tema.csv", index=False, encoding="utf-8"
    )
    pd.DataFrame(AUDITORIA).to_csv(
        TRATADO / "robots_verificacao.csv", index=False, encoding="utf-8"
    )

    if RECUSADAS:
        print(f"  {len(RECUSADAS)} endereco(s) recusados pelo robots.txt:")
        for endereco in RECUSADAS[:10]:
            print(f"    {endereco}")

    print(
        f"ok: {len(tabela)} noticias | {tabela['fonte'].nunique()} fontes | "
        f"{int(tabela['n_palavras'].sum())} palavras | "
        f"{len(RECUSADAS)} recusas do robots.txt"
    )


if __name__ == "__main__":
    main()
