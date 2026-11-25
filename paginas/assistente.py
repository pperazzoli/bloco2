# paginas/assistente.py - conversa com memoria sobre os dados do projeto
# criado 25-11-2026 (TP5)
#
# Cliente HTTP de POST /assistente, como a pagina de analise de linguagem e cliente das rotas
# do TP4: nao importa assistente.py nem modelo_llm.py. A memoria da conversa vive aqui, em
# st.session_state - a rota nao guarda estado -, e vai a cada pergunta junto do historico.
#
# O que a pagina mostra ao lado de cada resposta e o que torna a conversa auditavel: o
# grafico dos dados por tras dela, as fontes, a conferencia dos numeros e, se o usuario
# quiser, o bloco de dados exatamente como o modelo o leu.

import pandas as pd
import plotly.express as px
import streamlit as st

import utils

chamar = utils.chamar_api

# a primeira resposta inclui a carga do modelo no Ollama, que leva de segundos a minuto
PRAZO = 300
JANELA = 6

EXEMPLOS = [
    "Quais são as cinco UFs com maior prioridade de investimento?",
    "Por que a primeira delas está no topo?",
    "Como está a Bahia no índice?",
    "E Pernambuco, comparado com ela?",
    "Quais UFs do Nordeste têm maior prioridade?",
    "Onde a internet nas escolas é pior?",
]

dados = utils.dados_ativos()
indicadores = utils.indicadores_disponiveis(dados)
pesos = {n: float(st.session_state.pesos.get(n, 1.0)) for n in indicadores}
ranking = utils.calcular_indice(dados, tuple(sorted(pesos.items())), st.session_state.metodo_indice)


def grafico_do_indice(destaque):
    # o ranking inteiro, com as UFs de que a resposta fala em destaque
    tabela = ranking[["posicao", "uf", "indice_prioridade"]].copy()
    tabela["grupo"] = tabela["uf"].map(lambda uf: "citada na resposta" if uf in destaque else "demais UFs")
    figura = px.bar(
        tabela, x="indice_prioridade", y="uf", orientation="h", color="grupo",
        color_discrete_map={"citada na resposta": "#1f6f4a", "demais UFs": "#c9d6ce"},
        labels={"indice_prioridade": "Índice de prioridade (0 a 100)", "uf": "", "grupo": ""},
        height=520,
    )
    figura.update_layout(margin=dict(l=0, r=0, t=10, b=0), yaxis=dict(autorange="reversed"),
                         legend=dict(orientation="h", y=1.04))
    return figura


def grafico_dos_indicadores(ufs):
    # os indicadores das UFs citadas ao lado da media das 27, para ver de onde vem a carencia
    matriz = utils.matriz_uf_indicador(dados)
    linhas = [{"indicador": i, "serie": "Média das UFs", "valor": matriz[i].mean()} for i in matriz.columns]
    for uf in ufs:
        if uf in matriz.index:
            linhas += [{"indicador": i, "serie": uf, "valor": matriz.loc[uf, i]} for i in matriz.columns]
    tabela = pd.DataFrame(linhas)
    tabela["indicador"] = tabela["indicador"].map(lambda nome: nome if len(nome) <= 40 else nome[:37] + "...")
    figura = px.bar(
        tabela, x="valor", y="indicador", color="serie", barmode="group", orientation="h",
        labels={"valor": "%", "indicador": "", "serie": ""}, height=140 + 60 * len(matriz.columns),
        color_discrete_map={"Média das UFs": "#9aa5a0"},
    )
    figura.update_layout(margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=1.06))
    return figura


