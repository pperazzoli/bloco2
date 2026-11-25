# Escolha e integração do modelo de linguagem local — Bússola ESG Educação

**Estágio TDSP:** 3. Modeling · **Data:** 2026-11-16

Documento de decisão. Registra quais modelos de linguagem o projeto adotou, quais candidatos
foram medidos e descartados, com que números, como foram integrados ao serviço FastAPI
rodando inteiramente na máquina local, e o que cada um sabe e não sabe fazer.

Complementa `plano_llm.md`, que é o documento de preparação: lá estão as tarefas que o
problema de negócio pede, aqui estão as que foram implementadas e por quê.

> **São duas tarefas, e elas não têm o mesmo risco.** A classificação de sentimento escolhe
> entre três rótulos fixos; o resumo **redige**. O primeiro não pode inventar nada, o segundo
> pode e inventou na verificação. A seção 5.2 registra o que ele inventou, com o texto gerado
> lado a lado com o original, e a 5.3 descreve a conferência automática que passou a apontar
> essas invenções em todo resumo. Quem for ler só um trecho deste documento, leia aqueles.
>
> **edited 25-11-2026 (TP5):** o registro de modelos ganhou uma terceira tarefa, `conversa`,
> usada pelo assistente com memória da solução final. O modelo é o `llama3.1:8b`, servido
> pelo Ollama local em vez de carregado pelo `transformers`, e a escolha está em
> [`assistente_llm.md`](assistente_llm.md). Os dois modelos deste documento não mudaram, e a
> conferência da seção 5.3 ganhou uma segunda consumidora, a resposta do assistente.

---

## 1. Da prioridade planejada à tarefa implementada

O `plano_llm.md` ordenou cinco tarefas por utilidade para o usuário primário. As duas
primeiras — narrativa do reporte ESG (2.1) e resumo automático do corpus (2.2) — são
**gerativas**. A terceira, classificação de sentimento (2.3), é de **classificação**.

A exigência de execução local inverte essa ordem, e é a primeira decisão deste documento:

| | Tarefa gerativa (2.1, 2.2) | Tarefa de classificação (2.3) |
| --- | --- | --- |
| Arquitetura necessária | decoder ou encoder-decoder (mT5, mBART, Llama) | encoder com cabeça de classificação |
| Tamanho mínimo útil em português | 1,2 GB (mT5-base) a vários GB | 0,5 a 1,1 GB |
| Custo por item em CPU | dezenas de segundos por resumo | dezenas de milissegundos |
| Saída | texto novo, que pode conter afirmação falsa | um rótulo entre três, mais a pontuação de cada |
| Risco de alucinação | existe e precisa de contenção | **inexistente por construção** |

A tarefa gerativa é a mais útil e a mais cara. Num ambiente com GPU ou com API de provedor,
seria a escolha. Em CPU, um resumo de 563 palavras com mT5-base leva ordem de dezenas de
segundos, o que é incompatível com um painel interativo — e o modelo pequeno o bastante para
caber no orçamento ainda produziria português de qualidade ruim.

**Decisão inicial: a tarefa implementada seria a classificação de sentimento**, e a tabela
acima explica por quê — era a única que cabia no orçamento de CPU sem degradar a experiência
de uso.

**Decisão revista: a tarefa de resumo entrou também.** A revisão não desfaz o raciocínio
acima; ele continua valendo e está confirmado pela medição da seção 3. O que mudou foi o
custo medido do candidato escolhido: o PTT5 base, com 223 milhões de parâmetros, resume uma
matéria em cerca de 4 segundos em CPU. Isso é lento demais para rodar sobre o corpus inteiro
em lote — 105 matérias levariam perto de sete minutos —, e aceitável para uma matéria por
vez, lida na tela. A tarefa entrou nesse formato e só nesse: **o resumo é uma matéria por
vez, sob um botão; a classificação é que roda em lote.**

A narrativa do reporte ESG (tarefa 2.1) continua fora, e por um motivo diferente do custo:
ela exige um modelo que receba uma tabela de números e redija sobre ela sem errar nenhum.
Um modelo de 223 milhões de parâmetros treinado para resumir notícia não faz isso — a seção
5 mostra que ele inventa números quando resume texto que não os tem.

**Sobre o risco 8.4, uma correção de rumo que precisa ficar explícita.** A primeira versão
deste documento afirmou que o risco 8.4 — "IA generativa produzir afirmação incorreta no
reporte" — não precisava de contenção nesta entrega, porque um classificador não gera
afirmação nenhuma. Aquilo era verdade enquanto havia só o classificador. **Com a entrada do
resumo, deixou de ser:** o modelo de resumo gera texto, e na verificação produziu uma data,
um estado e uma cifra que não estavam no original. As quatro regras de contenção do risco
8.4 voltam a valer integralmente, e o campo `gerativo` da API existe justamente para que
nenhum consumidor confunda as duas coisas.

---

## 2. Critérios de seleção e os candidatos medidos — tarefa de sentimento

