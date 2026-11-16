# Plano de uso de LLM — Bússola ESG Educação

**Estágio TDSP:** 3. Modeling · **Data:** 2026-11-16

Documento de preparação, não de implementação. Registra quais dados já coletados servem a
tarefas com modelos de linguagem, quais tarefas o problema de negócio deste projeto de fato
pede, e o que precisa estar pronto para que a integração na próxima entrega seja ligar uma
peça, não reescrever o projeto.

---

## 1. Dados disponíveis e o que cada um habilita

| Insumo | Volume | Formato | O que habilita |
| --- | --- | --- | --- |
| `data/raw/noticias_educacao.csv`, coluna `texto` | 105 matérias, 59.185 palavras, média de 563 por matéria | texto livre em português | Resumo, classificação de sentimento, Q&A, extração de entidades |
| `data/raw/noticias_corpus.txt` | 387 KB, uma matéria por bloco | texto puro | Mesmo conteúdo em forma direta para indexação |
| `data/processed/ods4_uf.csv` | 189 observações, 7 indicadores, 27 UFs | tabular numérico | Geração de texto descritivo a partir de números |
| Ranking do índice de prioridade | 27 linhas, recalculado a cada execução | tabular numérico | Narrativa do reporte ESG |
| `data/processed/fontes.csv` | 9 fontes | tabular | Citação de proveniência dentro do texto gerado |
| Colunas `ufs_citadas` e `temas_ods4` | derivadas de 105 matérias por dicionário | listas | Linha de base para medir ganho de um LLM sobre a regra atual |

A última linha é a mais útil para a próxima etapa: a classificação temática e a detecção de
menções de UF já existem, feitas por dicionário de termos em `texto.py`. Isso dá **linha de
base mensurável** — qualquer tarefa de LLM sobre o mesmo corpus pode ser comparada com o que
a regra determinística já acerta, em vez de ser avaliada por impressão.

---

## 2. Tarefas previstas, em ordem de prioridade

A ordem segue a utilidade para o usuário primário do projeto — o analista de
Sustentabilidade que decide onde alocar orçamento e precisa reportá-lo.

### 2.1 Geração de texto: narrativa do reporte ESG · *prioridade alta*

**Tarefa.** `utils.gerar_reporte` hoje produz uma minuta correta e inteiramente tabular:
método, pesos, tabela das UFs priorizadas, lista de fontes e ressalva. Falta a narrativa —
o parágrafo que explica *por que* aquelas UFs foram priorizadas, em linguagem de relatório
de sustentabilidade.

**Insumo.** O ranking já calculado, os pesos escolhidos, a cesta de UFs e as fontes.

**Por que é a primeira.** É a tarefa onde o LLM faz o que o código não faz bem (redigir) e
não faz o que o código faz melhor (calcular). O número continua vindo de `nucleo.py`; o
modelo recebe números já apurados e só os descreve.

**Risco e contenção.** É aqui que mora o risco 8.4 do Project Charter — IA generativa
produzir afirmação incorreta no reporte. Contenção: o modelo nunca calcula nem estima; todo
valor citado no texto é injetado no prompt a partir do ranking, e a minuta gerada é marcada
como rascunho sujeito a revisão humana antes de ir a qualquer relatório público.

### 2.2 Resumo automático do corpus de notícias · *prioridade alta*

**Tarefa.** Resumir as matérias — individualmente, e em um panorama do período por UF ou por
tema da ODS 4 — para que o diagnóstico quantitativo venha com o contexto qualitativo já
legível.

**Insumo.** Coluna `texto`, 563 palavras por matéria em média. Cabe folgado em qualquer
janela de contexto atual, individualmente ou em lotes.

**Onde entra.** A página *Notícias e nuvem de palavras* já tem leitor de matéria: o resumo
gerado vai ao lado do resumo original, identificado como gerado por modelo.

**Avaliação.** Comparação com a coluna `resumo`, que nas três fontes de sindicação é o resumo
escrito pela própria redação — referência humana de graça, sem anotação manual.

### 2.3 Classificação de sentimento · *prioridade média*

**Tarefa.** Classificar cada matéria em positivo, negativo ou neutro quanto à situação da
educação no território citado.

**Insumo.** Título e corpo das 105 matérias.

**Onde entra.** Cruzamento com o índice de prioridade: a página de notícias já cruza menções
na imprensa com carência medida; o sentimento acrescenta direção ao volume.

**Ressalva registrada.** Vale a mesma advertência do risco 8.6 — o sentimento da imprensa
mede atenção e tom editorial, não a situação do território. **Não entra no cálculo do
índice**, em nenhuma hipótese; é camada de contexto, e a tela declara isso. Metade das
matérias é de agência oficial, com tom institucional neutro por natureza, o que limita o
sinal e é motivo de a tarefa não ser a primeira.

