# Bússola ESG Educação

Aplicação que ranqueia as UFs brasileiras por prioridade de investimento social privado em
educação básica, a partir dos indicadores oficiais da ODS 4, e gera o reporte ESG com a fonte
de cada número. Inclui um assistente com memória que responde perguntas sobre os dados, com
modelo de linguagem rodando na própria máquina.

Projeto organizado segundo o **TDSP** (Team Data Science Process).

---

## Como rodar

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Aplicação:

```bash
streamlit run app.py
```

Serviço de API, num segundo terminal — usado pelas páginas *Serviço de API*, *Análise de
linguagem* e *Assistente ESG*:

```bash
uvicorn api:app
```

Assistente: instale o [Ollama](https://ollama.com) e baixe o modelo uma vez (4,9 GB):

```bash
ollama pull llama3.1:8b
```

- Os dados já estão em `data/`: a aplicação sobe sem coleta. Para atualizar a base, com
  internet, rode `python coleta.py` e `python scraping.py`.
- Os modelos de sentimento e resumo são baixados do HuggingFace na primeira carga, cerca de
  2 GB, e depois rodam offline. O `torch` é a build de CPU.
- Sem a API ou sem o Ollama, só as páginas que dependem deles param, com aviso na tela.
- Avaliação do assistente, cerca de 15 minutos: `python avaliar_assistente.py --detalhe`.

---

## Estrutura

```
tp1/
├── 1_business_understanding/   Project Charter
├── 2_data_acquisition/         Data Summary Report
├── 3_modeling/                 plano de LLM, escolha dos modelos, assistente com memória
├── 4_deployment/               referência da API
├── 5_customer_acceptance/      relatório final
├── data/                       dados coletados: raw/ e processed/
├── paginas/                    as nove páginas do Streamlit
├── app.py                      ponto de entrada do Streamlit
├── api.py                      serviço FastAPI, 15 rotas
├── nucleo.py                   leitura dos dados e cálculo do índice
├── modelo_llm.py               modelos de linguagem locais
├── assistente.py               memória, contexto de dados e prompt do assistente
├── texto.py                    tratamento de texto e conferência do texto gerado
├── utils.py                    cache e estado de sessão do Streamlit
├── coleta.py                   coleta pelas APIs do IBGE
├── scraping.py                 raspagem das notícias
└── avaliar_assistente.py       avaliação do assistente
```

---

## Páginas

| Página | O que faz |
| --- | --- |
| **Visão geral** | Apresentação, métricas e o ciclo do dado ao insight |
| **Indicadores da ODS 4** | Filtros, ranking, mapa, tabela e comparação entre indicadores |
| **Índice de prioridade** | Pesos ajustáveis, ranking, cesta de UFs e download do reporte ESG |
| **Notícias e nuvem de palavras** | Nuvem, estatísticas e cruzamento entre imprensa e carência |
| **Análise de linguagem** | Sentimento e resumo das matérias com modelos locais |
| **Assistente ESG** | Conversa com memória sobre os dados, com fontes e conferência |
| **Upload e download** | Envio de CSV e download dos arquivos |
| **Serviço de API** | Situação, rotas e explorador da API |
| **Documentação** | Os documentos TDSP do repositório |

---

## Documentação

| Estágio TDSP | Documento |
| --- | --- |
| 1. Business Understanding | [Project Charter](1_business_understanding/project_charter.md) |
| 2. Data Acquisition & Understanding | [Data Summary Report](2_data_acquisition/data_summary_report.md) |
| 3. Modeling | [Plano de uso de LLM](3_modeling/plano_llm.md) · [Escolha do modelo de linguagem](3_modeling/modelo_llm.md) · [Assistente com memória](3_modeling/assistente_llm.md) |
| 4. Deployment | [Referência da API](4_deployment/api_reference.md) |
| 5. Customer Acceptance | [Relatório final](5_customer_acceptance/relatorio_final.md) |

Os mesmos documentos podem ser lidos na página *Documentação* da aplicação. A documentação
interativa da API fica em `http://127.0.0.1:8000/docs`, com o serviço no ar.
