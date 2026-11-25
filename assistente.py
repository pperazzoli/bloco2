# assistente.py - assistente conversacional com memoria, sobre os dados do projeto
# criado 25-11-2026 (TP5)
#
# Por que este arquivo existe, pela mesma razao de nucleo.py e modelo_llm.py: a conversa tem
# tres partes que nao sao do servidor web nem da interface - a memoria, a montagem do
# contexto de dados e o prompt. Ficam aqui, sem import de fastapi nem de streamlit. api.py
# expoe a conversa em POST /assistente, e a pagina Assistente ESG e cliente dessa rota.
#
# A regra que organiza o arquivo e a do risco 8.4 do Project Charter: o modelo nao calcula.
# Todo numero que ele pode citar chega pronto no bloco DADOS do prompt, apurado por
# nucleo.py - inclusive medias e diferencas, que um modelo de linguagem erra com facilidade.
# Depois a resposta e conferida contra esse mesmo bloco por texto.conferir_resposta.
#
# Memoria em duas camadas, as duas visiveis na tela e apagaveis pelo usuario:
#   - janela: as ultimas mensagens vao inteiras ao modelo, que assim entende "e o Para?" ou
#     "a primeira delas" pelo historico;
#   - foco: UFs, regioes, temas da ODS 4 e indicadores citados ate aqui, extraidos sem
#     modelo. E o foco que decide QUE DADOS entram no prompt da vez - sem ele, "e comparada
#     com Pernambuco?" chegaria ao modelo sem os indicadores da UF de que se falava antes.
# O servidor nao guarda nada entre chamadas: a memoria viaja na requisicao e volta
# atualizada na resposta. Vive na sessao do usuario e morre com ela, como o upload de CSV.

import re
import time
from datetime import datetime

import pandas as pd

import modelo_llm as ml
import nucleo as nc
import texto as tx

JANELA = 6              # mensagens do historico que voltam ao modelo: as tres ultimas trocas
MAX_FOCO_UFS = 3        # UFs cujos indicadores entram no prompt da vez; com 4 o contexto
                        # passou de 5 mil tokens e o modelo deixou de achar dado que estava la
MAX_MEMORIA = {"ufs": 6, "regioes": 2, "temas": 2, "indicadores": 3}
MAX_NOTICIAS = 4        # materias do corpus por resposta
LEAD = 360              # caracteres do resumo de cada materia que vao ao prompt
LIMITE_MENSAGEM = 2000  # caracteres de cada mensagem antiga que voltam ao modelo

REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]
NOME_DA_UF = {sigla: nome for nome, sigla in tx.UFS.items()}

# palavras que pedem comparacao. O bloco de comparacao so entra quando a pergunta cita UF ou
# usa uma delas: em "por que a primeira esta no topo?" ele era ruido e piorava a resposta.
COMPARACAO = re.compile(
    r"\b(compar\w*|versus|entre|das duas|dos dois|das tres|dos tres|qual das|qual dos|"
    r"melhor|pior|mais|menos|diferenca|frente|enquanto)\b"
)

# termos da pergunta que apontam para cada indicador, sem acento. A chave e um trecho do nome
# do indicador, para nao repetir aqui o nome exato que vem do csv.
TERMOS_DE_INDICADOR = {
    "conclusao do ensino medio": ["conclusao", "concluir", "concluem"],
    "participacao no ensino organizado": ["participacao", "pre-escola", "pre escola", "5 anos", "cinco anos"],
    "alfabetizacao": ["alfabetiza", "analfabet"],
    "com computador": ["computador", "infraestrutura"],
    "infraestrutura acessivel": ["acessivel", "acessibilidade", "infraestrutura"],
    "com internet": ["internet", "conectividade", "infraestrutura"],
    "docentes": ["docente", "professor", "formacao"],
}

# os temas da pergunta usam o dicionario da coleta com duas trocas: "investimento" sai, porque
# quase toda pergunta deste painel fala em investimento, e "superior" vira "ensino superior",
# senao "acima da media" e "indice superior" marcariam o tema 4.3.
_TROCAS = {"investimento": None, "superior": "ensino superior"}
TEMAS_DA_PERGUNTA = {
    tema: [_TROCAS.get(t, t) for t in termos if _TROCAS.get(t, t)]
    for tema, termos in tx.TEMAS_ODS4.items()
}

