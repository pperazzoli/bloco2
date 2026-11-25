# app.py - ponto de entrada da aplicacao
# edited 21-09-2026: o conteudo estatico do tp1 virou paginas/visao_geral.py e este
# arquivo passou a ser o roteador multipagina, com a barra lateral comum a todas
# edited 16-11-2026: entrou a setima pagina, paginas/servico_api.py, cliente da api do
# fastapi; as paginas de dados viraram o grupo "Dados e serviço"
# edited 16-11-2026 (TP4): entrou a oitava pagina, paginas/linguagem.py, que consome as
# rotas de linguagem natural da api e com elas o modelo local de modelo_llm.py
# edited 25-11-2026 (TP5): entrou a nona pagina, paginas/assistente.py, a conversa com
# memoria sobre os dados do projeto, cliente de POST /assistente

import streamlit as st

import utils

st.set_page_config(
    page_title="Bússola ESG Educação",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

utils.iniciar_estado()

navegacao = st.navigation(
    {
        "Projeto": [
            st.Page("paginas/visao_geral.py", title="Visão geral", icon="🧭", default=True),
            st.Page("paginas/documentacao.py", title="Documentação", icon="📄"),
        ],
        "Análise": [
            st.Page("paginas/indicadores.py", title="Indicadores da ODS 4", icon="📊"),
            st.Page("paginas/prioridade.py", title="Índice de prioridade", icon="🎯"),
            st.Page("paginas/noticias.py", title="Notícias e nuvem de palavras", icon="📰"),
            st.Page("paginas/linguagem.py", title="Análise de linguagem", icon="🤖"),
            st.Page("paginas/assistente.py", title="Assistente ESG", icon="💬"),
        ],
        "Dados e serviço": [
            st.Page("paginas/arquivos.py", title="Upload e download", icon="📁"),
            st.Page("paginas/servico_api.py", title="Serviço de API", icon="🔌"),
        ],
    }
)

with st.sidebar:
    st.markdown("### 🧺 Cesta de priorização")
    cesta = st.session_state.cesta
    if cesta:
        st.write(" ".join(f"`{uf}`" for uf in cesta))
        st.caption(f"{len(cesta)} UF(s) selecionada(s)")
        if st.button("Esvaziar cesta", width="stretch"):
            st.session_state.cesta = []
            utils.registrar("esvaziou a cesta")
            st.rerun()
    else:
        st.caption("Vazia. Marque UFs nas páginas de análise para levá-las ao reporte ESG.")

    if st.session_state.dados_extras is not None:
        st.info(f"{len(st.session_state.dados_extras)} linha(s) enviadas nesta sessão estão ativas.")

    st.divider()
    with st.expander("Estado da sessão"):
        st.caption("Cache das leituras: 1 hora. Limpe para reler os arquivos do disco.")
        if st.button("Limpar cache", width="stretch"):
            st.cache_data.clear()
            utils.registrar("limpou o cache")
            st.toast("cache limpo")
        if st.session_state.historico:
            st.code("\n".join(reversed(st.session_state.historico)), language=None)
        else:
            st.caption("Nenhuma ação registrada ainda.")

navegacao.run()
