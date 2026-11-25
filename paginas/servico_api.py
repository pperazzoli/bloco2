# paginas/servico_api.py - consumo da api do fastapi dentro da aplicacao
# criado 16-11-2026 (TP3)
# edited 16-11-2026 (TP4): entraram as quatro rotas de linguagem natural na tabela e a
# funcao de chamada foi para utils.chamar_api, para que a pagina de analise de linguagem use
# a mesma. O nome local fica como atalho, as chamadas desta pagina nao mudaram.
# edited 25-11-2026 (TP5): entrou POST /assistente na tabela, que passou a quinze rotas

# Esta pagina e um cliente HTTP da api.py: nao le os arquivos de data/ diretamente, chama o
# servico. E o que fecha a integracao pedida no TP3 e o que permite testar as rotas sem sair
# da aplicacao nem abrir o Swagger.

import pandas as pd
import streamlit as st

import utils

chamar = utils.chamar_api

# as consultas oferecidas no explorador, com os parametros que cada uma aceita.
# 'campos' declara o tipo de controle que a pagina deve desenhar para cada parametro.
CONSULTAS = {
    "GET /saude": {"caminho": "/saude", "campos": {}},
    "GET /estatisticas": {"caminho": "/estatisticas", "campos": {}},
    "GET /fontes": {"caminho": "/fontes", "campos": {}},
    "GET /indicadores": {
        "caminho": "/indicadores",
        "campos": {"uf": "ufs", "indicador": "texto", "ano": "ano", "limite": "limite"},
    },
    "GET /ranking": {
        "caminho": "/ranking",
        "campos": {"metodo": "metodo", "indicador": "indicadores", "limite": "limite"},
    },
    "GET /noticias": {
        "caminho": "/noticias",
        "campos": {"fonte": "fontes_noticia", "uf": "uf_unica", "busca": "texto", "limite": "limite"},
    },
    "GET /indicadores/enviados": {"caminho": "/indicadores/enviados", "campos": {}},
    "GET /modelo": {"caminho": "/modelo", "campos": {}},
}

ROTAS = [
    ["GET", "/", "Índice do serviço: apresenta a API e lista as rotas"],
    ["GET", "/saude", "Diz se o serviço responde e se os arquivos de dados estão no lugar"],
    ["GET", "/estatisticas", "Números gerais da base: UFs, indicadores, matérias, palavras"],
    ["GET", "/fontes", "Catálogo das fontes de dados do projeto"],
    ["GET", "/indicadores", "Consulta os indicadores da ODS 4, com filtros combináveis"],
    ["GET", "/ranking", "Índice de Prioridade de Investimento por UF"],
    ["GET", "/noticias", "Consulta o corpus de notícias coletado por raspagem"],
    ["POST", "/indicadores", "Envia novas observações para a base volátil do serviço"],
    ["GET", "/indicadores/enviados", "Lista o que foi enviado nesta execução do serviço"],
    ["DELETE", "/indicadores/enviados", "Descarta o que foi enviado nesta execução"],
    ["GET", "/modelo", "Ficha dos três modelos de linguagem locais e situação de cada carga"],
    ["POST", "/modelo/carregar", "Carrega um modelo na memória, ou tenta de novo após falha"],
    ["POST", "/processar_texto", "Analisa um texto com o modelo de linguagem local"],
    ["POST", "/noticias/sentimento", "Aplica o modelo ao corpus de notícias coletado"],
    ["POST", "/assistente", "Conversa com memória sobre os indicadores, o índice e as notícias"],
]


st.title("🔌 Serviço de API")
st.markdown(
    "A aplicação expõe os mesmos dados por HTTP, num serviço **FastAPI** que roda em "
    "processo separado. Esta página é um cliente dele: tudo que aparece abaixo vem de uma "
    "chamada de rede, não da leitura dos arquivos de `data/`."
)

base = st.text_input(
    "Endereço do serviço",
    value="http://127.0.0.1:8000",
    key="api_base",
    help="Suba o serviço com `uvicorn api:app --reload` na raiz do projeto.",
)

ok, resposta = chamar(base, "/saude")

