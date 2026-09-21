# app.py - ponto de entrada da aplicacao
# edited 21-09-2026: o conteudo estatico do tp1 virou paginas/visao_geral.py e este
# arquivo passou a ser o roteador multipagina, com a barra lateral comum a todas

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
        ],
        "Dados": [
            st.Page("paginas/arquivos.py", title="Upload e download", icon="📁"),
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
