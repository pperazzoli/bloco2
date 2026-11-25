# paginas/documentacao.py - leitura dos documentos tdsp dentro da aplicacao
# criado 21-09-2026
# edited 16-11-2026: a lista de documentos passou de dois para quatro com a entrada do plano
# de uso de llm e da referencia da api; a lista vem de utils.DOCS, nada mudou aqui alem da
# arvore de estrutura do repositorio
# edited 16-11-2026 (TP4): quinto documento, a escolha do modelo de linguagem. como antes, a
# lista vem de utils.DOCS e so a arvore de estrutura mudou neste arquivo
# edited 25-11-2026 (TP5): sexto e setimo documentos, o do assistente com memoria e o
# relatorio final; de novo so a arvore mudou aqui

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
├── 3_modeling/                  plano_llm.md, modelo_llm.md, assistente_llm.md
├── 4_deployment/                api_reference.md
├── 5_customer_acceptance/       relatorio_final.md
├── data/
│   ├── raw/                     noticias_educacao.csv, noticias_corpus.txt, malha_uf.geojson
│   └── processed/               ods4_uf.csv, fontes.csv, noticias_*.csv,
│                                 robots_verificacao.csv
├── paginas/                     as nove paginas da aplicacao streamlit
├── app.py                       roteador multipagina
├── api.py                       servico HTTP com FastAPI (15 rotas)
├── assistente.py                memoria, contexto de dados e prompt da conversa
├── avaliar_assistente.py        verificacao do assistente em quatro condicoes
├── modelo_llm.py                tres modelos de linguagem locais, sem framework web
├── nucleo.py                    leitura dos arquivos e calculo, sem streamlit
├── coleta.py                    coleta via API do IBGE
├── scraping.py                  extracao web com Beautiful Soup (checa robots.txt)
├── texto.py                     utilidades de texto e conferencia do resumo gerado
└── utils.py                     cache do streamlit, estado de sessao e chamada a API
""",
    language=None,
)