situacao = st.columns([3, 2])
if ok:
    corpo = resposta["corpo"]
    situacao[0].success(f"Serviço {corpo['situacao']} em `{base}` · consultado em {corpo['momento']}")
    situacao[1].metric("Observações enviadas ao serviço", corpo["observacoes_enviadas_nesta_execucao"])
    ausentes = [nome for nome, existe in corpo["arquivos"].items() if not existe]
    if ausentes:
        st.warning(f"Arquivos ausentes no servidor: {', '.join(ausentes)}")
else:
    situacao[0].error(f"Serviço fora do ar — {resposta}")
    st.info(
        "Para subir o serviço, abra um segundo terminal na raiz do projeto e rode:\n\n"
        "```\nuvicorn api:app --reload\n```\n\n"
        "A documentação interativa fica em http://127.0.0.1:8000/docs. As demais páginas da "
        "aplicação não dependem da API: elas leem os arquivos de `data/` diretamente."
    )

st.divider()

rotas, explorador, envio = st.tabs(["Rotas disponíveis", "Explorador de consultas", "Envio de dados"])

# ------------------------------------------------------------------ aba 1: documentacao

with rotas:
    st.subheader("As quinze rotas do serviço")
    st.dataframe(
        pd.DataFrame(ROTAS, columns=["Método", "Rota", "Função"]),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "A referência escrita está em `4_deployment/api_reference.md`, legível na página de "
        "Documentação. A interativa é gerada pelo próprio FastAPI a partir das anotações de "
        "`api.py`."
    )

    colunas = st.columns(2)
    colunas[0].link_button("📘 Abrir o Swagger UI", f"{base.rstrip('/')}/docs", width="stretch")
    colunas[1].link_button("📗 Abrir o ReDoc", f"{base.rstrip('/')}/redoc", width="stretch")

    st.subheader("Por que a API não duplica o cálculo")
    st.markdown(
        "`api.py` e `utils.py` chamam as mesmas funções de `nucleo.py`, que é pandas puro, sem "
        "Streamlit. O índice que a rota `/ranking` devolve é calculado pelo mesmo código que "
        "monta o ranking da página *Índice de prioridade* — o número não pode divergir entre "
        "os dois canais, o que seria falha de rastreabilidade, não só inconsistência de tela."
    )
    st.code(
        "data/  →  nucleo.py  →  utils.py  →  app.py + paginas/     (painel Streamlit)\n"
        "                    ↘  api.py                              (serviço HTTP FastAPI)\n"
        "                       ↑\n"
        "            modelo_llm.py + assistente.py                  (modelos de linguagem locais)",
        language=None,
    )
    st.caption(
        "As cinco rotas de linguagem natural são exercitadas nas páginas *Análise de "
        "linguagem* e *Assistente ESG*. São as únicas que dependem de modelo: se ele não "
        "carregar, respondem 503 e as dez restantes continuam atendendo."
    )

# ------------------------------------------------------------------ aba 2: consultas get

