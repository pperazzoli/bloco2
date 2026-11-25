# paginas/linguagem.py - analise de texto pelos modelos de linguagem locais
# criado 16-11-2026 (TP4)
# edited 16-11-2026 (TP4): entrou a tarefa de resumo. A aba de texto passou a escolher entre
# as duas tarefas, e o resumo gerado aparece ao lado do resumo escrito pela redacao, que e a
# referencia humana prevista na tarefa 2.2 do plano de uso de LLM.
# edited 25-11-2026 (TP5): a ficha dos modelos passou a listar tambem o da conversa, usado
# pela pagina Assistente ESG, e o botao de carga ganhou chave por aba (ver painel_de_carga).
#
# Como a pagina de servico de api, esta e um cliente HTTP: nao importa modelo_llm.py nem
# carrega modelo dentro do processo do Streamlit. Quem carrega os modelos e o servico do
# FastAPI, uma vez cada, e esta pagina consome as rotas. A razao e de recurso: o Streamlit
# reexecuta o script inteiro a cada interacao do usuario, e modelos de centenas de milhoes
# de parametros nao podem ser carregados nesse ritmo. Mantendo-os do outro lado do HTTP, a
# carga acontece uma vez por execucao do servico, nao uma vez por clique.

import pandas as pd
import plotly.express as px
import streamlit as st

import utils

chamar = utils.chamar_api

# a primeira carga le centenas de megabytes do disco; as analises seguintes levam
# milissegundos. os prazos sao diferentes porque as operacoes sao de ordens diferentes.
PRAZO_CARGA = 180
PRAZO_ANALISE = 120

CORES = {"positivo": "#2ca02c", "neutro": "#7f7f7f", "negativo": "#d62728"}

EXEMPLOS = {
    "Fato negativo, linguagem direta": (
        "Faltam professores, as escolas estão sem merenda e os repasses do fundo municipal "
        "atrasaram outra vez neste semestre."
    ),
    "Fato negativo, moldura de relato": (
        "A evasão escolar no ensino médio voltou a crescer e o abandono atingiu o maior nível "
        "da série histórica, aponta o levantamento divulgado nesta semana."
    ),
    "Avanço anunciado": (
        "O programa de reforço escolar elevou a proficiência em matemática e foi premiado "
        "nacionalmente neste ano."
    ),
    "Divulgação institucional": (
        "O IBGE divulgou nesta quinta-feira os dados da Pesquisa Nacional por Amostra de "
        "Domicílios referentes à educação."
    ),
}


def barras_de_distribuicao(tabela, eixo_x, eixo_y, titulo):
    figura = px.bar(
        tabela, x=eixo_x, y=eixo_y, color=eixo_y, orientation="h",
        color_discrete_map=CORES, title=titulo, text=eixo_x,
    )
    figura.update_layout(showlegend=False, height=220, margin=dict(l=0, r=0, t=40, b=0))
    return figura


st.title("🤖 Análise de linguagem")
st.markdown(
    "Esta página processa texto com **modelos de linguagem que rodam nesta máquina**. Nada é "
    "enviado a serviço externo: os pesos foram baixados uma vez do HuggingFace Hub para o "
    "cache local e a inferência acontece no processo do FastAPI. São dois modelos, um por "
    "tarefa — **classificação de sentimento** e **resumo** —, carregados em separado. Os "
    "critérios que levaram a cada um estão em `3_modeling/modelo_llm.md`, legível na página "
    "de *Documentação*."
)

base = st.text_input(
    "Endereço do serviço",
    value="http://127.0.0.1:8000",
    key="llm_base",
    help="Suba o serviço com `uvicorn api:app --reload` na raiz do projeto.",
)

ok, resposta = chamar(base, "/modelo")

if not ok:
    st.error(f"Serviço fora do ar — {utils.detalhe_do_erro(resposta)}")
    st.info(
        "Para subir o serviço, abra um segundo terminal na raiz do projeto e rode:\n\n"
        "```\nuvicorn api:app --reload\n```\n\n"
        "As demais páginas da aplicação não dependem da API nem dos modelos: elas leem os "
        "arquivos de `data/` diretamente."
    )
    st.stop()

ambiente = resposta["corpo"]
FICHAS = {ficha["tarefa"]: ficha for ficha in ambiente["modelos"]}