Os três critérios do enunciado foram aplicados nesta ordem: **acessibilidade local** primeiro,
porque um modelo que não carrega está fora independentemente de quão bom seja; **desempenho**
em seguida, medido no corpus deste projeto e não em métrica publicada; **custo computacional
local** por último, como critério de desempate.

### 2.1 Medição

Dois candidatos foram carregados de fato e medidos. O procedimento tem duas partes:

1. **Seis frases de controle**, escritas para o domínio do projeto, com rótulo esperado
   evidente para um leitor humano: duas positivas, duas negativas, duas neutras de registro
   institucional.
2. **Trinta matérias reais** do corpus (`data/raw/noticias_educacao.csv`), analisadas pelo
   título mais resumo.

O segundo teste não tem gabarito — o corpus não é anotado. Ele serve a outra pergunta, que
no caso deste projeto é a decisiva: **o modelo distingue algo, ou colapsa tudo num rótulo?**

### 2.2 Resultado

| | `lxyuan/distilbert-base-multilingual-cased-sentiments-student` | `cardiffnlp/twitter-xlm-roberta-base-sentiment` |
| --- | --- | --- |
| Arquitetura | DistilBERT multilingue destilado | XLM-RoBERTa base |
| Parâmetros | 135 milhões | 278 milhões |
| Tamanho no cache local | 545 MB | 1,1 GB de pesos (2,2 GB no cache, que guarda mais de um formato) |
| Tokenizador | WordPiece, carrega sem dependência extra | SentencePiece, **exige o pacote `sentencepiece`** |
| Carga a partir do cache | 1,4 s | 2,1 s |
| Inferência em CPU | 44 ms por matéria | 80 ms por matéria |
| **Frases de controle** | **3 de 6** | **6 de 6** |
| 30 matérias reais | 26 positivas, 2 neutras, 2 negativas | 25 neutras, 5 positivas |
| Treinado em | avaliações de produto, multilingue | 198 milhões de postagens em 8 idiomas, português incluído |
| Decisão | **descartado** | **adotado** |

### 2.3 Por que o candidato mais leve e mais rápido foi descartado

O modelo destilado é melhor nos dois critérios de custo: menos da metade dos parâmetros,
quase metade do tempo de inferência, um terço do espaço em disco, e nenhuma dependência
adicional. Ainda assim foi descartado, porque falha no critério que vem antes: ele não mede
o que diz medir neste corpus.

- Errou metade das frases de controle, inclusive uma denúncia explícita de falta de
  professores e de merenda, classificada como positiva.
- Em 30 matérias reais, atribuiu `positivo` a 26. Entre elas, "24º Encontro de Administração
  do Amazonas discute gestão, cultura e impacto social", que é convocação de evento, e
  "Inocentes atrás das grades", que é reportagem sobre encarceramento indevido.
- O rótulo `neutro` nunca passou de 0,15 de pontuação em nenhuma das frases de controle. A
  classe existe no cabeçalho do modelo e está inativa na prática.

A causa provável é o dado de treino: avaliações de produto quase não contêm texto neutro,
porque quem escreve uma avaliação está tomando posição. Um modelo destilado desse material
herda a ausência da classe neutra. **Em um corpus em que metade das matérias é release
institucional, um modelo sem classe neutra funcional não serve** — e um modelo que acerta
rápido o rótulo errado é pior que um modelo lento, porque o número errado circula.

### 2.4 Por que o modelo adotado passou

O `cardiffnlp/twitter-xlm-roberta-base-sentiment` acertou as seis frases de controle, com
margem folgada nas duas neutras (0,88 e 0,87). Nas 30 matérias reais classificou 25 como
neutras e 5 como positivas, nenhuma como negativa — o que, para um corpus formado por
agência oficial e por comunicação de fundações e institutos, é a **descrição correta** do
material, não falta de sensibilidade do modelo.

O custo de adotá-lo é conhecido e aceitável: o dobro dos parâmetros, 80 ms por item em CPU,
e o pacote `sentencepiece` no `requirements.txt`. A 80 ms por matéria, o corpus inteiro — 105
matérias — é classificado em cerca de 9 segundos num processador comum, sem GPU.

### 2.5 Acessibilidade local: o que a medição revelou e custou uma linha no requirements

A primeira tentativa de carregar o modelo adotado **falhou**, e a falha é instrutiva o
bastante para ficar registrada. O tokenizador do XLM-RoBERTa é SentencePiece, e o
`transformers` precisa da biblioteca homônima para converter o vocabulário. Sem ela a carga
não acontece:

```
SentencePieceExtractor requires the SentencePiece library but it was not found
...
ValueError: `tiktoken` is required to read a `tiktoken` file.
```

A biblioteca tem distribuição compilada para o Python 3.14 deste ambiente, foi acrescentada
ao `requirements.txt` com o comentário explicando por que está lá — nenhum módulo do projeto
a importa diretamente — e o problema desapareceu. O critério de acessibilidade local do
enunciado não é uma formalidade: foi o critério que efetivamente barrou um candidato por
algumas horas e que determina a linha extra na lista de dependências.