# A engenharia de prompt do projeto. Cada regra responde a uma falha observada ou a uma regra
# do Project Charter; a medicao de cada versao esta em 3_modeling/assistente_llm.md.
PROMPT_SISTEMA = """Você é o assistente da Bússola ESG Educação, aplicação que ajuda analistas de investimento social privado a decidir onde investir em educação básica no Brasil, com base nos indicadores oficiais da ODS 4.

Regras — siga todas:
1. Responda só com o que está no bloco DADOS abaixo. Se a resposta não estiver nos DADOS, diga que os dados do projeto não cobrem isso.
2. Nunca calcule, estime, arredonde nem projete números, e não faça previsões. Copie cada número exatamente como aparece nos DADOS, com vírgula decimal.
3. Ao usar uma notícia, cite-a pelo número entre colchetes, como [2]. Não invente notícias, títulos, fontes, pessoas nem instituições.
4. O índice de prioridade mede carência e prioridade de investimento, nunca o mérito de um território. Quanto maior o índice, maior a prioridade. Para explicar a posição de uma UF, mostre os indicadores em que ela está abaixo da média, com o valor da UF e a média.
5. Notícias mostram a pauta da imprensa; não medem a situação do território.
6. Não faça recomendação de investimento financeiro, como ações, fundos ou empresas: você apoia a priorização de investimento social em educação.
7. Use o histórico da conversa para entender referências como "ela", "essas UFs" ou "a primeira".
8. Nos sete indicadores, valor maior é melhor: o menor valor é a pior situação. Para dizer qual UF está pior ou melhor, use as linhas "Pior situação" e "Melhor situação" dos DADOS, sem comparar números por conta própria.
9. Responda em português do Brasil, de forma direta, em até 180 palavras. Ao citar uma UF, use o nome e a sigla, com o artigo certo: o Acre (AC), o Pará (PA), a Bahia (BA), Pernambuco (PE). Use lista quando comparar territórios."""


# ---------------------------------------------------------------- o que a pergunta cita

def _posicoes_de_uf(texto):
    # (posicao, sigla) de cada mencao, para preservar a ordem: "a primeira delas" e a
    # primeira citada. Nome longo antes do curto, para que "Mato Grosso do Sul" nao conte
    # tambem como "Mato Grosso". A sigla isolada vale em maiusculas - "e o PA?".
    bruto = str(texto)
    plano = tx.normalizar(bruto)
    achados, ocupado = [], []
    for nome in sorted(tx.UFS, key=len, reverse=True):
        alvo, agulha = (bruto, nome) if nome in tx.AMBIGUOS else (plano, tx.normalizar(nome))
        for achado in re.finditer(rf"\b{re.escape(agulha)}\b", alvo, flags=re.IGNORECASE):
            if any(inicio <= achado.start() < fim for inicio, fim in ocupado):
                continue
            ocupado.append((achado.start(), achado.end()))
            achados.append((achado.start(), tx.UFS[nome]))
    for achado in re.finditer(r"\b[A-Z]{2}\b", bruto):
        if achado.group(0) in tx.SIGLAS:
            achados.append((achado.start(), achado.group(0)))
    return achados


def _em_ordem(pares):
    vistos, saida = set(), []
    for _, item in sorted(pares):
        if item not in vistos:
            vistos.add(item)
            saida.append(item)
    return saida


def ufs_no_texto(texto):
    return _em_ordem(_posicoes_de_uf(texto))


def regioes_no_texto(texto):
    # "Rio Grande do Sul" termina em nome de regiao: os nomes de UF sao apagados antes da
    # busca, trocados por espacos do mesmo tamanho para nao deslocar as posicoes
    plano = tx.normalizar(texto)
    for nome in tx.UFS:
        plano = re.sub(rf"\b{re.escape(tx.normalizar(nome))}\b", lambda m: " " * len(m.group(0)), plano)
    pares = []
    for regiao in REGIOES:
        achado = re.search(rf"\b{re.escape(tx.normalizar(regiao))}\b", plano)
        if achado:
            pares.append((achado.start(), regiao))
    return _em_ordem(pares)


def temas_no_texto(texto):
    plano = tx.normalizar(texto)
    pares = []
    for tema, termos in TEMAS_DA_PERGUNTA.items():
        posicoes = [plano.find(t) for t in termos if t in plano]
        codigo = tema.split()[0]
        if re.search(rf"(?<![\w.]){re.escape(codigo)}(?![\w.])", plano):
            posicoes.append(plano.find(codigo))
        if posicoes:
            pares.append((min(posicoes), tema))
    return _em_ordem(pares)


