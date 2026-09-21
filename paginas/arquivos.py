# paginas/arquivos.py - servico de upload e download de arquivos
# criado 21-09-2026

import io
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

import utils

OBRIGATORIAS = ["indicador", "uf", "ano", "valor"]
# cod_uf fica nulo de proposito: linha sem codigo simplesmente nao entra no mapa
OPCIONAIS = {"indicador_ods": "personalizado", "regiao": "Não informada", "unidade": "%",
             "fonte": "Enviado pelo usuário", "fonte_url": "", "cod_uf": None}

st.title("📁 Upload e download de arquivos")
st.markdown(
    "Envie um CSV para complementar os indicadores oficiais. As linhas aceitas ficam no "
    "estado da sessão e passam a alimentar todas as páginas de análise — inclusive o "
    "Índice de Prioridade e o reporte ESG."
)

enviar, baixar = st.tabs(["Enviar arquivo", "Baixar arquivos"])

with enviar:
    st.subheader("1. Formato esperado")
    modelo = pd.DataFrame(
        [
            ["4.1.2", "Taxa de conclusão do ensino médio (20 a 22 anos)", "MG", "Sudeste", 2025, 71.4, "%", "Instituto X"],
            ["personalizado", "Cobertura do programa de reforço", "BA", "Nordeste", 2025, 38.0, "%", "Instituto X"],
        ],
        columns=["indicador_ods", "indicador", "uf", "regiao", "ano", "valor", "unidade", "fonte"],
    )
    st.dataframe(modelo, hide_index=True, width="stretch")
    st.caption(f"Colunas obrigatórias: {', '.join(OBRIGATORIAS)}. As demais são preenchidas se faltarem.")
    st.download_button(
        "⬇️ Baixar o modelo em CSV",
        data=utils.para_csv(modelo),
        file_name="modelo_indicadores.csv",
        mime="text/csv",
    )

    st.subheader("2. Enviar")
    arquivo = st.file_uploader("Arquivo CSV", type=["csv"], key="upload_indicadores")

    if arquivo is not None:
        separador = st.selectbox("Separador", [",", ";", "\t"], key="upload_separador")
        try:
            enviado = pd.read_csv(arquivo, sep=separador)
        except Exception as erro:
            st.error(f"Não foi possível ler o arquivo: {erro}")
            st.stop()

        st.write(f"Arquivo `{arquivo.name}` · {len(enviado)} linhas · {len(enviado.columns)} colunas")
        st.dataframe(enviado.head(20), hide_index=True, width="stretch")

        faltando = [c for c in OBRIGATORIAS if c not in enviado.columns]
        if faltando:
            st.error(f"Faltam colunas obrigatórias: {', '.join(faltando)}")
        else:
            limpo = enviado.copy()
            for coluna, padrao in OPCIONAIS.items():
                if coluna not in limpo.columns:
                    limpo[coluna] = padrao
            limpo["valor"] = pd.to_numeric(limpo["valor"], errors="coerce")
            limpo["ano"] = pd.to_numeric(limpo["ano"], errors="coerce")
            limpo["uf"] = limpo["uf"].astype(str).str.strip().str.upper()
            descartadas = int(limpo["valor"].isna().sum())
            limpo = limpo.dropna(subset=["valor", "uf", "indicador"])
            limpo["origem"] = "usuário"

            aviso = st.columns(3)
            aviso[0].metric("Linhas válidas", len(limpo))
            aviso[1].metric("Linhas descartadas", descartadas)
            aviso[2].metric("Indicadores novos", limpo["indicador"].nunique())
            if descartadas:
                st.warning(f"{descartadas} linha(s) sem valor numérico foram descartadas.")

            if st.button("Incorporar à sessão", type="primary"):
                anterior = st.session_state.dados_extras
                st.session_state.dados_extras = (
                    limpo if anterior is None else pd.concat([anterior, limpo], ignore_index=True)
                )
                utils.registrar(f"enviou {len(limpo)} linha(s) de {arquivo.name}")
                st.success(f"{len(limpo)} linha(s) incorporadas. As páginas de análise já as consideram.")
                st.rerun()

    st.subheader("3. Dados desta sessão")
    extras = st.session_state.dados_extras
    if extras is None or extras.empty:
        st.info("Nenhum dado enviado nesta sessão. Só os indicadores oficiais estão ativos.")
    else:
        st.dataframe(extras, hide_index=True, width="stretch", height=300)
        acoes = st.columns(2)
        acoes[0].download_button(
            "⬇️ Baixar os dados enviados",
            data=utils.para_csv(extras),
            file_name="dados_enviados.csv",
            mime="text/csv",
            width="stretch",
        )
        if acoes[1].button("Descartar os dados enviados", width="stretch"):
            st.session_state.dados_extras = None
            utils.registrar("descartou os dados enviados")
            st.rerun()

with baixar:
    st.subheader("Base consolidada")
    ativos = utils.dados_ativos()
    st.dataframe(ativos.head(50), hide_index=True, width="stretch", height=320)
    st.caption(f"{len(ativos)} linhas ativas, sendo {int((ativos['origem'] == 'usuário').sum())} enviadas nesta sessão.")

    catalogo = [
        ("data/processed/ods4_uf.csv", "Indicadores da ODS 4 por UF (IBGE)"),
        ("data/processed/fontes.csv", "Catálogo de fontes do projeto"),
        ("data/processed/noticias_termos.csv", "Frequência de termos nas notícias"),
        ("data/processed/noticias_por_uf.csv", "Menções por UF nas notícias"),
        ("data/processed/noticias_por_tema.csv", "Notícias por tema da ODS 4"),
        ("data/processed/robots_verificacao.csv", "Verificação de robots.txt dos sites raspados"),
        ("data/raw/noticias_educacao.csv", "Notícias raspadas com Beautiful Soup"),
        ("data/raw/noticias_corpus.txt", "Corpus de texto usado na nuvem de palavras"),
        ("data/raw/malha_uf.geojson", "Malha territorial das UFs (IBGE)"),
    ]

    st.subheader("Arquivos do projeto")
    for caminho_relativo, descricao in catalogo:
        caminho = utils.RAIZ / caminho_relativo
        if not caminho.exists():
            st.caption(f"`{caminho_relativo}` — ausente, rode os scripts de coleta")
            continue
        colunas = st.columns([4, 2, 2])
        colunas[0].markdown(f"**{descricao}**  \n`{caminho_relativo}`")
        colunas[1].caption(f"{caminho.stat().st_size / 1024:.0f} KB")
        colunas[2].download_button(
            "⬇️ Baixar",
            data=caminho.read_bytes(),
            file_name=caminho.name,
            key=f"baixar_{caminho.name}",
            width="stretch",
        )

    st.subheader("Tudo de uma vez")
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as pacote:
        for caminho_relativo, _ in catalogo:
            caminho = utils.RAIZ / caminho_relativo
            if caminho.exists():
                pacote.write(caminho, arcname=Path(caminho_relativo).name)
        extras = st.session_state.dados_extras
        if extras is not None and not extras.empty:
            pacote.writestr("dados_enviados.csv", extras.to_csv(index=False))
    st.download_button(
        "⬇️ Baixar todos os dados em ZIP",
        data=memoria.getvalue(),
        file_name="bussola_esg_educacao_dados.zip",
        mime="application/zip",
        type="primary",
    )