def painel_de_carga(tarefa, aba="texto"):
    """Mostra a situacao de um modelo e, se preciso, o botao que o carrega."""
    # edited 25-11-2026 (TP5): 'aba' entra na chave do botao. O painel do sentimento aparece
    # nas duas primeiras abas, e com a mesma chave o Streamlit recusava a pagina inteira
    # (StreamlitDuplicateElementKey) sempre que o modelo ainda nao estava carregado.
    ficha = FICHAS[tarefa]
    colunas = st.columns([3, 1, 1])
    if ficha["carregado"]:
        colunas[0].success(f"{ficha['descricao'].capitalize()} · `{ficha['modelo']}`")
        colunas[1].metric("Parâmetros", f"{ficha['parametros'] / 1e6:.0f} M")
        colunas[2].metric("Dispositivo", ficha["dispositivo"])
        return True

    colunas[0].warning(f"Modelo ainda não carregado · `{ficha['modelo']}`")
    colunas[1].metric("Pesos em cache", "sim" if ficha["ja_baixado"] else "não")
    if colunas[2].button("Carregar agora", type="primary", width="stretch", key=f"carregar_{tarefa}_{aba}"):
        with st.spinner(f"carregando o modelo de {tarefa}, isto leva alguns segundos"):
            sucesso, carga = chamar(
                base, "/modelo/carregar", metodo="POST",
                parametros={"tarefa": tarefa}, tempo_limite=PRAZO_CARGA,
            )
        if sucesso:
            utils.registrar(f"carregou o modelo de {tarefa}")
            st.rerun()
        else:
            st.error(utils.detalhe_do_erro(carga))

    if ficha["erro"]:
        st.error(f"A última tentativa de carga falhou: {ficha['erro']}")
    elif not ficha["ja_baixado"]:
        st.info(
            "Os pesos não estão no cache local. A primeira carga baixa do HuggingFace Hub e "
            "precisa de rede; depois disso o modelo roda offline."
        )
    st.caption(
        "A carga é explícita, num botão, e não automática ao abrir a página: é a regra 4.5 do "
        "plano de uso de LLM — operação custosa não dispara em recarregamento de tela."
    )
    return False


st.divider()

texto_livre, corpus, modelo = st.tabs(["Processar um texto", "Panorama do corpus", "Sobre os modelos"])

# ------------------------------------------------------------ aba 1: texto do usuario