def indicadores_no_texto(texto, disponiveis):
    plano = tx.normalizar(texto)
    pares = []
    for nome in disponiveis:
        nome_plano = tx.normalizar(nome)
        for trecho, termos in TERMOS_DE_INDICADOR.items():
            if trecho not in nome_plano:
                continue
            # so o inicio da palavra tem fronteira: "alfabetiza" casa com "alfabetizacao",
            # e "5 anos" nao casa dentro de "15 anos"
            posicoes = [a.start() for t in termos
                        for a in [re.search(rf"(?<!\w){re.escape(t)}", plano)] if a]
            if posicoes:
                pares.append((min(posicoes), nome))
    return _em_ordem(pares)


# ---------------------------------------------------------------- memoria

def memoria_vazia():
    return {"ufs": [], "regioes": [], "temas": [], "indicadores": []}


def _juntar(*listas, limite):
    vistos, saida = set(), []
    for lista in listas:
        for item in lista:
            if item not in vistos:
                vistos.add(item)
                saida.append(item)
    return saida[:limite]


def foco_da_vez(pergunta, memoria, disponiveis):
    """O que a pergunta cita e o foco que decide os dados do prompt.

    O foco e o que a pergunta cita, primeiro, mais o que a memoria guarda. Assim "e o Para?"
    traz o Para e mantem a UF anterior a mao, para a comparacao que costuma vir em seguida.
    """
    citado = {
        "ufs": ufs_no_texto(pergunta),
        "regioes": regioes_no_texto(pergunta),
        "temas": temas_no_texto(pergunta),
        "indicadores": indicadores_no_texto(pergunta, disponiveis),
    }
    foco = {
        "ufs": _juntar(citado["ufs"], memoria["ufs"], limite=MAX_FOCO_UFS),
        **{tipo: _juntar(citado[tipo], memoria[tipo], limite=MAX_MEMORIA[tipo])
           for tipo in ("regioes", "temas", "indicadores")},
    }
    return citado, foco


def atualizar_memoria(memoria, citado, resposta):
    # UF entra tambem pela resposta, porque e nela que aparece a lista a que a proxima
    # pergunta se refere ("a primeira delas"). Regiao, tema e indicador entram so pela
    # pergunta: sao o assunto que o usuario escolheu, nao o que o modelo mencionou de passagem.
    return {
        "ufs": _juntar(citado["ufs"], ufs_no_texto(resposta), memoria["ufs"], limite=MAX_MEMORIA["ufs"]),
        **{tipo: _juntar(citado[tipo], memoria[tipo], limite=MAX_MEMORIA[tipo])
           for tipo in ("regioes", "temas", "indicadores")},
    }


# ---------------------------------------------------------------- contexto de dados

def _num(valor):
    return f"{valor:.1f}".replace(".", ",")


def _descrever_pesos(pesos):
    if len(set(pesos.values())) <= 1:
        return f"iguais para os {len(pesos)} indicadores"
    return "; ".join(f"{nome}: {peso:g}" for nome, peso in pesos.items() if peso > 0)


def _raizes(texto):
    # plural reduzido ao singular, o bastante para "creches" casar com "creche"
    return {t[:-1] if t.endswith("s") and len(t) > 4 else t for t in tx.tokenizar(texto)}


def _selecionar_noticias(noticias, foco, pergunta):
    # selecao lexica, sem banco vetorial: o corpus tem 105 materias e a secao 6.1 do Data
    # Summary Report ja registrou que filtro basta nesta escala. UF em foco vale 3, tema em
    # foco vale 2, cada palavra da pergunta que aparece no titulo ou no resumo vale 1.
    termos = _raizes(pergunta)
    ufs, temas = set(foco["ufs"]), foco["temas"]
    pontos = []
    for titulo, resumo, citadas, temas_da_materia in noticias[
        ["titulo", "resumo", "ufs_citadas", "temas_ods4"]
    ].fillna("").itertuples(index=False):
        valor = 3 * len(ufs & set(str(citadas).split(";")))
        valor += 2 * sum(tema in str(temas_da_materia) for tema in temas)
        valor += len(termos & _raizes(f"{titulo} {resumo}"))
        pontos.append(valor)
    escolhidas = noticias.assign(pontos=pontos)
    escolhidas = escolhidas[escolhidas["pontos"] >= 2]
    return escolhidas.sort_values(["pontos", "data"], ascending=False).head(MAX_NOTICIAS)