---

## 3. Critérios de seleção e os candidatos medidos — tarefa de resumo

A primeira versão deste documento descartou os modelos de resumo **na triagem, sem medição**,
estimando dezenas de segundos por item em CPU. A estimativa foi depois verificada, e estava
errada por um fator grande: o modelo escolhido resume em cerca de 4 segundos. Fica o
registro, porque a lição é metodológica — a triagem por ordem de grandeza dispensou um
candidato que a medição aprovaria, e só a medição revelou isso.

### 3.1 O impedimento que apareceu primeiro não foi de custo

Nenhum dos candidatos carregou na primeira tentativa, e por uma razão que não tem nada a ver
com o modelo:

```
KeyError: 'The task summarization has been removed from transformers.
Use the `text-generation` pipeline with a chat model instead.'
```

O **transformers 5 removeu a tarefa `summarization` do `pipeline`**. O que saiu foi o atalho,
não o suporte: os modelos *sequence-to-sequence* continuam carregando por
`AutoModelForSeq2SeqLM` e gerando por `.generate()`. O projeto passou a usar esse caminho,
embrulhado na classe `MotorGerativo` de `modelo_llm.py`, com uma vantagem lateral: os
parâmetros de geração ficaram à vista na constante `GERACAO`, em vez de escondidos num padrão
de pipeline.

É o segundo achado de **acessibilidade local** desta entrega, depois do `sentencepiece` da
seção 2.5. Os dois seguem o mesmo padrão: o que trava a adoção de um modelo local raramente é
o modelo: é a ferramenta em volta dele.

### 3.2 Os dois candidatos, medidos sobre o corpus

| | `recogna-nlp/ptt5-base-summ-xlsum` | `csebuetnlp/mT5_multilingual_XLSum` |
| --- | --- | --- |
| Arquitetura | T5 em português (PTT5) | mT5 multilingue, 45 idiomas |
| Parâmetros | **223 milhões** | 582 milhões |
| Tamanho no cache local | **892 MB** | 2,3 GB |
| Por matéria, busca gulosa | **1,2 a 1,7 s** | 3,2 a 3,6 s |
| Por matéria, feixe de 4 | **3,5 a 4,7 s** | 6,7 a 12,1 s |
| Treino | XL-Sum, porção em português | XL-Sum, 45 idiomas |
| Decisão | **adotado** | descartado |

O mT5 produz português um pouco mais fluente — mas custa 2,6 vezes mais disco e de 2 a 3
vezes mais tempo, e **alucina igual**: resumindo a matéria do curso de educação integral,
escreveu "O Itaú Social lançou **nesta quarta-feira** um novo curso gratuito e on-line para
**estudantes** do 6º ao 9º ano", sendo que a data não está no texto e o curso é para
gestores de rede e professores, não para estudantes. Entre dois modelos que erram do mesmo
jeito, o critério de custo decide, e decide pelo menor.

### 3.3 Busca em feixe, que aqui é decisão de contenção e não de qualidade

A geração usa `num_beams=4`. A busca gulosa é duas a três vezes mais rápida e seria a escolha
óbvia pelo critério de custo — mas foi ela que produziu as piores invenções na medição. Com
busca gulosa, o PTT5 expandiu a sigla ISP como "Instituto de Pesquisa Social Privado" (é
*Investimento* Social Privado) e enfeitou dois dos três resumos com "é um dos pilares da
democracia" e "um dos pilares da política educacional brasileira", frases que não estão em
texto nenhum. Com feixe de 4, os mesmos três resumos ficaram mais curtos e mais colados ao
original.

**Pagar 2 a 3 segundos por matéria para reduzir invenção é troca boa** num projeto cujo
produto final é um reporte ESG. Os parâmetros são fixos e estão declarados em
`modelo_llm.GERACAO`; não são expostos ao usuário, porque resumo que muda de forma a cada
clique não serve a um relatório.

---

## 4. Integração local com o FastAPI

### 4.1 Onde os modelos vivem, e por que não é dentro do Streamlit

```
data/  →  nucleo.py  →  utils.py  →  app.py + paginas/     (painel Streamlit)
                    ↘  api.py                              (serviço HTTP FastAPI)
                       ↑
            modelo_llm.py                                  (modelos de linguagem locais)
```

`modelo_llm.py` não importa `fastapi` nem `streamlit`, pela mesma razão que `nucleo.py` não
importa: os modelos são recurso do projeto, não do servidor web. Quem os carrega é o processo
do FastAPI, uma vez cada por execução.

A página *Análise de linguagem* da aplicação Streamlit **não carrega modelo nenhum**: é
cliente HTTP das rotas, como a página *Serviço de API*. A razão é de ciclo de vida. O
Streamlit reexecuta o script inteiro a cada interação do usuário — mover um controle
reexecuta a página. Modelos de centenas de milhões de parâmetros não podem ser carregados
nesse ritmo. Do outro lado do HTTP, a carga acontece uma vez por execução do serviço, não uma
vez por clique.

