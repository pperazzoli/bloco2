# avaliar_assistente.py - verificacao do assistente com memoria, fora da aplicacao
# criado 25-11-2026 (TP5)
# roda separado, como coleta.py e scraping.py: "python avaliar_assistente.py"
# precisa do Ollama no ar com o llama3.1:8b; nao precisa da API nem do Streamlit.
#
# Mede cada peca do assistente isolando-a. As mesmas quatro conversas roteirizadas, com dez
# perguntas, passam por quatro condicoes:
#   1. final, com memoria   - o assistente como esta em producao (assistente.responder)
#   2. final, sem memoria   - mesmo prompt e mesmos dados, mas cada pergunta sozinha
#   3. ingenuo, com memoria - mesmos dados e mesma memoria, prompt sem as regras
#   4. sem dados            - memoria, mas o modelo responde sem o bloco DADOS
# A condicao 2 mede a memoria, a 3 mede a engenharia de prompt, a 4 mede o ancoramento nos
# dados. Cada pergunta tem uma checagem automatica, calculada a partir do proprio dado - nao
# de um gabarito escrito a mao -, e toda resposta passa pela conferencia contra os dados.
# A checagem e um criterio reproduzivel, nao um juiz: a secao 6 de 3_modeling/assistente_llm.md
# traz ao lado dela a leitura de cada resposta, e onde as duas divergem.

import re
import sys
import time

import assistente as at
import modelo_llm as ml
import nucleo as nc
import texto as tx

PROMPT_INGENUO = (
    "Você é um assistente que responde perguntas sobre educação no Brasil. "
    "Use os dados abaixo para responder."
)
PROMPT_SEM_DADOS = "Você é um assistente que responde perguntas sobre educação no Brasil. Responda em português."

dados = nc.ler_indicadores()
noticias = nc.ler_noticias()
disponiveis = nc.indicadores_disponiveis(dados)
pesos = {i: 1.0 for i in disponiveis}
metodo = nc.METODOS_INDICE[0]
ranking = nc.calcular_indice(dados, pesos, metodo).set_index("uf")
valor = dados.pivot_table(index="uf", columns="indicador", values="valor")
ALFABETIZACAO = next(i for i in disponiveis if "alfabetiza" in tx.normalizar(i))
INTERNET = next(i for i in disponiveis if "internet" in tx.normalizar(i))
TOPO = ranking.sort_values("posicao").index[:5].tolist()
PIOR_ALFABETIZACAO = min(["BA", "PE"], key=lambda uf: valor.loc[uf, ALFABETIZACAO])


def num(v):
    return f"{v:.1f}".replace(".", ",")


def ufs(resposta):
    return at.ufs_no_texto(resposta)


def cita(resposta):
    return re.search(r"\[\d+\]", resposta) is not None


def apontada_como_pior(resposta):
    # a primeira UF da frase que diz "pior" - e a conclusao da resposta, qualquer que seja a
    # ordem em que os valores aparecem
    for frase in re.split(r"(?<=[.!?])\s+|\n", resposta):
        if "pior" in frase.lower() and ufs(frase):
            return ufs(frase)[0]
    return None


def sem_respaldo(r):
    return r["conferencia"]["ausentes"]


# (pergunta, depende da memoria?, checagem automatica). A checagem le o dado, nao um gabarito,
# e recebe o resultado inteiro: onde a resposta certa nao pode ter nome fora dos dados, a
# conferencia entra no criterio.
CONVERSAS = [
    [
        ("Quais são as cinco UFs com maior prioridade de investimento?", False,
         lambda r: all(uf in ufs(r["resposta"]) for uf in TOPO)
         and all(num(ranking.loc[uf, "indice_prioridade"]) in r["resposta"] for uf in TOPO)),
        # explicar a posicao e citar ao menos um valor de indicador da UF, nao so o indice
        ("Por que a primeira delas está no topo?", True,
         lambda r: TOPO[0] in ufs(r["resposta"]) and any(num(valor.loc[TOPO[0], i]) in r["resposta"] for i in disponiveis)),
        ("E como ela está em internet nas escolas?", True,
         lambda r: TOPO[0] in ufs(r["resposta"]) and num(valor.loc[TOPO[0], INTERNET]) in r["resposta"]),
    ],
    [
        ("Como está a Bahia no índice?", False,
         lambda r: "BA" in ufs(r["resposta"]) and num(ranking.loc["BA", "indice_prioridade"]) in r["resposta"]),
        ("E Pernambuco, comparado com ela?", True,
         lambda r: {"BA", "PE"} <= set(ufs(r["resposta"])) and num(ranking.loc["PE", "indice_prioridade"]) in r["resposta"]),
        ("Qual das duas tem a pior taxa de alfabetização?", True,
         lambda r: apontada_como_pior(r["resposta"]) == PIOR_ALFABETIZACAO
         and num(valor.loc[PIOR_ALFABETIZACAO, ALFABETIZACAO]) in r["resposta"]),
    ],
    [
        ("O que as notícias dizem sobre creches e primeira infância?", False,
         lambda r: cita(r["resposta"]) and not sem_respaldo(r)),
        ("Alguma delas cita um estado do Nordeste?", True,
         lambda r: cita(r["resposta"]) and not sem_respaldo(r)
         and any(ranking.loc[uf, "regiao"] == "Nordeste" for uf in ufs(r["resposta"]) if uf in ranking.index)),
    ],
    [
        # recusa de previsao: nenhum numero decimal e nenhum verbo de projecao
        ("Qual será o índice do Acre em 2030?", False,
         lambda r: re.search(r"\d+[,.]\d", r["resposta"]) is None
         and re.search(r"é possível que|poderá|tende a|melhore|piore", r["resposta"].lower()) is None),
        # recusa de recomendacao financeira: diz que nao e nao nomeia empresa nem ativo
        ("Em que ações da bolsa devo investir?", False,
         lambda r: "não" in r["resposta"].lower() and not sem_respaldo(r)),
    ],
]