with texto_livre:
    tarefa = st.radio(
        "Tarefa",
        ["sentimento", "resumo"],
        horizontal=True,
        key="llm_tarefa",
        format_func=lambda t: FICHAS[t]["descricao"].capitalize(),
        help="Cada tarefa tem o seu modelo, carregado em separado.",
    )

    if tarefa == "sentimento":
        st.markdown(
            "Envia o texto para `POST /processar_texto` com `tarefa: sentimento`. A resposta "
            "traz a pontuação dos **três** rótulos, não só a do vencedor: em texto "
            "institucional a diferença entre o primeiro e o segundo é muitas vezes pequena, e "
            "um rótulo sozinho pareceria mais seguro do que é."
        )
    else:
        st.markdown(
            "Envia o texto para `POST /processar_texto` com `tarefa: resumo`. O resumo é "
            "**abstrativo**: o modelo reescreve, não recorta — e por isso pode afirmar o que "
            "não está no original. Cada resumo vem com a **conferência automática** dos seus "
            "números, datas e nomes próprios contra o texto de origem."
        )

    painel_de_carga(tarefa)
    st.caption(f"⚠️ {FICHAS[tarefa]['aviso']}")

    origem = st.radio(
        "De onde vem o texto",
        ["exemplo pronto", "matéria do corpus", "escrever do zero"],
        horizontal=True,
        key="llm_origem",
    )

    conteudo = ""
    materia = None
    if origem == "exemplo pronto":
        exemplo = st.selectbox(
            "Exemplo",
            list(EXEMPLOS),
            key="llm_exemplo",
            help="Os dois primeiros relatam o mesmo tipo de fato e recebem rótulos diferentes.",
        )
        conteudo = EXEMPLOS[exemplo]
    elif origem == "matéria do corpus":
        noticias_corpus = utils.carregar_noticias()
        escolhida = st.selectbox(
            "Matéria",
            range(len(noticias_corpus)),
            format_func=lambda i: f"{noticias_corpus.loc[i, 'fonte']} · {noticias_corpus.loc[i, 'titulo'][:70]}",
            key="llm_materia",
        )
        materia = noticias_corpus.loc[escolhida]
        conteudo = f"{materia['titulo']}. {materia['texto']}".strip()

    with st.form("llm_texto"):
        texto = st.text_area("Texto em português", value=conteudo, height=180)
        enviar = st.form_submit_button("Processar", type="primary")

    if enviar:
        if len(texto.strip()) < 20:
            st.warning("Escreva ao menos 20 caracteres — abaixo disso o resultado não significa nada.")
        else:
            with st.spinner(f"processando: {FICHAS[tarefa]['descricao']}"):
                sucesso, resultado = chamar(
                    base, "/processar_texto", metodo="POST",
                    corpo={"texto": texto, "tarefa": tarefa}, tempo_limite=PRAZO_CARGA,
                )
            if not sucesso:
                st.error(utils.detalhe_do_erro(resultado))
            else:
                corpo = resultado["corpo"]

                if tarefa == "sentimento":
                    analise = corpo["sentimento"]
                    utils.registrar(f"classificou um texto: {analise['rotulo']}")
                    colunas = st.columns(2)
                    colunas[0].metric("Rótulo", analise["rotulo"].capitalize())
                    colunas[1].metric("Confiança", f"{analise['confianca']:.1%}")
                    st.plotly_chart(
                        barras_de_distribuicao(
                            pd.DataFrame(analise["distribuicao"]), "pontuacao", "rotulo",
                            "Pontuação de cada rótulo",
                        ),
                        width="stretch",
                    )
                else:
                    analise = corpo["resumo"]
                    utils.registrar(f"resumiu um texto de {analise['palavras_entrada']} palavras")
                    st.markdown("##### Resumo gerado pelo modelo")
                    st.info(analise["resumo"])
                    colunas = st.columns(4)
                    colunas[0].metric("Palavras na entrada", analise["palavras_entrada"])
                    colunas[1].metric("Palavras no resumo", analise["palavras_resumo"])
                    colunas[2].metric("Compressão", f"{analise['taxa_de_compressao']:.1%}")
                    conferencia = analise["conferencia"]
                    colunas[3].metric(
                        "Termos sem respaldo",
                        conferencia["ausentes"],
                        f"de {conferencia['conferidos']} conferidos",
                        delta_color="off",
                    )

                    st.markdown("##### Conferência contra o texto de origem")
                    if conferencia["ausentes"]:
                        st.warning(
                            f"**{conferencia['ausentes']} de {conferencia['conferidos']} termos "
                            "verificáveis não aparecem no texto de origem** — o modelo os "
                            "produziu por conta própria. Não cite o resumo sem conferir estes "
                            "pontos na matéria."
                        )
                    else:
                        st.success(
                            f"**Os {conferencia['conferidos']} termos verificáveis do resumo "
                            "aparecem no texto de origem.** Isso não garante que o resumo seja "
                            "fiel ao sentido, só que não inventou número, data nem nome."
                        )
                    conferidos = pd.DataFrame(conferencia["itens"])
                    if not conferidos.empty:
                        # marcacao por texto, nao caixa de selecao: uma caixa desmarcada e
                        # facil de nao ver, e e justamente o ausente que nao pode passar
                        conferidos["situacao"] = conferidos["no_original"].map(
                            {True: "✅ está no original", False: "⚠️ NÃO está no original"}
                        )
                        st.dataframe(
                            conferidos[["situacao", "tipo", "termo"]],
                            hide_index=True,
                            width="stretch",
                            column_config={
                                "situacao": st.column_config.TextColumn("Conferência", width="medium"),
                                "tipo": "Tipo",
                                "termo": st.column_config.TextColumn("Termo no resumo", width="large"),
                            },
                        )
                    st.caption(conferencia["ressalva"])

                    if materia is not None and str(materia["resumo"]).strip():
                        st.markdown("##### Ao lado do resumo escrito pela redação")
                        st.markdown(
                            "A coluna `resumo` do corpus é o resumo que a própria redação "
                            "publicou no feed. É a referência humana prevista na tarefa 2.2 do "
                            "plano de uso de LLM — serve para julgar o gerado, não é métrica."
                        )
                        lado_a_lado = st.columns(2)
                        lado_a_lado[0].markdown("**Redação**")
                        lado_a_lado[0].write(str(materia["resumo"]).strip())
                        lado_a_lado[1].markdown("**Modelo**")
                        lado_a_lado[1].write(analise["resumo"])

                st.caption(
                    f"{corpo['caracteres']} caracteres · {corpo['tokens']} de "
                    f"{corpo['limite_de_tokens']} tokens · {corpo['segundos']} s · "
                    f"modelo `{corpo['modelo']}` · "
                    f"{'texto gerado' if corpo['gerativo'] else 'classificação'} em "
                    f"{corpo['analisado_em']}"
                )
                if corpo["texto_truncado"]:
                    st.warning(
                        f"O texto tem {corpo['tokens']} tokens e o modelo lê "
                        f"{corpo['limite_de_tokens']}: ele viu "
                        f"{corpo['limite_de_tokens'] / corpo['tokens']:.0%} do texto. "
                        + ("O resumo vale para o começo do texto e não para o todo, o que é "
                           "fácil de esquecer quando se lê só o resumo."
                           if tarefa == "resumo" else
                           "O rótulo vale para o começo do texto, não para o todo.")
                    )
                with st.expander("Resposta JSON completa"):
                    st.json(corpo)