with explorador:
    escolhida = st.selectbox("Consulta", list(CONSULTAS), key="api_consulta")
    definicao = CONSULTAS[escolhida]
    parametros = {}

    dados_locais = utils.dados_ativos()

    for nome, tipo in definicao["campos"].items():
        if tipo == "ufs":
            valor = st.multiselect("uf", sorted(dados_locais["uf"].unique()), key="api_ufs")
            if valor:
                parametros["uf"] = valor
        elif tipo == "uf_unica":
            valor = st.selectbox("uf", ["(todas)"] + sorted(dados_locais["uf"].unique()), key="api_uf_unica")
            if valor != "(todas)":
                parametros["uf"] = valor
        elif tipo == "indicadores":
            valor = st.multiselect(
                "indicador", utils.indicadores_disponiveis(dados_locais), key="api_indicadores",
                help="Vazio significa todos os indicadores com peso igual.",
            )
            if valor:
                parametros["indicador"] = valor
        elif tipo == "fontes_noticia":
            valor = st.multiselect("fonte", sorted(utils.carregar_noticias()["fonte"].unique()), key="api_fontes")
            if valor:
                parametros["fonte"] = valor
        elif tipo == "metodo":
            parametros["metodo"] = st.radio(
                "metodo", ["min-max entre UFs", "distancia de 100%"], horizontal=True, key="api_metodo",
            )
        elif tipo == "ano":
            anos = ["(todos)"] + sorted(dados_locais["ano"].dropna().unique().astype(int).tolist())
            valor = st.selectbox("ano", anos, key="api_ano")
            if valor != "(todos)":
                parametros["ano"] = int(valor)
        elif tipo == "limite":
            parametros["limite"] = st.slider("limite", 1, 200, 20, key="api_limite")
        elif tipo == "texto":
            valor = st.text_input(nome, key=f"api_texto_{nome}", placeholder="deixe vazio para não filtrar")
            if valor.strip():
                parametros[nome] = valor.strip()

    url = f"{base.rstrip('/')}{definicao['caminho']}"
    st.caption("Requisição que será feita:")
    st.code(f"GET {url}" + (f"\n{parametros}" if parametros else ""), language=None)

    if st.button("Consultar o serviço", type="primary", key="api_consultar"):
        sucesso, resultado = chamar(base, definicao["caminho"], parametros=parametros)
        if not sucesso:
            st.error(resultado if isinstance(resultado, str) else resultado["corpo"])
            utils.registrar(f"consulta à API falhou: {escolhida}")
        else:
            corpo = resultado["corpo"]
            st.success(f"HTTP {resultado['status']}")
            utils.registrar(f"consultou a API em {escolhida}")

            if isinstance(corpo, dict) and isinstance(corpo.get("dados"), list) and corpo["dados"]:
                tabela = pd.DataFrame(corpo["dados"])
                st.caption(
                    f"{corpo.get('retornados', len(tabela))} de {corpo.get('total', len(tabela))} "
                    "registro(s) devolvidos pelo serviço"
                )
                st.dataframe(tabela, hide_index=True, width="stretch", height=360)
                st.download_button(
                    "⬇️ Baixar a resposta em CSV",
                    data=utils.para_csv(tabela),
                    file_name=f"api_{definicao['caminho'].strip('/').replace('/', '_')}.csv",
                    mime="text/csv",
                )
            with st.expander("Resposta JSON completa", expanded=not isinstance(corpo, dict) or "dados" not in corpo):
                st.json(corpo)

# ------------------------------------------------------------------ aba 3: envio post

with envio:
    st.markdown(
        "A rota `POST /indicadores` é o equivalente, por HTTP, ao upload de CSV da página "
        "*Upload e download*. As linhas enviadas são marcadas com `origem = api`, passam a "
        "valer nas consultas e no `/ranking`, e **não são gravadas em disco** — somem quando o "
        "serviço reinicia."
    )

    with st.form("api_post"):
        linha = st.columns(2)
        indicador = linha[0].text_input("indicador", value="Cobertura do programa de reforço")
        indicador_ods = linha[1].text_input("indicador_ods", value="personalizado")

        linha = st.columns(4)
        uf = linha[0].selectbox("uf", sorted(utils.dados_ativos()["uf"].unique()))
        ano = linha[1].number_input("ano", min_value=2000, max_value=2100, value=2026, step=1)
        valor = linha[2].number_input("valor", value=38.0, step=0.5, format="%.1f")
        unidade = linha[3].text_input("unidade", value="%")

        fonte = st.text_input("fonte", value="Enviado pela página de API")
        enviar = st.form_submit_button("Enviar ao serviço", type="primary")

    if enviar:
        corpo = [{
            "indicador": indicador, "uf": uf, "ano": int(ano), "valor": float(valor),
            "indicador_ods": indicador_ods, "unidade": unidade, "fonte": fonte,
        }]
        sucesso, resultado = chamar(base, "/indicadores", metodo="POST", corpo=corpo)
        if not sucesso:
            st.error(resultado if isinstance(resultado, str) else resultado["corpo"])
        else:
            st.success(f"HTTP {resultado['status']} · {resultado['corpo']['aceitas']} observação(ões) aceita(s)")
            st.json(resultado["corpo"])
            utils.registrar(f"enviou 1 observação à API ({uf})")

    st.divider()

    st.subheader("Base volátil do serviço")
    sucesso, resultado = chamar(base, "/indicadores/enviados")
    if not sucesso:
        st.caption("Serviço indisponível, não há o que listar.")
    else:
        enviados = resultado["corpo"]["dados"]
        if not enviados:
            st.info("O serviço não recebeu nenhuma observação nesta execução.")
        else:
            st.dataframe(pd.DataFrame(enviados), hide_index=True, width="stretch")
            if st.button("Descartar tudo no serviço", key="api_delete"):
                chamar(base, "/indicadores/enviados", metodo="DELETE")
                utils.registrar("descartou os dados enviados à API")
                st.rerun()