### 2.4 Perguntas e respostas sobre o corpus · *prioridade média*

**Tarefa.** Responder perguntas em linguagem natural sobre o material coletado — "que
estados aparecem associados a evasão escolar nas matérias deste período?", "o que as fontes
dizem sobre financiamento da primeira infância?" — citando as matérias usadas.

**Insumo.** As 105 matérias mais a tabela de indicadores, para perguntas que cruzam texto e
número.

**Observação de dimensionamento.** 59 mil palavras é corpus pequeno. Não exige banco
vetorial: a seleção por filtro já existente — fonte, UF, tema, busca textual, tudo disponível
em `GET /noticias` — reduz o conjunto a poucas matérias, que vão inteiras no prompt. Montar
RAG com *embeddings* aqui seria estrutura sem demanda, e fica registrado como desnecessário
nesta escala, não como etapa omitida.

**Requisito não negociável.** Toda resposta cita título, fonte e URL das matérias que a
sustentam. Resposta sem citação não é exibida.

### 2.5 Extração estruturada de entidades · *prioridade baixa*

**Tarefa.** Extrair de cada matéria os valores que a regra atual não alcança: organizações
mencionadas, programas e políticas citados, cifras de investimento anunciadas.

**Por que é a última.** É a tarefa de maior risco de alucinação — inventar uma cifra é pior
que não extrair nenhuma — e a de menor retorno imediato para a decisão de alocação. Depende
de validação cruzada contra o texto original antes de qualquer uso.

---

## 3. O que já está pronto para a integração

O projeto não precisa de reestruturação para receber as tarefas acima. O que a arquitetura
atual já entrega:

**3.1 Corpus limpo e versionado.** Texto já extraído, sem HTML, com data normalizada, fonte
atribuída e URL do original em cada registro. A etapa que normalmente consome o maior tempo
de um projeto de LLM está concluída e versionada em `data/raw/`.

**3.2 Acesso por HTTP.** `GET /noticias?com_texto=true` entrega as matérias filtradas em
JSON. Um script de LLM, um notebook ou um agente externo consome o corpus sem conhecer o
layout de `data/`, sem importar módulo do projeto e sem reimplementar filtro.

**3.3 Núcleo sem Streamlit.** `nucleo.py` é pandas puro. Uma rotina de LLM pode importá-lo e
obter o ranking, os indicadores e as estatísticas sem subir interface — o que importa porque
a geração de texto da tarefa 2.1 recebe números, não texto.

**3.4 Linha de base para comparação.** As colunas `temas_ods4` e `ufs_citadas` dão referência
determinística contra a qual medir qualquer classificação por modelo.

**3.5 Lugar na interface.** A aplicação é multipágina com navegação por grupos: a tarefa de
LLM entra como página nova em `paginas/`, sem tocar nas existentes. O padrão está
estabelecido pela própria página *Serviço de API*, acrescentada nesta entrega.

**3.6 Estado de sessão e cache.** Já há onde guardar resultado de chamada custosa sem
repeti-la: `@st.cache_data` para resultado serializável e `st.session_state` para o que o
usuário acumula na sessão. Chamada a modelo é a operação mais lenta e mais cara do projeto,
e a camada que a protege já existe.

---

## 4. O que falta decidir na próxima entrega

**4.1 Provedor e modelo.** Decisão em aberto. Critérios: suporte a português, custo por
milhão de *tokens* no volume do projeto (59 mil palavras ≈ 90 mil *tokens* para processar o
corpus inteiro uma vez) e possibilidade de execução local para o caso de a credencial não
poder ser publicada.

**4.2 Guarda da credencial.** `.streamlit/secrets.toml` já está no `.gitignore`, e é o lugar
previsto para a chave de API. Nenhuma credencial entra no repositório.

**4.3 Tratamento de indisponibilidade.** A aplicação hoje sobe sem rede, por decisão de
projeto registrada na seção 10 do Project Charter. Uma chamada a modelo rompe isso. Regra a
manter: a falha de uma chamada de LLM degrada a funcionalidade de texto e **não** derruba o
painel — mesma postura adotada com a API, cuja ausência a página *Serviço de API* informa na
tela sem afetar as demais.

**4.4 Marcação do conteúdo gerado.** Todo texto produzido por modelo precisa aparecer
identificado como tal na interface e no reporte, com data de geração e o modelo usado. É
exigência de governança, não escolha estética: o reporte ESG é documento que a empresa
publica, e a distinção entre dado apurado e texto gerado tem de ser visível ao leitor.

**4.5 Limite de custo por sessão.** Um painel interativo pode disparar chamadas a cada
mudança de filtro. A geração precisa ficar atrás de ação explícita do usuário — um botão —
nunca de recarregamento de página.