### 4.2 Um registro por tarefa, não um modelo global

Com a entrada do resumo, o que era um estado único virou um registro: `MODELOS` tem uma
entrada por tarefa, e `_ESTADO` guarda separadamente o pipeline, o instante da carga, o tempo
que levou e o erro de cada uma. A consequência prática é que **as falhas não se contaminam**:
se o modelo de resumo não carregar, a classificação continua respondendo 200, e o 503 sai só
nas rotas que precisam do que faltou.

Cada entrada do registro declara `gerativo`. Não é rótulo decorativo: é o que separa o modelo
que escolhe entre rótulos fixos daquele que produz texto novo, e é essa distinção que decide
quais regras de contenção do risco 8.4 do Project Charter se aplicam ao resultado. O campo
atravessa o sistema inteiro — está no registro, na resposta da API e na tela.

### 4.3 Carga preguiçosa, em memória, com falha memorizada

Cada modelo é carregado na primeira chamada que precisa dele, não na subida do serviço.
Quatro consequências desejadas:

1. `uvicorn api:app` sobe em menos de um segundo, como antes do TP4.
2. Quem usa só as rotas de dados nunca paga o custo de carga nenhuma.
3. Quem usa só o sentimento nunca carrega o modelo de resumo, e vice-versa.
4. `GET /saude` e `GET /modelo` relatam a situação dos dois **sem carregá-los**, e por isso
   continuam baratas o suficiente para servir a monitoramento.

A falha é memorizada de propósito: sem isso, cada requisição repetiria uma tentativa
impossível de carga e toda chamada ficaria lenta sem mudar de resultado.
`POST /modelo/carregar?tarefa=<tarefa>` é o caminho explícito da nova tentativa, para quando
a causa da falha tiver sido removida.

### 4.4 Execução offline

Os pesos são baixados uma vez para o cache local do HuggingFace
(`~/.cache/huggingface/hub`), e dali em diante a carga não toca a rede. `GET /modelo` informa
em `ja_baixado` se os pesos de cada modelo já estão em disco e em `cache_local` onde estão, o
que permite distinguir, antes de tentar, "vai demorar porque precisa baixar" de "vai demorar
porque precisa carregar".

### 4.5 Um caminho de código para um texto e para muitos

`classificar` e `resumir` recebem sempre uma lista e devolvem sempre uma lista, mesmo para um
único texto. O motivo é prático: o pipeline do `transformers` devolve formatos diferentes
para entrada única e entrada em lote, e tratar os dois seria código de desempacotamento
duplicado, do tipo que divergiria com o tempo. A rota de texto único chama
`processar(tarefa, [texto])[0]`.

`resumir` acrescenta a cada resultado a conferência de `texto.conferir_resumo`, descrita na
seção 5.3. Fica dentro da função, e não a cargo de quem chama, para que nenhum resumo saia
do projeto sem ela.

### 4.6 As quatro rotas

| Método e rota | Função |
| --- | --- |
| `GET /modelo` | Ficha dos dois modelos e situação de cada carga. Não carrega. |
| `POST /modelo/carregar` | Carrega um modelo na memória, ou tenta de novo após falha. |
| `POST /processar_texto` | **Rota pedida pelo enunciado.** Processa um texto na tarefa pedida. |
| `POST /noticias/sentimento` | Aplica a classificação ao corpus já coletado e agrega por rótulo e por UF. |

`POST /processar_texto` tem o campo `tarefa` desde a primeira versão, quando havia uma tarefa
só, justamente para que a segunda não mudasse o contrato. Foi o que aconteceu: `sentimento`
continua sendo o padrão e quem já consumia a rota não precisou mudar o corpo da requisição. O
que mudou foi a **forma da resposta** — o cabeçalho comum ficou, e o resultado passou a vir
num bloco com o nome da tarefa, `sentimento` ou `resumo`, com o outro omitido em vez de nulo.
É a forma que o enunciado descreve: tipo de análise realizada mais os resultados gerados.

`POST /noticias/sentimento` continua valendo só para a classificação, e isso é decisão, não
omissão: resumir as 105 matérias levaria perto de sete minutos de CPU, e um resumo só vale
alguma coisa lido um a um. O resumo em lote seria um botão que custa sete minutos para
produzir texto que ninguém vai ler inteiro.

A referência completa das rotas, com parâmetros e exemplos, está em
`4_deployment/api_reference.md`.

---

## 5. O que cada modelo sabe e não sabe fazer

### 5.1 Limite medido no sentimento: o registro do relato domina o fato relatado

O achado mais importante da verificação, e o que mais afeta a leitura dos resultados. A
mesma notícia recebe rótulos diferentes conforme a moldura:

| Texto | Rótulo | Pontuações |
| --- | --- | --- |
| "Faltam professores, as escolas estão sem merenda e os repasses atrasaram outra vez." | `negativo` | negativo 0,86 · neutro 0,12 · positivo 0,01 |
| "A evasão escolar voltou a crescer e o abandono atingiu o maior nível da série histórica, **aponta o levantamento divulgado nesta semana**." | `neutro` | neutro 0,54 · negativo 0,34 · positivo 0,13 |

As duas frases relatam fato igualmente ruim. A segunda, trazida na moldura jornalística, é
classificada como neutra — o modelo mede o **tom de quem escreve**, e o tom de quem relata um
dado é neutro mesmo quando o dado é péssimo.

Isso não é defeito a corrigir: é a definição da tarefa. Análise de sentimento mede tom, não
valência do fato. A consequência prática tem de ficar explícita, porque é onde um leitor
apressado erraria: **`neutro` não significa "situação estável no território"**. Significa
"texto escrito em registro informativo". As duas frases da tabela estão lado a lado na
interface, como exemplos, justamente para que quem usa a tela veja o limite em vez de ler
sobre ele.

### 5.2 Limite medido no resumo: o modelo inventa, e inventou número

É o achado mais importante desta entrega, e o que a primeira versão deste documento afirmou
não existir. Os dois resumos abaixo saíram da verificação automatizada, com o modelo adotado
e os parâmetros declarados em `GERACAO`.

**Caso 1 — inventou uma data, um ordinal e trocou a série escolar.**

> *Entrada (trecho):* "O Itaú Social e o Instituto Reúna lançam um curso gratuito e on-line
> sobre a implementação da educação integral nos anos finais do Ensino Fundamental. A
> formação é voltada a gestores de redes de ensino e a professores **do sexto ao nono ano**…"
>
> *Gerado:* "O Itaú Social e o Instituto Reúna lançam **nesta segunda-feira** a **primeira**
> formação para gestores de redes de ensino e professores **do terceiro e último ano** do
> Ensino Fundamental."

Três invenções numa frase: a data não está no texto, "primeira" não está no texto, e "do
terceiro e último ano" contradiz o original.

**Caso 2 — inventou um estado e uma cifra.**

> *Entrada, inteira:* "A rede estadual ampliou a oferta de vagas em creche e reduziu pela
> metade a fila de espera, segundo o balanço da secretaria de educação."
>
> *Gerado:* "A rede estadual de ensino estadual **do Rio Grande do Sul** ampliou a oferta de
> vagas em creches e creche para **mais de mil estudantes**, de acordo com a secretaria de
> educação do Estado."

A entrada não nomeia estado nenhum e não traz número nenhum. O modelo produziu os dois. **Num
projeto cujo produto é um reporte ESG sobre alocação de investimento por UF, uma cifra
inventada atribuída a um estado inventado é exatamente o dano que o risco 8.4 descreve** — e
note que o texto gerado é gramatical, plausível e soa apurado.

**Por que isso acontece, e por que não se "conserta" com ajuste de parâmetro.** O modelo foi
treinado para produzir a primeira frase de uma notícia a partir do corpo dela. Quando o corpo
não tem matéria suficiente para uma frase de abertura — como no caso 2, de 25 palavras —, ele
preenche com o que é estatisticamente provável num texto desse gênero: um estado, um número,
uma data. A geração abstrativa não distingue "o que o texto diz" de "o que textos assim
costumam dizer".

**O que o projeto faz a respeito**, já implementado:

1. **Conferência automática de todo resumo contra o texto de origem** — a seção 5.3, que é a
   principal contenção e não depende de o leitor estar atento.
2. O campo `gerativo` vem `true` na resposta, e a tela o exibe. Nenhum consumidor recebe o
   resumo sem saber que é texto produzido por modelo.
3. O `aviso` de toda resposta de resumo diz, com estas palavras, que o resumo "pode afirmar o
   que não está no original — inclusive números".
4. A interface mostra o resumo gerado **ao lado do resumo escrito pela redação**, quando a
   matéria vem do corpus. É a comparação prevista na tarefa 2.2 do `plano_llm.md`, e serve
   para que o limite seja visto, não lido.
5. O resumo **não alimenta nada**: não entra no reporte ESG, não é gravado em `data/`, não é
   insumo de cálculo. É leitura de tela e nada mais.
6. A busca em feixe foi escolhida sobre a gulosa por reduzir invenção, ao custo de 2 a 3
   segundos por matéria (seção 3.3).

### 5.3 Conferência automática do resumo contra a fonte

A contenção dos itens 2 a 5 acima depende de o leitor prestar atenção ao aviso. Esta não: ela
aponta o dedo no termo inventado.

**Como funciona, e por que não usa modelo.** `texto.conferir_resumo` procura no resumo os
três tipos de termo que um modelo gerativo inventa com mais frequência — **número, data e
nome próprio** — e checa cada um no texto de origem, por palavra inteira, sem acento e sem
diferenciar maiúsculas. Nomes compostos contam como um item só, de modo que "Rio Grande do
Sul" é apontado uma vez e não três. Não há segunda passagem de modelo, de propósito: um
modelo que confere outro tem o mesmo problema do primeiro, e custaria o mesmo tempo de CPU.