def mostrar_detalhe(detalhe, chave):
    """O que acompanha cada resposta: a conferencia em uma linha e o resto num expansor."""
    conferencia = detalhe["conferencia"]
    ausentes = [i["termo"] for i in conferencia["itens"] if not i["no_original"]]
    if ausentes:
        st.warning(
            f"⚠️ **{len(ausentes)} de {conferencia['conferidos']}** números, datas ou nomes desta "
            f"resposta não estão nos dados que o modelo recebeu: {', '.join(ausentes)}. "
            "Confira antes de usar."
        )
    else:
        st.caption(
            f"✅ Os {conferencia['conferidos']} números, datas e nomes da resposta estão nos dados "
            "que o modelo recebeu."
        )
    if detalhe["resposta_cortada"]:
        st.warning("A resposta bateu no limite de tamanho e saiu cortada.")
    st.caption(
        f"Texto gerado por `{detalhe['modelo']}` em {detalhe['analisado_em']} · {detalhe['segundos']} s · "
        f"{detalhe['tokens_prompt']} tokens de entrada · {detalhe['mensagens_lembradas']} mensagens lembradas"
    )

    with st.expander("Dados, fontes e conferência desta resposta"):
        destaque = detalhe["ufs_na_resposta"] or detalhe["foco"]["ufs"]
        grafico, fontes, conferida, lido = st.tabs(
            ["Gráfico", "Fontes", "Conferência", "O que o modelo leu"]
        )
        with grafico:
            st.plotly_chart(grafico_do_indice(destaque), width="stretch", key=f"indice_{chave}")
            if destaque:
                st.plotly_chart(grafico_dos_indicadores(destaque[:4]), width="stretch", key=f"ind_{chave}")
            st.caption(
                "Os gráficos usam os pesos e o método da página *Índice de prioridade* — os mesmos "
                "que foram enviados ao assistente."
            )
        with fontes:
            noticias = detalhe["fontes"]["noticias"]
            if noticias:
                st.markdown("**Matérias que o modelo recebeu**, pelo número com que pode citá-las:")
                st.dataframe(
                    pd.DataFrame(noticias), hide_index=True, width="stretch",
                    column_config={
                        "n": st.column_config.NumberColumn("Nº", format="[%d]"),
                        "titulo": st.column_config.TextColumn("Título", width="large"),
                        "fonte": "Fonte", "data": "Data",
                        "url": st.column_config.LinkColumn("Original", display_text="abrir"),
                    },
                )
            else:
                st.caption("Nenhuma matéria do corpus entrou no contexto desta resposta.")
            st.markdown("**Indicadores**, todos do IBGE:")
            st.dataframe(
                pd.DataFrame(detalhe["fontes"]["indicadores"]), hide_index=True, width="stretch",
                column_config={
                    "indicador": st.column_config.TextColumn("Indicador", width="large"),
                    "indicador_ods": "Meta", "ano": st.column_config.NumberColumn("Ano", format="%d"),
                    "fonte": "Fonte", "fonte_url": st.column_config.LinkColumn("Consulta", display_text="abrir"),
                },
            )
        with conferida:
            itens = pd.DataFrame(conferencia["itens"])
            if itens.empty:
                st.caption("A resposta não tem número, data nem nome próprio a conferir.")
            else:
                itens["situacao"] = itens["no_original"].map(
                    {True: "✅ está nos dados", False: "⚠️ NÃO está nos dados"}
                )
                st.dataframe(itens[["situacao", "tipo", "termo"]], hide_index=True, width="stretch")
            st.caption(conferencia["ressalva"])
        with lido:
            st.caption(
                "O bloco de dados montado pelo projeto para esta pergunta, exatamente como foi ao "
                "modelo, depois das regras do prompt e antes do histórico."
            )
            st.code(detalhe["contexto"], language=None)


# ------------------------------------------------------------ cabecalho e servico

st.title("💬 Assistente ESG")
st.markdown(
    "Pergunte em linguagem natural sobre os indicadores da ODS 4, o índice de prioridade e as "
    "notícias. O assistente **lembra a conversa** — dá para perguntar \"e o Pará?\" ou \"qual "
    "das duas está pior?\" — e responde com os **dados que o projeto já apurou**: o modelo "
    "recebe os números prontos e não calcula nada. Toda resposta vem com a conferência dos seus "
    "números, datas e nomes contra esses dados, e com as fontes."
)

with st.expander("Como funciona"):
    st.code(
        "pergunta + histórico + memória de foco\n"
        "        │\n"
        "        ▼\n"
        "nucleo.py apura os dados do foco ──► bloco DADOS: ranking, indicadores, médias,\n"
        "        │                            posições, comparação e notícias\n"
        "        ▼\n"
        "llama3.1:8b no Ollama, nesta máquina ──► resposta\n"
        "        │\n"
        "        ▼\n"
        "conferência dos números, datas e nomes contra o bloco DADOS ──► tela",
        language=None,
    )
    st.markdown(
        "- **Memória de janela:** as últimas seis mensagens voltam ao modelo, que assim entende "
        "referências como \"ela\" e \"a primeira delas\".\n"
        "- **Memória de foco:** as UFs, regiões, temas e indicadores citados ficam guardados e "
        "decidem que dados entram na próxima resposta. Está na barra lateral, e pode ser apagada.\n"
        "- **Sem saída da máquina:** o modelo roda no Ollama local. Nenhuma pergunta nem dado é "
        "enviado a serviço externo.\n"
        "- **Limite:** a conferência é léxica — pega número ou nome que não está nos dados, mas "
        "não pega número verdadeiro posto no lugar errado. As seções 4.4 e 7 de "
        "`3_modeling/assistente_llm.md` descrevem os casos medidos."
    )

base = st.text_input(
    "Endereço do serviço",
    value="http://127.0.0.1:8000",
    key="assistente_base",
    help="Suba o serviço com `uvicorn api:app --reload` na raiz do projeto.",
)

ok, resposta = chamar(base, "/modelo")
if not ok:
    st.error(f"Serviço fora do ar — {utils.detalhe_do_erro(resposta)}")
    st.info(
        "O assistente roda no serviço de API. Para subi-lo, abra um segundo terminal na raiz do "
        "projeto e rode:\n\n```\nuvicorn api:app --reload\n```\n\n"
        "As demais páginas da aplicação não dependem da API: elas leem os arquivos de `data/`."
    )
    st.stop()