def montar_contexto(dados, noticias, ranking, foco, pergunta, metodo, pesos):
    """Monta o bloco DADOS do prompt e a lista das fontes que ele usou.

    Tudo o que vai aqui foi apurado por nucleo.py - posicao, indice, media e diferenca. O
    modelo so le. As fontes voltam em separado, para a tela exibi-las sem depender de o
    modelo cita-las.
    """
    total = len(ranking)
    por_uf = ranking.set_index("uf")
    disponiveis = nc.indicadores_disponiveis(dados)
    ficha = dados.drop_duplicates("indicador").set_index("indicador")
    media = {i: ranking[i].mean() for i in disponiveis if i in ranking.columns}
    partes = []

    # posicao de cada UF em cada indicador, do menor valor para o maior: o modelo erra ao
    # contar posicao numa lista, entao a posicao tambem chega pronta
    posicao_no_indicador = {
        i: ranking.set_index("uf")[i].rank(method="min").to_dict()
        for i in disponiveis if i in ranking.columns
    }

    partes.append(
        "Dados do projeto Bússola ESG Educação: indicadores oficiais de monitoramento da ODS 4 "
        f"(Educação de Qualidade) para as {total} UFs do Brasil, publicados pelo IBGE.\n\n"
        f"## Índice de Prioridade de Investimento por UF ({total} UFs; escala de 0 a 100: "
        "quanto maior, maior a carência e a prioridade)\n"
        f"Método de normalização: {metodo}. Pesos: {_descrever_pesos(pesos)}. Fonte dos "
        "indicadores: IBGE, API de Agregados, anos de 2024 e 2025.\n"
        + "\n".join(
            f"{linha.posicao}º {NOME_DA_UF.get(linha.uf, linha.uf)} ({linha.uf}), "
            f"{linha.regiao}: {_num(linha.indice_prioridade)}"
            for linha in ranking.itertuples()
        )
    )

    for sigla in foco["ufs"]:
        if sigla not in por_uf.index:
            continue
        linha = por_uf.loc[sigla]
        itens, distancias = [], []
        for indicador in disponiveis:
            valor = linha.get(indicador)
            if pd.isna(valor):
                continue
            diferenca = valor - media[indicador]
            if diferenca < 0:
                distancias.append((diferenca, indicador, valor))
            lado = "abaixo" if diferenca < 0 else "acima"
            itens.append(
                f"- {indicador} (meta {ficha.loc[indicador, 'indicador_ods']}, "
                f"{int(ficha.loc[indicador, 'ano'])}): {_num(valor)}%; média das UFs "
                f"{_num(media[indicador])}%; {_num(abs(diferenca))} pontos {lado} da média; "
                f"{int(posicao_no_indicador[indicador][sigla])}º pior valor entre as {total} UFs"
            )
        # o nome se repete na frase de proposito: com "Esta abaixo..." solto, o modelo
        # atribuiu a contagem de uma UF a outra na verificacao
        nome = f"{NOME_DA_UF.get(sigla, sigla)} ({sigla})"
        # as maiores distancias abaixo da media sao a explicacao da posicao no indice; vem
        # prontas porque, so com a contagem, o modelo explicava sem citar valor nenhum
        piores = sorted(distancias)[:3]
        explicacao = (
            f"Maiores distâncias abaixo da média: " + "; ".join(
                f"{indicador} ({_num(valor)}% contra média de {_num(media[indicador])}%)"
                for _, indicador, valor in piores
            ) + "." if piores else f"{nome} não está abaixo da média em nenhum indicador."
        )
        partes.append(
            f"## {nome} — região {linha['regiao']}; posição {int(linha['posicao'])}º de "
            f"{total} no índice, com índice {_num(linha['indice_prioridade'])}\n"
            f"{nome} está abaixo da média das {total} UFs em {len(distancias)} dos {len(itens)} indicadores. "
            f"{explicacao}\n"
            + "\n".join(itens)
        )

    presentes = [s for s in foco["ufs"] if s in por_uf.index]
    pede_comparacao = bool(ufs_no_texto(pergunta)) or COMPARACAO.search(tx.normalizar(pergunta))
    if len(presentes) >= 2 and pede_comparacao:
        # comparacao pronta: qual UF tem o maior e o menor valor em cada indicador. Sem
        # ela, o modelo comparava duas UFs lendo dois blocos e trocava os numeros entre elas
        rotulo = {s: f"{NOME_DA_UF.get(s, s)} ({s})" for s in presentes}
        linhas = [
            "- Índice de prioridade: "
            + "; ".join(f"{rotulo[s]} {_num(por_uf.loc[s, 'indice_prioridade'])}, "
                        f"{int(por_uf.loc[s, 'posicao'])}º" for s in presentes)
            + f". Maior prioridade (maior índice): {rotulo[max(presentes, key=lambda s: por_uf.loc[s, 'indice_prioridade'])]}."
        ]
        for indicador in disponiveis:
            valores = {s: por_uf.loc[s, indicador] for s in presentes if pd.notna(por_uf.loc[s, indicador])}
            if len(valores) < 2:
                continue
            maior, menor = max(valores, key=valores.get), min(valores, key=valores.get)
            # "pior" e "melhor" escritos por extenso: o usuario pergunta "qual tem a pior", e
            # com "menor valor" o modelo inverteu a conclusao na verificacao
            linhas.append(
                f"- {indicador}: " + "; ".join(f"{rotulo[s]} {_num(v)}%" for s, v in valores.items())
                + f". Pior situação (menor valor): {rotulo[menor]}. Melhor situação (maior valor): {rotulo[maior]}."
            )
        partes.append("## Comparação direta entre " + ", ".join(rotulo.values()) + "\n" + "\n".join(linhas))

    for regiao in foco["regioes"]:
        recorte = ranking[ranking["regiao"] == regiao]
        if recorte.empty:
            continue
        partes.append(
            f"## Região {regiao}: {len(recorte)} UFs, na ordem do índice\n"
            + "\n".join(
                f"- {linha.posicao}º {NOME_DA_UF.get(linha.uf, linha.uf)} ({linha.uf}): "
                f"{_num(linha.indice_prioridade)}"
                for linha in recorte.itertuples()
            )
            + f"\nMédia do índice na região {regiao}: {_num(recorte['indice_prioridade'].mean())}; "
            f"média do índice nas {total} UFs: {_num(ranking['indice_prioridade'].mean())}"
        )

    for indicador in foco["indicadores"]:
        if indicador not in ranking.columns:
            continue
        ordem = ranking[["uf", "regiao", indicador]].dropna().sort_values(indicador)
        partes.append(
            f"## {indicador} (meta {ficha.loc[indicador, 'indicador_ods']}, "
            f"{int(ficha.loc[indicador, 'ano'])}), do pior para o melhor valor — o menor valor é "
            "a pior situação e a maior carência\n"
            + "\n".join(
                f"{n}º pior valor — {NOME_DA_UF.get(uf, uf)} ({uf}), {regiao}: {_num(valor)}%"
                for n, (uf, regiao, valor) in enumerate(ordem.itertuples(index=False), start=1)
            )
            + f"\nMédia das {len(ordem)} UFs: {_num(media[indicador])}%"
        )

    # celula vazia do pandas e NaN, e NaN e verdadeiro num teste booleano
    escolhidas = _selecionar_noticias(noticias, foco, pergunta).fillna({"ufs_citadas": "", "temas_ods4": ""})
    inicio, fim = noticias["data"].min(), noticias["data"].max()
    cabecalho = (
        f"## Notícias do corpus de imprensa ({noticias['fonte'].nunique()} fontes, de "
        f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}). Mostram a pauta da imprensa, não medem a "
        "situação do território."
    )
    citadas = []
    if escolhidas.empty:
        partes.append(cabecalho + "\nNenhuma matéria do corpus corresponde a esta pergunta.")
    else:
        blocos = []
        for n, materia in enumerate(escolhidas.itertuples(), start=1):
            data = f"{materia.data:%d/%m/%Y}" if pd.notna(materia.data) else "sem data"
            # o resumo que vem do feed do WordPress termina no rodape "O post ... apareceu
            # primeiro em ...", que nao e conteudo da materia
            lead = re.split(r"\s+O post\s", " ".join(str(materia.resumo).split()))[0][:LEAD]
            blocos.append(
                f"[{n}] \"{materia.titulo}\" — {materia.fonte}, {data}. "
                f"UFs citadas: {str(materia.ufs_citadas).replace(';', ', ') or 'nenhuma'}. "
                f"Temas da ODS 4: {str(materia.temas_ods4).replace(';', ', ') or 'nenhum'}.\n"
                f"Lead: {lead}"
            )
            citadas.append({
                "n": n, "titulo": materia.titulo, "fonte": materia.fonte,
                "data": materia.data.date().isoformat() if pd.notna(materia.data) else None,
                "url": None if pd.isna(materia.url) else str(materia.url),
            })
        partes.append(cabecalho + "\n" + "\n".join(blocos))

    fontes = {
        "indicadores": [
            {"indicador": nome, "indicador_ods": str(ficha.loc[nome, "indicador_ods"]),
             "ano": int(ficha.loc[nome, "ano"]), "fonte": str(ficha.loc[nome, "fonte"]),
             "fonte_url": "" if pd.isna(ficha.loc[nome, "fonte_url"]) else str(ficha.loc[nome, "fonte_url"])}
            for nome in disponiveis
        ],
        "noticias": citadas,
    }
    return "\n\n".join(partes), fontes