Mora em `texto.py`, ao lado de `mencoes_uf` e `temas_do_texto`, porque é da mesma família —
comparação léxica sobre texto em português, sem dependência de modelo nem de framework web.

**A conferência é obrigatória, não opcional.** `modelo_llm.resumir` a executa e a anexa a
todo resultado; nenhum resumo sai da função sem ela. Deixá-la a cargo de quem chama seria
confiar em que todo consumidor se lembre de pedi-la — e é justamente o resumo não conferido
que produz o dano.

**O que ela faz com os casos da seção 5.2:**

| Caso | Apontado |
| --- | --- |
| Caso 1 | `segunda-feira` (data), `primeira`, `terceiro`, `último` (números) — **4 de 7 termos** |
| Caso 2 | `Rio Grande do Sul`, `Estado` (nomes), `mil` (número) — **3 de 3 termos** |
| Resumo fiel, de controle | nada: os 4 termos verificáveis estão todos no original |

Numa execução pela interface, com a mesma entrada curta do caso 2, o modelo produziu desta
vez **"Cochabamba"** — cidade boliviana, em matéria sobre educação brasileira — além de
"Estado de Goiás" e "mil". A conferência apontou os quatro termos, e a taxa de compressão
veio em **132%**: o resumo ficou maior que a entrada. Os dois sinais juntos dizem a mesma
coisa, e dizem na tela.

**O que ela não faz, e fica declarado.** É comparação **léxica, não semântica**: diz se o
termo aparece no original, não se o resumo é fiel ao sentido dele. Um resumo que inverta uma
relação entre duas entidades que estão ambas no texto passa sem ser apontado. E ela erra de
propósito para o lado de apontar demais — no caso 2 apontou também "Estado", que o original
tem como "estadual". É escolha consciente: **um termo apontado que está no texto custa um
olhar; um termo inventado que passa custa uma afirmação falsa num reporte.**

### 5.4 O que o resultado dos modelos não pode ser usado para dizer

- **Não entra no cálculo do Índice de Prioridade de Investimento, em nenhuma hipótese.** É a
  ressalva do risco 8.6 do Project Charter: imprensa mede atenção editorial, não situação do
  território. O campo `aviso` de toda resposta das rotas de linguagem repete isso, e a tela
  o exibe.
- **Não mede a qualidade da educação na UF citada.** Uma UF com saldo negativo pode ser a que
  tem cobertura jornalística mais atenta, não a que tem a pior rede.
- **Não é medida de volume.** Metade do corpus vem de uma única agência oficial, e o número
  de matérias por UF reflete a pauta dessas fontes.

### 5.5 Truncagem, declarada e não escondida

Os dois modelos têm janela de 512 tokens. O corpo integral das matérias tem 563 palavras em
média, o que dá entre 700 e 1.250 tokens — passa da janela. Três decisões:

1. O padrão de `POST /noticias/sentimento` é analisar **título mais resumo**, o lead da
   matéria: cabe inteiro na janela e é onde o tom editorial se concentra.
2. Com `campo=texto`, o corpo integral é enviado e **truncado, não rejeitado**, e cada linha
   da resposta traz `tokens` e `texto_truncado`. Na verificação, as 5 matérias testadas com
   corpo integral vieram todas marcadas como truncadas, com 726 a 1.238 tokens.
3. Na tela, a truncagem é dita em proporção, não em jargão: ao resumir uma matéria de 1.161
   tokens, a página avisa que **o modelo viu 44% do texto**.

Truncar silenciosamente seria o erro nas duas tarefas, e é pior no resumo. Um rótulo truncado
é um rótulo sobre o começo do texto; **um resumo truncado parece um resumo do texto inteiro**,
e nada na sua forma denuncia que não é. Por isso a mensagem da tela, nesse caso, diz com
todas as letras que o resumo vale para o começo do texto "e não para o todo, o que é fácil de
esquecer quando se lê só o resumo".

---

## 6. Tratamento de erro

O princípio é o do Project Charter, seção 10, estendido aos modelos: **a indisponibilidade de
um modelo degrada a funcionalidade dele e não derruba o resto** — nem as rotas de dados, nem
a outra tarefa de linguagem.

| Situação | Código | O que a resposta traz |
| --- | --- | --- |
| Pesos ausentes, sem rede, `transformers` não instalado, memória insuficiente | **503** | o motivo, os modelos do serviço, quatro passos do que fazer, e a lista do que continua funcionando |
| Tarefa fora do registro em `POST /modelo/carregar` | **422** | as tarefas que existem |
| Texto com menos de 20 caracteres úteis, ou só espaços | **422** | o campo apontado e a regra violada |
| `tarefa` ou `campo` com valor desconhecido | **422** | os valores aceitos |
| `limite` acima do máximo | **422** | o limite e o valor recebido |
| Filtro que não casa com nenhuma matéria | **404** | os filtros como foram interpretados e o total do corpus |
| Modelo carregado, falha ao processar o texto | **500** | o tipo da exceção e que o modelo está carregado |