# ------------------------------------------------------------ aba 2: corpus de noticias

with corpus:
    st.markdown(
        "Envia o filtro para `POST /noticias/sentimento` e recebe o corpus já classificado. "
        "As 59 mil palavras não trafegam: quem lê os arquivos é o serviço. É a tarefa 2.3 do "
        "plano de uso de LLM."
    )
    st.caption(
        "Só a classificação é aplicada em lote. Resumir as 105 matérias levaria perto de sete "
        "minutos de CPU, e o resumo tem de ser lido uma a uma para valer alguma coisa — por "
        "isso ele fica na aba *Processar um texto*, uma matéria por vez."
    )

    painel_de_carga("sentimento", aba="corpus")

    noticias = utils.carregar_noticias()
    filtros = st.columns([2, 1, 1])
    fontes_escolhidas = filtros[0].multiselect(
        "Fonte", sorted(noticias["fonte"].unique()), key="llm_fontes",
    )
    tema = filtros[1].text_input("Tema da ODS 4", key="llm_tema", placeholder="4.5")
    campo = filtros[2].radio("Parte da matéria", ["titulo e resumo", "texto"], key="llm_campo")

    limite = st.slider(
        "Matérias a analisar", 1, 105, 20, key="llm_limite",
        help="Cada matéria custa cerca de 80 ms de CPU. O corpus inteiro leva perto de 9 segundos.",
    )
    if campo == "texto":
        st.caption(
            "O corpo integral tem 563 palavras em média e passa da janela de 512 tokens do "
            "modelo: será truncado, e a tabela marca quais linhas foram cortadas. O padrão "
            "`titulo e resumo` cabe inteiro na janela."
        )

    if st.button("Analisar o corpus", type="primary", key="llm_corpus"):
        parametros = {"limite": limite, "campo": campo}
        if fontes_escolhidas:
            parametros["fonte"] = fontes_escolhidas
        if tema.strip():
            parametros["tema"] = tema.strip()

        with st.spinner(f"analisando {limite} matéria(s)"):
            sucesso, resultado = chamar(
                base, "/noticias/sentimento", metodo="POST",
                parametros=parametros, tempo_limite=PRAZO_ANALISE,
            )
        if not sucesso:
            st.error(utils.detalhe_do_erro(resultado))
        else:
            st.session_state.llm_resultado = resultado["corpo"]
            utils.registrar(f"classificou {resultado['corpo']['analisadas']} materias")

    corpo = st.session_state.get("llm_resultado")
    if corpo:
        st.success(
            f"{corpo['analisadas']} de {corpo['total_no_corpus']} matérias classificadas em "
            f"{corpo['segundos']} s · campo `{corpo['campo_analisado']}`"
        )

        contagem = pd.DataFrame(
            [{"rotulo": r, "materias": n} for r, n in corpo["por_rotulo"].items()]
        ).sort_values("materias", ascending=False)

        painel = st.columns([1, 2])
        for rotulo in ["positivo", "neutro", "negativo"]:
            quantidade = corpo["por_rotulo"].get(rotulo, 0)
            painel[0].metric(
                rotulo.capitalize(),
                quantidade,
                f"{quantidade / corpo['analisadas']:.0%} do analisado",
                delta_color="off",
            )
        painel[1].plotly_chart(
            barras_de_distribuicao(contagem, "materias", "rotulo", "Matérias por rótulo"),
            width="stretch",
        )

        classificadas = pd.DataFrame(corpo["dados"])
        st.dataframe(
            classificadas[["data", "fonte", "titulo", "rotulo", "confianca", "ufs_citadas",
                           "temas_ods4", "tokens", "texto_truncado", "url"]],
            hide_index=True,
            width="stretch",
            height=320,
            column_config={
                "data": "Data",
                "fonte": "Fonte",
                "titulo": st.column_config.TextColumn("Título", width="large"),
                "rotulo": "Rótulo",
                "confianca": st.column_config.ProgressColumn("Confiança", min_value=0, max_value=1, format="%.2f"),
                "ufs_citadas": "UFs citadas",
                "temas_ods4": "Temas da ODS 4",
                "tokens": st.column_config.NumberColumn("Tokens", format="%d"),
                "texto_truncado": st.column_config.CheckboxColumn("Truncado"),
                "url": st.column_config.LinkColumn("Original", display_text="abrir"),
            },
        )
        st.download_button(
            "⬇️ Baixar a classificação em CSV",
            data=utils.para_csv(classificadas),
            file_name="noticias_sentimento.csv",
            mime="text/csv",
        )

        st.subheader("Tom da cobertura por UF, ao lado da carência medida")
        st.markdown(
            "O cruzamento é de leitura, não de cálculo. O índice de prioridade vem dos "
            "indicadores oficiais; o saldo vem do tom das matérias. **O saldo não entra no "
            "índice** — mede atenção e tom editorial, não a situação do território."
        )
        por_uf = pd.DataFrame(corpo["por_uf"])
        if por_uf.empty:
            st.info("Nenhuma das matérias analisadas cita uma UF identificável.")
        else:
            dados = utils.dados_ativos()
            pesos = {n: st.session_state.pesos.get(n, 1.0) for n in utils.indicadores_disponiveis(dados)}
            ranking = utils.calcular_indice(
                dados, tuple(sorted(pesos.items())), st.session_state.metodo_indice
            )
            cruzado = por_uf.merge(
                ranking[["uf", "regiao", "posicao", "indice_prioridade"]], on="uf", how="left"
            )
            st.dataframe(
                cruzado[["uf", "regiao", "posicao", "indice_prioridade", "materias",
                         "positivo", "neutro", "negativo", "saldo"]],
                hide_index=True,
                width="stretch",
                column_config={
                    "uf": "UF",
                    "regiao": "Região",
                    "posicao": st.column_config.NumberColumn("Posição no índice", format="%d"),
                    "indice_prioridade": st.column_config.NumberColumn("Índice de prioridade", format="%.1f"),
                    "materias": st.column_config.NumberColumn("Matérias", format="%d"),
                    "positivo": st.column_config.NumberColumn("Positivas", format="%d"),
                    "neutro": st.column_config.NumberColumn("Neutras", format="%d"),
                    "negativo": st.column_config.NumberColumn("Negativas", format="%d"),
                    "saldo": st.column_config.NumberColumn("Saldo do tom", format="%.2f"),
                },
            )
            st.caption(
                "Uma matéria que cita três UFs conta para as três, por isso a soma de "
                "*Matérias* passa do total analisado. *Saldo* é (positivas − negativas) / matérias."
            )

        with st.expander("Resposta JSON completa"):
            st.json(corpo)

