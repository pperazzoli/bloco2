# texto.py - utilidades de texto puro, sem dependencia de streamlit
# usado tanto pelo scraping.py (offline) quanto pela aplicacao (online)
# criado 21-09-2026
# edited 16-11-2026 (TP4): entrou conferir_resumo, que compara um resumo gerado por modelo
# com o texto de origem. Mora aqui, e nao em modelo_llm.py, porque nao usa modelo nenhum:
# e comparacao lexica, da mesma familia de mencoes_uf e temas_do_texto.

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


# ---------------------------------------------------------------- conferencia de resumo

# Numeros por extenso e ordinais. "um" e "uma" ficam de fora porque sao artigo antes de
# serem numero, e "segundo" tambem: em texto jornalistico quase sempre significa "conforme".
NUMEROS_POR_EXTENSO = frozenset(
    """
dois duas tres quatro cinco seis sete oito nove dez onze doze treze catorze quatorze quinze
dezesseis dezessete dezoito dezenove vinte trinta quarenta cinquenta sessenta setenta
oitenta noventa cem cento duzentos trezentos quatrocentos quinhentos seiscentos setecentos
oitocentos novecentos mil milhao milhoes bilhao bilhoes dezena dezenas centena centenas
metade dobro triplo terco
primeiro primeira terceiro terceira quinto quinta sexto sexta setimo setima oitavo oitava
nono nona decimo decima ultimo ultima unico unica
""".split()
)

# Datas que um modelo gerativo costuma inventar quando o texto nao as traz.
EXPRESSOES_DE_DATA = frozenset(
    """
segunda-feira terca-feira quarta-feira quinta-feira sexta-feira sabado domingo
janeiro fevereiro marco abril maio junho julho agosto setembro outubro novembro dezembro
ontem hoje amanha
""".split()
)

# token com hifen preservado, para que "quarta-feira" nao vire "quarta"
TOKEN = re.compile(r"\w+(?:-\w+)*", re.UNICODE)
DIGITOS = re.compile(r"\d[\d.,]*\d|\d")

# nome proprio: palavra iniciada por maiuscula, encadeando as seguintes e os conectores
# que ficam no meio de nome composto - "Rio Grande do Sul" conta como um item so
_MAIUSCULA = r"[A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ]"
_PROPRIA = rf"{_MAIUSCULA}\w*(?:-\w+)*"
_CONECTOR = r"(?:de|do|da|dos|das|e|em|no|na|nos|nas)"
NOME_PROPRIO = re.compile(rf"{_PROPRIA}(?:\s+(?:{_CONECTOR}\s+)?{_PROPRIA})*")

RESSALVA_CONFERENCIA = (
    "Comparação léxica, não semântica: confere se o termo aparece no texto de origem, não se "
    "o resumo é fiel ao sentido dele. Erra de propósito para o lado de apontar demais — um "
    "termo apontado que está no texto custa um olhar, um termo inventado que passa custa uma "
    "afirmação falsa."
)


# lista curta de proposito: usar STOPWORDS inteira comeria "São" de "São Paulo", porque
# "sao" esta la como forma do verbo ser
ARTIGOS_INICIAIS = frozenset("o a os as um uma uns umas no na do da de em ao aos".split())


def _sem_artigo_inicial(grupo):
    # "O Itaú Social" no comeco da frase entra com o artigo colado; o nome e "Itaú Social"
    partes = grupo.strip().split()
    while len(partes) > 1 and normalizar(partes[0]) in ARTIGOS_INICIAIS:
        partes.pop(0)
    return " ".join(partes)


def _aparece(termo, plano):
    # busca por palavra inteira: "Estado" nao casa com "estadual", e e para nao casar mesmo
    alvo = normalizar(termo).strip()
    if not alvo:
        return True
    return re.search(rf"(?<!\w){re.escape(alvo)}(?!\w)", plano) is not None


def conferir_resumo(resumo, original):
    """Confere se cada afirmacao verificavel do resumo aparece no texto de origem.

    Nao usa modelo: procura no resumo os tres tipos de termo que um modelo gerativo inventa
    com mais frequencia - numero, data e nome proprio - e checa cada um contra o original.
    Devolve a lista conferida, com os ausentes primeiro, e a contagem.
    """
    plano = normalizar(original)
    itens = []
    vistos = set()

    def registrar(tipo, termo):
        limpo = str(termo).strip()
        chave = (tipo, normalizar(limpo))
        if not limpo or chave in vistos:
            return
        vistos.add(chave)
        itens.append({"tipo": tipo, "termo": limpo, "no_original": _aparece(limpo, plano)})

    for numero in DIGITOS.findall(resumo):
        registrar("número", numero)

    for token in TOKEN.findall(resumo):
        achatado = normalizar(token)
        if achatado in NUMEROS_POR_EXTENSO:
            registrar("número", token)
        elif achatado in EXPRESSOES_DE_DATA:
            registrar("data", token)

    for grupo in NOME_PROPRIO.findall(resumo):
        limpo = _sem_artigo_inicial(grupo)
        achatado = normalizar(limpo)
        # descarta o que ja foi contado como numero ou data e a maiuscula de inicio de frase
        if len(limpo) < 3 or achatado in STOPWORDS:
            continue
        if achatado in NUMEROS_POR_EXTENSO or achatado in EXPRESSOES_DE_DATA:
            continue
        registrar("nome próprio", limpo)

    ausentes = sum(1 for item in itens if not item["no_original"])
    itens.sort(key=lambda item: (item["no_original"], item["tipo"], normalizar(item["termo"])))
    return {
        "situacao": "revisar" if ausentes else "sem divergência",
        "conferidos": len(itens),
        "ausentes": ausentes,
        "itens": itens,
        "metodo": "números, datas e nomes próprios do resumo procurados no texto de origem",
        "ressalva": RESSALVA_CONFERENCIA,
    }