As três exceções de `modelo_llm.py` — `ModeloIndisponivel`, `ErroDeInferencia` e
`TarefaDesconhecida` — são traduzidas por *exception handlers* registrados no `app`, em um
lugar só, em vez de um `try/except` repetido em cada rota. A distinção importa a quem
consome: **503** é o serviço dizendo que o modelo não está disponível e que a requisição pode
ser repetida depois; **500** é falha ao processar aquele texto específico, com o modelo de
pé; **422** é o pedido que está errado, não o serviço.

A verificação do 503 foi feita sem simular nada no código: um segundo processo do serviço foi
iniciado apontando o cache do HuggingFace para uma pasta vazia e com o acesso ao Hub
desligado — a situação real de quem clona o repositório e roda a API sem rede. Nessa
condição, `GET /ranking`, `GET /indicadores`, `GET /noticias` e `GET /fontes` responderam 200
normalmente, as rotas de linguagem responderam 503 com o motivo nas **duas** tarefas,
`GET /modelo` respondeu 200 relatando as duas falhas em separado, e a validação de entrada
manteve precedência: texto curto recebeu 422 e tarefa inexistente recebeu 422, não 503,
porque não faz sentido reclamar da indisponibilidade de um modelo para um pedido que seria
inválido de qualquer forma.

---

## 7. Response models

Toda rota do serviço — as quatro de linguagem e as dez anteriores — declara `response_model`.
O FastAPI valida a saída contra a classe declarada antes de serializar, e o `/docs` passa a
mostrar o formato exato da resposta, não só o da requisição.

O ganho é de contrato. Se uma rota deixar de devolver uma chave prometida, o erro aparece no
servidor como falha de validação, em vez de chegar ao cliente como resposta silenciosamente
diferente da documentada. Numa aplicação cuja meta declarada é rastreabilidade de 100%, uma
resposta que muda de forma sem aviso é falha de governança, não inconveniente de integração.

Onde o conteúdo da linha varia com o filtro — as tabelas de indicadores e de notícias — o
tipo é `list[dict]`. Ali a forma do registro é a forma do CSV de origem, e congelar coluna
por coluna no modelo quebraria a rota a cada mudança de fonte de dados. O envelope em volta
(`total`, `retornados`, `filtros`, `dados`) é que está tipado, e é ele que o cliente usa para
paginar e para saber o que foi filtrado.

Os modelos das rotas de linguagem são estritos, porque ali a forma é conhecida e estável.
`RespostaTexto` merece nota própria: tem um cabeçalho comum às tarefas — `tarefa`, `modelo`,
`gerativo`, contagem de tokens, truncagem, tempo, instante e aviso — e **um bloco por tarefa**,
`ResultadoSentimento` ou `ResultadoResumo`, do qual só o da tarefa pedida aparece. O outro é
omitido, não vem nulo, graças a `response_model_exclude_none`. É a forma que o enunciado
descreve — tipo de análise realizada mais os resultados gerados — e é a que permite
acrescentar uma terceira tarefa sem quebrar quem já consome as duas.

`ResultadoResumo` carrega `Conferencia`, com a lista de `ItemConferido`. Está no modelo de
resposta, e não só na tela, porque a conferência é parte do resultado: um consumidor que
integre a rota recebe junto do texto gerado a lista do que nele não tem respaldo, e pode
decidir por conta própria — por exemplo, descartar todo resumo com `situacao: "revisar"`.

São **26 esquemas** gerados no `openapi.json`, contra os 5 que havia no TP3.

---

## 8. Verificação

Três baterias foram executadas contra o serviço em pé.

**8.1 Rotas de linguagem e tratamento de erro — 108 verificações, nenhuma falha.**
Ficha dos dois modelos antes de qualquer carga (nenhum carregado, pesos em cache, três
rótulos no classificador e nenhum no gerativo); `/saude` relatando os dois sem carregá-los;
**carga em separado**, confirmando que carregar o sentimento não carrega o resumo —
`XLMRobertaForSequenceClassification` com 278.045.955 parâmetros em 7,9 s, e
`T5ForConditionalGeneration` com 223 milhões em 1,5 s, ambos em `cpu`; os quatro casos de
rótulo das seções 2.2 e 5.1; distribuição com três rótulos, ordenada e somando 1,000; dois
casos de resumo, com compressão de 194 para 29 palavras (14,9%); o bloco da tarefa não pedida
**ausente** da resposta nas duas direções; a conferência presente em todo resumo, com a
contagem batendo com a lista, os ausentes primeiro, a `situacao` coerente com a contagem e os
tipos dentro dos três previstos; a conferência apontando a invenção num resumo que inventa e
reconhecendo "Itaú Social" como presente quando está no original; quatro casos de 422 na
validação de entrada e um na tarefa inexistente; truncagem declarada nas duas tarefas em
texto de 722 tokens; corpus de 10 matérias em 0,91 s com a soma dos rótulos fechando; filtros
por tema e por UF conferidos linha a linha; 422 para campo inválido e para limite acima do
máximo; 404 para filtro sem resultado; e, no `openapi.json`, as 14 operações com esquema de
resposta, os blocos `ResultadoSentimento`, `ResultadoResumo`, `Conferencia` e `ItemConferido`
presentes e o 503 declarado.

