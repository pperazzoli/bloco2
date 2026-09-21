# paginas/documentacao.py - leitura dos documentos tdsp dentro da aplicacao
# criado 21-09-2026

import streamlit as st

import utils

st.title("📄 Documentação do projeto")
st.caption("Os arquivos abaixo são lidos do repositório, não há cópia embutida na aplicação.")

escolhido = st.radio(
    "Documento",
    list(utils.DOCS.keys()),
    horizontal=True,
    key="documento_escolhido",
)

conteudo = utils.carregar_documento(escolhido)
caminho = utils.DOCS[escolhido]

cabecalho = st.columns([4, 1])
cabecalho[0].caption(f"`{caminho.relative_to(utils.RAIZ)}` · {len(conteudo.splitlines())} linhas")
cabecalho[1].download_button(
    "⬇️ Baixar",
    data=conteudo.encode("utf-8"),
    file_name=caminho.name,
    mime="text/markdown",
    width="stretch",
)

renderizado, fonte = st.tabs(["Leitura", "Markdown bruto"])
with renderizado:
    st.markdown(conteudo)
with fonte:
    st.code(conteudo, language="markdown")

st.divider()

st.subheader("Estrutura TDSP do repositório")
st.code(
    """
tp1/
├── 1_business_understanding/    project_charter.md
├── 2_data_acquisition/          data_summary_report.md
├── 3_modeling/
├── 4_deployment/
├── 5_customer_acceptance/
├── data/
│   ├── raw/                     noticias_educacao.csv, noticias_corpus.txt, malha_uf.geojson
│   └── processed/               ods4_uf.csv, fontes.csv, noticias_*.csv,
│                                 robots_verificacao.csv
├── paginas/                     paginas da aplicacao streamlit
├── app.py                       roteador multipagina
├── coleta.py                    coleta via API do IBGE
├── scraping.py                  extracao web com Beautiful Soup (checa robots.txt)
├── texto.py                     utilidades de texto
└── utils.py                     cache, estado de sessao e calculos
""",
    language=None,
)
