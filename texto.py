# texto.py - utilidades de texto puro, sem dependencia de streamlit
# usado tanto pelo scraping.py (offline) quanto pela aplicacao (online)
# criado 21-09-2026

import re
import unicodedata
from collections import Counter

# lista propria de stopwords em portugues, evita dependencia de corpus externo
STOPWORDS = frozenset(
    """
a as o os um uma uns umas de do da dos das em no na nos nas por pelo pela pelos pelas
para com sem sob sobre entre ate apos ante contra desde perante tras e ou mas porem
porque pois que se quando onde como qual quais quanto quantos quem cujo cuja
ao aos aquele aquela aqueles aquelas aquilo este esta estes estas isto esse essa
esses essas isso ele ela eles elas eu tu nos vos me te lhe lhes meu minha seus sua suas
nosso nossa nossos nossas dele dela deles delas
ser sou somos sao era eram foi foram sera serao sendo sido
estar esta estao estava estavam esteve estiveram
ter tem tinha tinham teve tiveram tera terao tendo tido
haver havia houve houveram
fazer faz fez fazem fazendo feito feita feitos feitas
poder pode podem podia podiam podera poderao
dizer diz disse dizem segundo conforme
mais menos muito muita muitos muitas pouco pouca poucos poucas
todo toda todos todas outro outra outros outras mesmo mesma mesmos mesmas
tambem ainda nao sim apenas tanto cada qualquer nenhum nenhuma
depois antes agora hoje ontem amanha sempre nunca aqui ali
durante alem bem assim entao portanto contudo entretanto
ano anos mes meses dia dias hora horas semana semanas
primeiro primeira segundo segunda terceiro terceira ultimo ultima proximo proxima
mil milhao milhoes bilhao bilhoes cento
foto agencia leia veja saiba fonte credito imagem post apareceu
nesta neste nessa nesse pessoas informacoes parte forma deve devem diferentes
duas dois tres maior menor meio tempo partir sobretudo caso casos vez vezes
janeiro fevereiro marco abril maio junho julho agosto setembro outubro novembro dezembro
""".split()
)

# termos genericos do dominio: aparecem em quase toda materia e afogam a nuvem
STOPWORDS_DOMINIO = frozenset(
    """
educacao ensino escola escolas aluno alunos estudante estudantes professor professores
brasil brasileiro brasileira brasileiros pais nacional
""".split()
)

# nomes acentuados de proposito: "Para" sem acento colide com a preposicao
UFS = {
    "Acre": "AC", "Alagoas": "AL", "Amapá": "AP", "Amazonas": "AM", "Bahia": "BA",
    "Ceará": "CE", "Distrito Federal": "DF", "Espírito Santo": "ES", "Goiás": "GO",
    "Maranhão": "MA", "Mato Grosso do Sul": "MS", "Mato Grosso": "MT",
    "Minas Gerais": "MG", "Pará": "PA", "Paraíba": "PB", "Paraná": "PR",
    "Pernambuco": "PE", "Piauí": "PI", "Rio de Janeiro": "RJ",
    "Rio Grande do Norte": "RN", "Rio Grande do Sul": "RS", "Rondônia": "RO",
    "Roraima": "RR", "Santa Catarina": "SC", "São Paulo": "SP",
    "Sergipe": "SE", "Tocantins": "TO",
}

SIGLAS = frozenset(UFS.values())
# sem acento "Para" vira a preposicao mais comum da lingua, entao exige a acentuacao
AMBIGUOS = frozenset({"Pará"})

# temas da ods 4 e os termos que sinalizam cada um no texto da materia
TEMAS_ODS4 = {
    "4.1 conclusao e aprendizagem": ["ideb", "aprendizagem", "alfabetizacao", "saeb", "evasao", "abandono", "conclusao", "pisa"],
    "4.2 primeira infancia": ["creche", "pre-escola", "infantil", "primeira infancia"],
    "4.3 tecnico e superior": ["tecnico", "superior", "universidade", "enem", "prouni", "fies", "sisu", "graduacao"],
    "4.5 equidade": ["equidade", "desigualdade", "inclusao", "raca", "genero", "indigena", "quilombola", "deficiencia"],
    "4.a infraestrutura": ["infraestrutura", "internet", "conectividade", "computador", "predio", "acessibilidade", "merenda"],
    "4.c docentes": ["docente", "formacao de professor", "magisterio", "carreira docente", "piso salarial"],
    "financiamento": ["fundeb", "orcamento", "investimento", "verba", "financiamento", "repasse", "emenda"],
}

PALAVRA = re.compile(r"[a-z][a-z-]{2,}")
# sigla de uf so conta entre parenteses ou barra, como o jornalismo costuma escrever
SIGLA_ISOLADA = re.compile(r"[(/-]\s*([A-Z]{2})\s*[)/,.]")


def sem_acento(valor):
    normalizado = unicodedata.normalize("NFKD", str(valor))
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def normalizar(valor):
    return sem_acento(valor).lower()


def tokenizar(conteudo, extras=frozenset(), manter_dominio=False):
    bloqueadas = set(STOPWORDS) | {normalizar(p) for p in extras}
    if not manter_dominio:
        bloqueadas |= set(STOPWORDS_DOMINIO)
    achadas = PALAVRA.findall(normalizar(conteudo))
    return [p for p in achadas if len(p) > 3 and p not in bloqueadas]


def contar_termos(conteudos, limite=200, extras=frozenset(), manter_dominio=False):
    contagem = Counter()
    for conteudo in conteudos:
        contagem.update(tokenizar(conteudo, extras, manter_dominio))
    return contagem.most_common(limite)


def mencoes_uf(conteudo):
    achadas = set()
    bruto = str(conteudo)
    plano = normalizar(bruto)
    for nome, sigla in UFS.items():
        # os ambiguos so contam acentuados, os demais valem com ou sem acento
        alvo, agulha = (bruto, nome) if nome in AMBIGUOS else (plano, normalizar(nome))
        if re.search(rf"\b{re.escape(agulha)}\b", alvo, flags=re.IGNORECASE):
            achadas.add(sigla)
    achadas.update(s for s in SIGLA_ISOLADA.findall(bruto) if s in SIGLAS)
    return sorted(achadas)


def temas_do_texto(conteudo):
    plano = normalizar(conteudo)
    return sorted(t for t, termos in TEMAS_ODS4.items() if any(k in plano for k in termos))