A conferência foi verificada também fora da API, em três casos de laboratório: os dois
resumos alucinados da seção 5.2, em que apontou tudo o que era esperado, e um resumo fiel de
controle, em que não apontou nada.

**8.2 Indisponibilidade dos modelos — 37 verificações, nenhuma falha.** Descrita na seção 6.

**8.3 Regressão do TP3 — bateria inteira reexecutada, nenhuma falha.** A bateria do TP3 foi
rodada de novo depois da entrada dos `response_model`, incluindo a verificação de paridade entre
`nucleo.calcular_indice` e `GET /ranking`: os 27 valores do índice continuam idênticos entre
o painel e a API. Nenhuma rota anterior mudou de forma — `GET /fontes` continua devolvendo
exatamente `total` e `dados`, sem campos nulos acrescentados pelo envelope das outras rotas.

Além disso, foi conferido no `openapi.json` que as 14 operações do serviço declaram esquema
de resposta para o código de sucesso, que as rotas de linguagem declaram 503 na documentação
e que os quatro grupos de rotas têm descrição própria.

---

## 9. O que fica pendente

**9.1 A narrativa do reporte ESG.** A tarefa 2.1 do `plano_llm.md`, de maior valor para o
usuário, continua fora — e a seção 5.2 explica por quê melhor do que o argumento de custo
explicaria: um modelo que inventa cifras ao resumir não pode redigir um relatório que cita
cifras. Implementá-la exige ou um modelo bem maior, com GPU ou provedor remoto, ou uma
arquitetura em que o texto seja montado por modelo a partir de valores injetados e depois
verificado valor a valor contra a tabela de origem antes de ser exibido.

A conferência da seção 5.3 é o primeiro pedaço dessa segunda arquitetura, e ficou mais perto
do que se esperava: o mecanismo que confere números e nomes de um resumo contra a matéria é o
mesmo que conferiria os valores de uma narrativa contra o ranking. O que falta ali não é mais
a verificação — é a geração, e a decisão de qual modelo a faria.

**9.2 Verificação automática do resumo contra a fonte — ~~pendente~~ feita.** Implementada em
`texto.conferir_resumo` e descrita na seção 5.3. O que **continua** pendente é a camada
semântica: a conferência atual pega termo inventado — número, data, nome próprio — e não
pega relação invertida entre duas entidades que estejam ambas no texto. Essa segunda camada
não tem solução barata sem modelo, e um modelo que confere outro tem o mesmo problema do
primeiro.

**9.3 Linha de base da classificação temática.** A seção 3.4 do `plano_llm.md` registra que
`temas_ods4` dá referência determinística para medir um classificador. A tarefa de
classificação temática por modelo — que permitiria essa comparação — não foi implementada:
exigiria um terceiro modelo, de classificação *zero-shot*, com 1,1 GB e sete passagens por
matéria. Fica pendente, com o custo já levantado.

**9.4 Avaliação quantitativa do sentimento.** O corpus não é anotado, e as seis frases de
controle são amostra pequena. Uma medição própria exigiria anotar manualmente algumas
dezenas de matérias. É trabalho de anotação, não de código, e está fora do escopo desta
entrega; o que existe hoje é o teste de controle e a verificação de que o modelo distingue
em vez de colapsar num rótulo.

**9.5 Avaliação quantitativa do resumo.** Mesma situação, com uma vantagem: a coluna `resumo`
do corpus dá referência humana de graça para as três fontes de sindicação. Medir ROUGE contra
ela seria um script curto. Não foi feito nesta entrega, e vale dizer por quê: ROUGE mede
sobreposição de palavras e **não detecta invenção** — pontuaria bem um resumo que repete o
vocabulário do original e inventa um número. A métrica que falta não é a fácil.

Há, porém, uma métrica agora disponível e que não existia antes: a **taxa de termos sem
respaldo**, que a conferência produz por resumo. Rodá-la sobre as 105 matérias daria um
número comparável entre modelos — e seria o critério que faltou na seção 3.2, onde "alucinam
igual" foi observação qualitativa. Fica como o próximo passo barato desta frente.

**9.6 Marcação do conteúdo gerado — cumprida, e agora com motivo.** A regra 4.4 do
`plano_llm.md` exige que todo resultado de modelo apareça identificado como tal, com data e
modelo usado. Está cumprida: cada resposta carrega `modelo`, `analisado_em`, `gerativo` e
`aviso`, e a tela os exibe. Quando havia só o classificador, era precaução de governança;
com o resumo, passou a ser necessidade demonstrada — a seção 5.2 mostra o texto, gramatical e
plausível, que a marcação existe para desqualificar como apuração.