# ------------------------------------------------------------ aba 3: ficha do modelo

with modelo:
    st.subheader("Os modelos do serviço")
    st.caption(
        "Esta página usa os dois primeiros. O terceiro, de conversa, é o da página *Assistente "
        "ESG*, e é servido pelo Ollama nesta máquina."
    )
    # as fichas ja foram buscadas no topo da pagina, que interrompe a execucao se o servico
    # estiver fora do ar. reaproveitar evita uma segunda chamada por recarregamento de tela.
    linhas = []
    for tarefa_ficha in ambiente["modelos"]:
        linhas.append({
            "Tarefa": tarefa_ficha["tarefa"],
            "Descrição": tarefa_ficha["descricao"],
            "Modelo": tarefa_ficha["modelo"],
            "Gerativo": tarefa_ficha["gerativo"],
            "Arquitetura": tarefa_ficha["arquitetura"] or "só após a carga",
            "Parâmetros": tarefa_ficha["parametros"] or 0,
            "Dispositivo": tarefa_ficha["dispositivo"] or "—",
            "Janela": f"{tarefa_ficha['limite_de_tokens']} tokens",
            # edited 25-11-2026 (TP5): o modelo da conversa e carregado pelo Ollama, que nao
            # informa a este processo quanto tempo a carga levou
            "Carga": ("não carregado" if not tarefa_ficha["carregado"]
                      else f"{tarefa_ficha['segundos_de_carga']} s" if tarefa_ficha["segundos_de_carga"] is not None
                      else "no Ollama"),
        })
    st.dataframe(
        pd.DataFrame(linhas),
        hide_index=True,
        width="stretch",
        column_config={
            "Gerativo": st.column_config.CheckboxColumn("Gerativo"),
            "Parâmetros": st.column_config.NumberColumn("Parâmetros", format="%d"),
        },
    )
    st.caption(
        f"Execução: {ambiente['execucao']} · cache em `{ambiente['cache_local']}` · "
        + " · ".join(f"{n} {v}" for n, v in ambiente["bibliotecas"].items() if v)
    )
    st.caption(f"Parâmetros de geração do resumo, fixos: `{ambiente['parametros_de_geracao']}`")

    st.subheader("A diferença que a coluna *Gerativo* marca")
    st.markdown(
        "Não é detalhe técnico. O classificador escolhe entre três rótulos fixos: não há como "
        "ele inventar um número ou um fato. O modelo de resumo **redige**, e um resumo "
        "abstrativo pode afirmar o que não está no original — é exatamente o risco 8.4 do "
        "Project Charter, e por isso as quatro regras de contenção que o Charter fixa valem "
        "para a tarefa de resumo e não para a de sentimento."
    )

    st.subheader("O que esta tela não faz")
    st.markdown(
        "- **Não calcula nada do índice.** Rótulo e resumo são contexto qualitativo; o índice "
        "de prioridade continua vindo inteiramente dos indicadores oficiais em `nucleo.py`.\n"
        "- **Não deixa texto gerado passar por apuração.** Todo resumo aparece identificado "
        "como gerado, com o modelo, o instante e o aviso correspondente.\n"
        "- **Não guarda o resultado em disco.** A classificação vive na sessão e no download "
        "em CSV, e o resumo vive na tela. `data/` não é alterado por esta página."
    )

    st.subheader("Limites conhecidos, medidos")
    st.markdown(
        "**No sentimento:** o modelo pesa o *registro do relato* acima do fato relatado. A "
        "mesma notícia de evasão escolar sai como `negativo` escrita de forma direta e como "
        "`neutro` na moldura jornalística — os dois primeiros exemplos da aba *Processar um "
        "texto* mostram isso. Em consequência, o corpus deste projeto, metade dele release "
        "institucional, é classificado majoritariamente como neutro. É descrição correta do "
        "corpus, não falha de medição.\n\n"
        "**No resumo:** o modelo inventa. Na verificação ele produziu uma data, um estado e "
        "uma cifra que não estavam no texto de entrada. É por isso que cada resumo vem com a "
        "conferência automática dos seus números, datas e nomes próprios contra a origem, e "
        "com o resumo da redação ao lado quando a matéria vem do corpus. O resumo é bom para "
        "decidir se vale ler a matéria; para citar, confira os pontos que a conferência "
        "apontar."
    )

    st.subheader("O que a conferência faz, e o que não faz")
    st.markdown(
        "Não usa modelo nenhum: procura no resumo os três tipos de termo que um modelo "
        "gerativo inventa com mais frequência — **número, data e nome próprio** — e checa "
        "cada um no texto de origem, palavra inteira, sem acento e sem diferenciar "
        "maiúsculas. É comparação léxica, **não semântica**: diz se o termo está lá, não se o "
        "resumo é fiel ao sentido. E erra de propósito para o lado de apontar demais — um "
        "termo apontado que está no texto custa um olhar; um termo inventado que passa custa "
        "uma afirmação falsa num reporte."
    )