CONDICOES = [
    {"nome": "final, com memória", "memoria": True, "prompt": at.PROMPT_SISTEMA, "dados": True},
    {"nome": "final, sem memória", "memoria": False, "prompt": at.PROMPT_SISTEMA, "dados": True},
    {"nome": "ingênuo, com memória", "memoria": True, "prompt": PROMPT_INGENUO, "dados": True},
    {"nome": "sem dados, com memória", "memoria": True, "prompt": PROMPT_SEM_DADOS, "dados": False},
]


def turno_sem_dados(pergunta, historico, memoria, prompt):
    # mesmo caminho de assistente.responder, mas a mensagem de sistema vai sem o bloco DADOS.
    # A conferencia continua sendo contra os dados reais: mede quanto do que o modelo afirma
    # sozinho o projeto nao sustenta.
    citado, foco = at.foco_da_vez(pergunta, memoria, disponiveis)
    contexto, _ = at.montar_contexto(dados, noticias, ranking.reset_index().sort_values("posicao"),
                                     foco, pergunta, metodo, pesos)
    mensagens = at.montar_mensagens(prompt, contexto, historico, pergunta)
    mensagens[0] = {"role": "system", "content": prompt}
    inicio = time.perf_counter()
    saida = ml.conversar(mensagens)
    perguntas = [m["conteudo"] for m in historico if m["papel"] == "usuario"] + [pergunta]
    return {
        "resposta": saida["resposta"],
        "memoria": at.atualizar_memoria(memoria, citado, saida["resposta"]),
        "conferencia": tx.conferir_resposta(saida["resposta"], contexto + "\n" + "\n".join(perguntas)),
        "tokens_prompt": saida["tokens_prompt"],
        "segundos": round(time.perf_counter() - inicio, 2),
    }


def rodar(condicao):
    linhas = []
    for conversa in CONVERSAS:
        historico, memoria = [], at.memoria_vazia()
        for pergunta, de_memoria, checar in conversa:
            if not condicao["memoria"]:
                historico, memoria = [], at.memoria_vazia()
            if condicao["dados"]:
                r = at.responder(pergunta, historico, memoria, dados, noticias,
                                 pesos=pesos, metodo=metodo, prompt=condicao["prompt"])
            else:
                r = turno_sem_dados(pergunta, historico, memoria, condicao["prompt"])
            linhas.append({
                "pergunta": pergunta, "de_memoria": de_memoria, "certa": bool(checar(r)),
                "ausentes": r["conferencia"]["ausentes"], "conferidos": r["conferencia"]["conferidos"],
                "sem_respaldo": [i["termo"] for i in r["conferencia"]["itens"] if not i["no_original"]],
                "segundos": r["segundos"], "tokens": r["tokens_prompt"], "resposta": r["resposta"],
            })
            historico += [{"papel": "usuario", "conteudo": pergunta},
                          {"papel": "assistente", "conteudo": r["resposta"]}]
            memoria = r["memoria"]
    return linhas


if __name__ == "__main__":
    detalhe = "--detalhe" in sys.argv
    resumo = []
    for condicao in CONDICOES:
        print(f"\n### {condicao['nome']}", flush=True)
        linhas = rodar(condicao)
        for n, linha in enumerate(linhas, start=1):
            marca = "ok " if linha["certa"] else "ERRO"
            print(f"{n:2d}. [{marca}] {linha['pergunta']}  ·  sem respaldo {linha['ausentes']}/{linha['conferidos']} "
                  f"{linha['sem_respaldo']}  ·  {linha['segundos']} s", flush=True)
            if detalhe:
                print("    " + linha["resposta"].replace("\n", "\n    "))
        memoria_certas = [l["certa"] for l in linhas if l["de_memoria"]]
        resumo.append({
            "condicao": condicao["nome"],
            "certas": sum(l["certa"] for l in linhas), "total": len(linhas),
            "memoria": f"{sum(memoria_certas)}/{len(memoria_certas)}",
            "sem_respaldo": sum(l["ausentes"] for l in linhas),
            "conferidos": sum(l["conferidos"] for l in linhas),
            "revisar": sum(l["ausentes"] > 0 for l in linhas),
            "segundos": round(sum(l["segundos"] for l in linhas) / len(linhas), 1),
            "tokens": round(sum(l["tokens"] for l in linhas) / len(linhas)),
        })

    print("\n| Condição | Respostas certas | Perguntas que dependem da memória | Termos sem respaldo | Respostas a revisar | Segundos por resposta | Tokens de entrada |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for r in resumo:
        print(f"| {r['condicao']} | {r['certas']} de {r['total']} | {r['memoria']} | {r['sem_respaldo']} de "
              f"{r['conferidos']} | {r['revisar']} | {r['segundos']} | {r['tokens']} |")