def montar_mensagens(prompt, contexto, historico, pergunta):
    # o bloco DADOS vai na mensagem de sistema e muda a cada pergunta, conforme o foco; o
    # historico vai como as mensagens que foram, para o modelo resolver as referencias
    mensagens = [{"role": "system", "content": f"{prompt}\n\nDADOS\n\n{contexto}"}]
    for item in historico[-JANELA:]:
        papel = "assistant" if item["papel"] == "assistente" else "user"
        mensagens.append({"role": papel, "content": str(item["conteudo"])[:LIMITE_MENSAGEM]})
    mensagens.append({"role": "user", "content": pergunta})
    return mensagens


# ---------------------------------------------------------------- a conversa

def responder(pergunta, historico, memoria, dados, noticias, pesos=None,
              metodo=nc.METODOS_INDICE[0], prompt=PROMPT_SISTEMA):
    """Responde uma pergunta com os dados do projeto, a memoria e o modelo local.

    historico: lista de {"papel": "usuario" | "assistente", "conteudo": texto}.
    memoria: o foco devolvido na resposta anterior, ou vazio no inicio da conversa.
    pesos e metodo: os mesmos da pagina Indice de prioridade, para que o indice citado na
    conversa seja o mesmo da tela - a paridade da meta 4.11 do Project Charter.
    """
    inicio = time.perf_counter()
    memoria = {**memoria_vazia(), **(memoria or {})}
    historico = list(historico or [])
    disponiveis = nc.indicadores_disponiveis(dados)

    pesos = {i: float((pesos or {}).get(i, 1.0)) for i in disponiveis}
    ranking = nc.calcular_indice(dados, pesos, metodo)
    if ranking.empty:
        # todos os pesos zerados na tela: a conversa segue com pesos iguais, e o prompt diz
        pesos = {i: 1.0 for i in disponiveis}
        ranking = nc.calcular_indice(dados, pesos, metodo)

    citado, foco = foco_da_vez(pergunta, memoria, disponiveis)
    contexto, fontes = montar_contexto(dados, noticias, ranking, foco, pergunta, metodo, pesos)
    saida = ml.conversar(montar_mensagens(prompt, contexto, historico, pergunta))

    # a conferencia aceita o que esta nos dados e o que o proprio usuario escreveu; o que o
    # assistente disse antes nao conta, senao uma invencao repetida passaria a ter respaldo
    perguntas = [m["conteudo"] for m in historico if m["papel"] == "usuario"] + [pergunta]
    conferencia = tx.conferir_resposta(saida["resposta"], contexto + "\n" + "\n".join(perguntas))

    return {
        "resposta": saida["resposta"],
        "modelo": ml.MODELOS["conversa"]["modelo"],
        "gerativo": True,
        "memoria": atualizar_memoria(memoria, citado, saida["resposta"]),
        "foco": foco,
        "ufs_na_resposta": ufs_no_texto(saida["resposta"]),
        "fontes": fontes,
        "conferencia": conferencia,
        "contexto": contexto,
        "mensagens_lembradas": len(historico[-JANELA:]),
        "tokens_prompt": saida["tokens_prompt"],
        "tokens_resposta": saida["tokens_resposta"],
        "limite_de_tokens": ml.MODELOS["conversa"]["limite_tokens"],
        "resposta_cortada": saida["resposta_cortada"],
        "segundos": round(time.perf_counter() - inicio, 2),
        "analisado_em": datetime.now().isoformat(timespec="seconds"),
        "aviso": ml.AVISOS["conversa"],
    }