ficha = next((m for m in resposta["corpo"]["modelos"] if m["tarefa"] == "conversa"), None)
if ficha is None:
    st.error("O serviço no ar é anterior ao TP5 e não tem o assistente. Reinicie o `uvicorn`.")
    st.stop()
if not ficha["ja_baixado"]:
    st.warning(
        f"O Ollama não respondeu ou o modelo `{ficha['modelo']}` não está nele. Inicie o Ollama "
        f"nesta máquina e, na primeira vez, baixe o modelo com `ollama pull {ficha['modelo']}` "
        "(4,9 GB). As perguntas responderão 503 até lá."
    )
else:
    estado = f"carregado · {ficha['dispositivo']}" if ficha["carregado"] else "no disco, carrega na primeira pergunta"
    st.caption(
        f"Modelo `{ficha['modelo']}` ({ficha['arquitetura']}, {ficha['parametros'] / 1e9:.1f} bilhões "
        f"de parâmetros) · {estado} · servido pelo Ollama em `{resposta['corpo'].get('servidor_da_conversa')}`"
    )
if st.session_state.dados_extras is not None:
    st.caption(
        "Os dados enviados por upload nesta sessão não chegam ao assistente, que roda no serviço: "
        "ele usa os indicadores oficiais."
    )

# ------------------------------------------------------------ memoria na barra lateral

with st.sidebar:
    st.markdown("### 🧠 Memória da conversa")
    memoria = st.session_state.memoria_conversa or {}
    perguntas = sum(m["papel"] == "usuario" for m in st.session_state.conversa)
    st.caption(f"{perguntas} pergunta(s) · as {JANELA} últimas mensagens voltam ao modelo")
    for rotulo, chave in [("UFs", "ufs"), ("Regiões", "regioes"), ("Temas da ODS 4", "temas"),
                          ("Indicadores", "indicadores")]:
        itens = memoria.get(chave) or []
        curtos = [i if len(i) <= 32 else i[:29] + "..." for i in itens]
        st.markdown(f"**{rotulo}:** " + (" ".join(f"`{i}`" for i in curtos) if curtos else "—"))
    if st.session_state.conversa:
        st.download_button(
            "⬇️ Baixar a conversa (Markdown)",
            data=utils.conversa_em_markdown(st.session_state.conversa).encode("utf-8"),
            file_name="conversa_assistente_esg.md",
            mime="text/markdown",
            width="stretch",
        )
        if st.button("Esquecer a conversa", width="stretch"):
            st.session_state.conversa = []
            st.session_state.memoria_conversa = None
            utils.registrar("apagou a conversa com o assistente")
            st.rerun()
    st.caption("A memória vive só nesta sessão do navegador: não é gravada em disco nem fica no serviço.")

# ------------------------------------------------------------ conversa

pergunta = None
if not st.session_state.conversa:
    st.markdown("**Para começar**, escolha uma pergunta ou escreva a sua abaixo:")
    colunas = st.columns(3)
    for n, exemplo in enumerate(EXEMPLOS):
        if colunas[n % 3].button(exemplo, key=f"exemplo_{n}", width="stretch"):
            pergunta = exemplo

for n, mensagem in enumerate(st.session_state.conversa):
    with st.chat_message("user" if mensagem["papel"] == "usuario" else "assistant"):
        st.markdown(mensagem["conteudo"])
        if mensagem["papel"] == "assistente":
            mostrar_detalhe(mensagem["detalhe"], n)

digitada = st.chat_input("Pergunte sobre os indicadores, o índice ou as notícias")
pergunta = digitada or pergunta

if pergunta:
    with st.chat_message("user"):
        st.markdown(pergunta)
    corpo = {
        "pergunta": pergunta,
        "historico": [{"papel": m["papel"], "conteudo": m["conteudo"]} for m in st.session_state.conversa],
        "memoria": st.session_state.memoria_conversa or {},
        "pesos": pesos,
        "metodo": st.session_state.metodo_indice,
    }
    with st.chat_message("assistant"):
        with st.spinner("consultando os dados e redigindo — a primeira resposta também carrega o modelo"):
            sucesso, resultado = chamar(base, "/assistente", metodo="POST", corpo=corpo, tempo_limite=PRAZO)
        if not sucesso:
            st.error(utils.detalhe_do_erro(resultado))
        else:
            detalhe = resultado["corpo"]
            st.session_state.conversa = st.session_state.conversa + [
                {"papel": "usuario", "conteudo": pergunta},
                {"papel": "assistente", "conteudo": detalhe["resposta"], "detalhe": detalhe},
            ]
            st.session_state.memoria_conversa = detalhe["memoria"]
            utils.registrar(f"perguntou ao assistente ({detalhe['conferencia']['situacao']})")
            st.rerun()
