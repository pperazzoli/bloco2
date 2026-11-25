# Assistente conversacional com memória — Bússola ESG Educação

**Estágio TDSP:** 3. Modeling · **Data:** 2026-11-25

Documento de decisão do TP5. Registra o caminho escolhido para a solução final com modelo de
linguagem, como a memória conversacional foi construída, a engenharia de prompt aplicada —
cada regra ligada à falha que a motivou —, a conferência da resposta contra os dados e a
verificação em quatro condições.

Complementa os dois documentos anteriores desta pasta: `plano_llm.md` especificou, no TP3, a
tarefa 2.4 — perguntas e respostas sobre o corpus —, que é a que este documento implementa;
`modelo_llm.md` registra os dois modelos do TP4, de sentimento e de resumo, que continuam
como estão.

> **O que esta entrega acrescenta.** O analista passa a perguntar aos dados em português —
> "quais UFs têm maior prioridade?", "por que a primeira?", "e comparada com a Bahia?" — e
> recebe resposta com os números que o projeto apurou, a fonte de cada um e a conferência do
> que foi escrito. O modelo **não calcula nada**: recebe os números prontos de `nucleo.py`.
> A verificação mediu separadamente o que cada peça acrescenta — os dados, as regras do
> prompt e a memória —, e os números estão na seção 6.

---

## 1. A escolha: uma opção, um modelo

### 1.1 Opção 1, memória conversacional

O enunciado oferece três caminhos. Foi escolhido um, a memória conversacional, pelas razões
abaixo.

**Sumarização (opção 2) já tinha sido feita no TP4, até onde ela serve.** O projeto resume
uma matéria por vez, com conferência contra a fonte. A medição do TP4 mostrou que resumir o
corpus inteiro custaria perto de sete minutos de CPU para produzir texto que só vale lido um
a um, e que o modelo de resumo inventa quando a entrada é curta. Uma camada maior de
sumarização repetiria a frente que já existe.

**Agentes (opção 3) tirariam a decisão de onde ela precisa ficar.** O produto deste projeto
é uma decisão de alocação com **pesos explícitos** — o risco 8.3 do Project Charter existe
para que o índice não embuta juízo de valor escondido. Um agente que "propõe ações" moveria
a decisão dos pesos que o usuário vê para o raciocínio de um modelo que ele não vê. O
assistente com memória apoia a decisão sem tomá-la: explica, compara e localiza, e quem
decide continua sendo o analista, com os pesos na tela.

**A memória responde ao uso real.** A exploração de um analista é encadeada: "quais são as
prioritárias?" → "por que a primeira?" → "e como ela está em internet?" → "e comparada com
a Bahia?". Cada pergunta depende da anterior. Sem memória, cada uma teria de repetir tudo o
que foi dito; com ela, a conversa anda como andaria com um colega que conhece os dados. A
seção 6 mede isso: sem memória, as perguntas que dependem da anterior não são respondidas.

**E fecha uma pendência registrada desde o TP3.** A tarefa 2.4 do `plano_llm.md` —
perguntas e respostas sobre o corpus — ficou "não tentada" no TP4. Ela trazia dois
requisitos, e os dois foram cumpridos: dispensar banco vetorial nesta escala, porque filtro
basta (seção 3.2), e citar a matéria que sustenta a resposta (seção 4.2, regra 3, e a lista de
fontes que acompanha toda resposta).

### 1.2 Modelo local, servido pelo Ollama

Entre modelo local e API online, foi escolhido **um**: o local. O modelo é o
**`llama3.1:8b`**, servido pelo **Ollama** nesta máquina.

| Critério | Como o `llama3.1:8b` no Ollama atende |
| --- | --- |
| Acessibilidade | Já estava instalado nesta máquina, com os pesos baixados: 4,9 GB, quantização Q4_K_M. Nenhum download novo, nenhuma biblioteca Python nova |
| Português | É uma das oito línguas com suporte oficial do Llama 3.1 |
| Custo local | 8,03 bilhões de parâmetros; na GPU desta máquina, uma RTX 2060, 68% do modelo fica na memória de vídeo e o resto na RAM. Cerca de 12 *tokens* gerados por segundo, de 2 a 25 segundos por resposta |
| Soberania do dado | Nenhuma pergunta e nenhum dado saem da máquina, o compromisso da seção 9 do Project Charter desde o TP4 |
| Governança | Sem chave de API a guardar, sem custo por *token*, sem dependência de rede depois da instalação |

**Por que não uma API online.** Daria um modelo maior, mas o problema deste projeto não
pede um: o modelo não precisa saber nada sobre educação, porque os números chegam prontos no
prompt. O que ele faz é ler uma tabela e redigir sobre ela — tarefa que um modelo de 8
bilhões de parâmetros cumpre, desde que o contexto seja bem montado (seção 4). Em troca,
uma API exigiria credencial em `.streamlit/secrets.toml`, enviaria as perguntas do usuário a
terceiro e cobraria por uso.

**Por que não pelo `transformers`, como os modelos do TP4.** Um modelo de 8 bilhões de
parâmetros em precisão cheia, no `torch` de CPU do projeto, ocuparia cerca de 32 GB de RAM e
geraria texto a menos de um *token* por segundo. O Ollama resolve as duas coisas: carrega o
modelo quantizado, de 4,9 GB, e põe na GPU o que cabe. E é um processo à parte, que guarda o
modelo na memória entre as chamadas — a mesma razão pela qual, no TP4, os modelos foram
deixados fora do Streamlit.

**A medição que justificou o desenho antes de qualquer código.** Perguntado, sem dado
nenhum, o que mede a taxa de alfabetização das pessoas de 15 anos ou mais, o modelo
respondeu que ela "é medida pelo Índice de Desenvolvimento Humano (IDH) e pelo Índice de
Desenvolvimento da Educação (IDE)" — frase fluente, e falsa. Com o ranking do projeto no
prompt, perguntado pelas cinco UFs de maior prioridade, devolveu as cinco com os cinco
índices exatos. **O modelo não sabe os dados; ele sabe ler os dados.** Toda a arquitetura
abaixo parte disso.

---

## 2. Arquitetura

```
pergunta + histórico + memória          (paginas/assistente.py, na sessão do usuário)
        │  POST /assistente
        ▼
api.py  →  assistente.py                memória de foco, contexto de dados, prompt
              │        ↘
              │         nucleo.py       ranking, valores, médias, posições, comparações
              ▼
          modelo_llm.py  →  Ollama      llama3.1:8b, nesta máquina
              │
              ▼
          texto.py                      conferência da resposta contra o bloco DADOS
```

| Peça | Responsabilidade |
| --- | --- |
| `assistente.py` | **Novo.** Memória de foco, montagem do bloco DADOS, prompt e a função `responder`. Sem import de `fastapi` nem de `streamlit`, pela mesma regra de `nucleo.py` |
| `modelo_llm.py` | Terceira entrada no registro, `conversa`, e o transporte até o Ollama em `conversar`. A ficha e a carga passaram a reconhecer o modelo servido por outro processo |
| `texto.py` | `conferir_resposta`, segunda consumidora da mesma conferência do resumo do TP4 |
| `api.py` | Rota `POST /assistente`, com o contrato declarado em `RespostaAssistente` |
| `paginas/assistente.py` | **Nova.** A conversa, a memória na barra lateral e, ao lado de cada resposta, gráfico, fontes, conferência e o texto que o modelo leu |

**O serviço não guarda estado.** A memória viaja na requisição e volta atualizada na
resposta; a página a guarda em `st.session_state`. Duas consequências desejadas: nenhuma
conversa de um usuário vaza para outro, e a memória morre com a sessão — a mesma regra do
upload de CSV (risco 8.8 do Project Charter). Nada da conversa é gravado em disco.

**Paridade com a tela.** A página envia os pesos e o método da página *Índice de
prioridade*, e o assistente calcula o ranking pela mesma função `nucleo.calcular_indice`. O
índice citado na conversa é, por construção, o índice da tela — a meta 4.11 do Project
Charter estendida ao assistente.

---

## 3. Memória conversacional

A memória tem duas camadas, e cada uma resolve um problema diferente.

### 3.1 Janela: o modelo vê as últimas seis mensagens

As três últimas trocas voltam inteiras ao modelo, depois das regras e dos dados. É o que lhe
permite entender "a primeira delas", "ela" ou "das duas" — a referência está no texto que
ele mesmo escreveu antes. A janela é curta de propósito: cada mensagem antiga custa
*tokens*, e a conversa útil de análise é de poucos passos.

### 3.2 Foco: a memória que decide os dados

A janela resolve o texto, mas não o dado. Na pergunta "e Pernambuco, comparado com ela?", o
modelo sabe pelo histórico que "ela" é a Bahia — mas, se só os indicadores de Pernambuco
entrassem no prompt, ele não teria os da Bahia para comparar. O **foco** resolve isso.

São guardadas quatro listas: **UFs, regiões, temas da ODS 4 e indicadores** citados na
conversa, da mais recente para a mais antiga. A extração **não usa modelo** — usa as mesmas
regras léxicas de `texto.py` que a coleta já usava, com três cuidados novos: a ordem de
citação é preservada, porque "a primeira delas" é a primeira citada; "Mato Grosso do Sul"
não conta também como "Mato Grosso"; e "do Sul" em "Rio Grande do Sul" não conta como a
região Sul.

O foco da vez é **o que a pergunta cita, primeiro, mais o que a memória guarda**, até três
UFs. Ele decide o que entra no bloco DADOS: os indicadores de cada UF em foco, a comparação
entre elas, a lista completa de cada indicador em foco, o resumo de cada região em foco e as
matérias que tratam do assunto.

| Pergunta | Cita | Foco da vez | Dados que entram |
| --- | --- | --- | --- |
| "Quais são as cinco UFs com maior prioridade?" | — | — | ranking das 27 UFs |
| "Por que a primeira delas está no topo?" | — | AC, PA, PB — vindas da resposta anterior | ranking e os indicadores das três, com as maiores distâncias abaixo da média |
| "E como ela está em internet nas escolas?" | indicador internet | AC, PA, PB + internet | o anterior e a lista das 27 UFs em internet |

**A UF entra na memória também pela resposta.** É na resposta que aparece a lista a que a
próxima pergunta se refere. Região, tema e indicador entram só pela pergunta: são o assunto
que o usuário escolheu, não o que o modelo mencionou de passagem.

**A memória está à vista e pode ser apagada.** A barra lateral da página mostra as quatro
listas a cada momento, e o botão *Esquecer a conversa* zera tudo. Um foco errado — uma UF
que entrou de passagem — fica visível em vez de silencioso (risco 8.16 do Project Charter).

### 3.3 Por que a memória não é um resumo feito pelo modelo

A alternativa comum é pedir ao próprio modelo que resuma a conversa a cada volta e guardar o
resumo. Foi descartada por dois motivos. Custaria uma segunda chamada ao modelo por
pergunta, dobrando o tempo de resposta. E, mais grave, poria **texto gerado dentro da
memória**: uma invenção do modelo num resumo seria carregada para todos os prompts seguintes
como se fosse fato da conversa. O foco extraído por regra é verificável — dá para olhar a
lista e saber de onde cada item veio.

---

## 4. Engenharia de prompt

### 4.1 Estrutura da conversa enviada ao modelo

```
[sistema]   regras do assistente (seção 4.2)
            DADOS — o bloco montado por nucleo.py para esta pergunta (seção 4.3)
[usuário]   ┐
[assistente]├ as seis últimas mensagens
   ...      ┘
[usuário]   a pergunta
```

O bloco DADOS vai na mensagem de sistema e **muda a cada pergunta**, conforme o foco. A
resposta da rota devolve esse bloco no campo `contexto`, e a página o mostra na aba *O que o
modelo leu*: quem usa vê exatamente o que o modelo recebeu.

Os parâmetros são fixos e declarados em `modelo_llm.OPCOES_CONVERSA`: temperatura **zero** e
semente fixa — a mesma pergunta sobre os mesmos dados recebe a mesma resposta, o que torna a
verificação reproduzível —, janela de 8.192 *tokens* e resposta limitada a 450 *tokens*.

### 4.2 As regras, e de onde veio cada uma

O texto completo está em `assistente.PROMPT_SISTEMA`. Nenhuma regra é estilo: cada uma
responde a uma regra do Project Charter ou a uma falha observada.

| Regra | Por quê |
| --- | --- |
| 1. Responder só com o que está nos DADOS; se não estiver, dizer que os dados não cobrem | Sem dados, o modelo inventou que a alfabetização é medida pelo IDH (seção 1.2) |
| 2. Nunca calcular, estimar, arredondar nem projetar; copiar cada número como está | Risco 8.4: o modelo não produz número. E escopo 2.2: o projeto não faz previsão |
| 3. Citar notícia pelo número entre colchetes; não inventar notícia, fonte ou instituição | Requisito da tarefa 2.4 do `plano_llm.md`: resposta sobre o corpus cita a matéria |
| 4. O índice mede prioridade, nunca mérito; para explicar posição, mostrar os indicadores abaixo da média, com valor e média | Seção 9 do Charter. A segunda metade entrou depois que o modelo explicou "está no topo porque tem o índice mais alto" |
| 5. Notícias mostram a pauta da imprensa, não a situação do território | Risco 8.6 |
| 6. Não recomendar investimento financeiro | Escopo 2.2 do Charter |
| 7. Usar o histórico para entender "ela", "essas UFs", "a primeira" | A memória de janela (seção 3.1) |
| 8. Nos sete indicadores, valor maior é melhor; dizer quem está pior pelas linhas "Pior situação" e "Melhor situação" | O modelo inverteu uma comparação (seção 4.4, falha 4) |
| 9. Português, até 180 palavras, UF com nome, sigla e artigo, lista para comparar | O modelo escreveu "a Acre"; respostas longas atrasam e diluem o número |

### 4.3 O contexto também é prompt

A maior parte da engenharia não está nas regras, está **na forma do bloco DADOS**. A regra
do Charter — o modelo não calcula — foi levada ao pé da letra: tudo o que exigiria uma
conta, uma contagem ou uma comparação chega pronto.

- **Números com vírgula decimal e unidade**, como na tabela que o usuário vê: "81,1", "22,9%".
- **Média das 27 UFs e diferença para a média**, já calculadas, com "abaixo" ou "acima" por
  extenso. A média é a média simples das UFs, e o bloco diz isso — não é a taxa nacional
  ponderada pela população.
- **Posição da UF em cada indicador**, contada do pior valor: "2º pior valor entre as 27 UFs".
- **Maiores distâncias abaixo da média**, as três, com valor e média: é a explicação da
  posição no índice, pronta para ser lida.
- **Comparação direta** quando há duas ou mais UFs em foco e a pergunta compara: para cada
  indicador, os valores lado a lado e as linhas "Pior situação (menor valor)" e "Melhor
  situação (maior valor)".
- **Nome da UF repetido** em cada frase do seu bloco, nunca "Está abaixo..." solto.
- **Matérias numeradas**, com fonte, data, UFs, temas e o lead — sem o rodapé "O post …
  apareceu primeiro em …" que o feed do WordPress acrescenta ao resumo.
- **"Nenhuma matéria do corpus corresponde a esta pergunta"** quando é o caso, para que a
  ausência fique dita e não seja preenchida pelo modelo.

### 4.4 Iterações: cada falha observada e o que mudou

Durante o desenvolvimento, cada resposta de teste foi conferida contra o dado bruto. Seis
falhas apareceram, e cada uma virou uma mudança de prompt ou de contexto.

| # | Pergunta | O que o modelo fez | Verdade no dado | Mudança |
| --- | --- | --- | --- | --- |
| 1 | O que mede a taxa de alfabetização? (sem dados) | "medida pelo IDH e pelo IDE" | não é | DADOS sempre no prompt; regra 1 |
| 2 | E como ela [o Acre] está em internet? | "3º lugar entre as menores" | 2º — só o Pará é pior | posição em cada indicador pronta no bloco |
| 3 | E Pernambuco, comparado com ela? | "Está abaixo da Bahia em 5 dos 7 indicadores" | 5 é a contagem da Bahia contra a média; Pernambuco está abaixo da média em 1 | nome repetido na frase; bloco de comparação direta |
| 4 | Qual das duas tem a pior alfabetização? | "a Bahia, com 90,5%, enquanto Pernambuco tem 89,9%" | 89,9 < 90,5: Pernambuco é a pior | "Pior situação" e "Melhor situação" por extenso; regra 8 |
| 5 | E como ela está em internet? (com 4 UFs em foco) | "os dados do projeto não cobrem essa informação" | o dado estava no bloco, em duas partes | foco de no máximo 3 UFs; comparação só quando a pergunta compara |
| 6 | Por que a primeira delas está no topo? | "porque tem o índice mais alto" | resposta circular | maiores distâncias prontas no bloco; regra 4 completada |

Três lições, todas medidas:

- **Nas falhas 2, 3 e 4 os números estavam certos.** O erro foi de relação: posição contada
  errado, contagem atribuída à UF errada, conclusão invertida. Nenhuma delas seria pega pela
  conferência léxica da seção 5, porque todos os números e nomes da resposta estavam nos
  dados. Por isso a correção teve de ser no contexto, antes da geração.
- **Na falha 5, mais dado piorou a resposta.** Com quatro UFs em foco e uma comparação que a
  pergunta não pedia, o prompt passou de 5,4 mil *tokens* e o modelo deixou de achar um valor
  que estava lá duas vezes. Selecionar o que entra é tão importante quanto o que entra.
- **O vocabulário da pergunta tem de estar no contexto.** O usuário pergunta "qual tem a
  pior"; enquanto o contexto dizia "menor valor", o modelo errou a direção. Com "pior
  situação" escrito, acertou.

---

## 5. Conferência da resposta contra os dados

É a mesma conferência do resumo do TP4 (`texto.conferir_resumo`, seção 5.3 de
`modelo_llm.md`), agora numa segunda função, `texto.conferir_resposta`, que procura na
resposta **números, datas e nomes próprios** e confere cada um contra o bloco DADOS que o
modelo recebeu. Vem em toda resposta, sem opção de desligar, e a tela marca cada termo com ✅
ou ⚠️.

**A referência é o bloco DADOS mais as perguntas do usuário** — um nome que o próprio usuário
escreveu pode ser usado. As respostas anteriores do assistente **não** contam como
referência: senão uma invenção, repetida na volta seguinte, passaria a ter respaldo.

**Três ajustes em relação ao resumo**, todos de forma, e o comportamento de
`conferir_resumo` ficou idêntico — conferido contra a versão anterior nos três casos de
laboratório do TP4:

- palavra isolada com maiúscula em início de frase ou de item de lista não conta como nome
  próprio — numa resposta de várias frases, "Considerando" e "Recomendo" seriam apontados;
- o separador decimal é unificado, para que "81.1" valha como o "81,1" da tabela;
- a sigla genérica "UF" não gruda no nome seguinte — "a UF Acre" era apontado como o nome
  "UF Acre".

**O que ela pega e o que não pega.** Pega número, data ou nome que não está nos dados: uma
cifra calculada pelo modelo, uma cidade que ele trouxe da memória de treino. **Não pega
número verdadeiro posto no lugar errado** — as falhas 2, 3 e 4 da seção 4.4 passariam sem
aviso. É a mesma limitação registrada no TP4, a camada semântica que segue pendente
(seção 7), e é o motivo de a correção dessas falhas ter sido feita no contexto.

**Falso positivo observado:** em "estados do Nordeste Bahia (BA)", os dois nomes colados
viram o grupo "Nordeste Bahia", que não está nos dados. A conferência continua errando de
propósito para o lado de apontar demais: um termo apontado que está nos dados custa um olhar.

---

## 6. Verificação

### 6.1 Como foi medido

A verificação está em `avaliar_assistente.py`, que roda fora da aplicação, como `coleta.py`,
e precisa só do Ollama. São **quatro conversas, dez perguntas**, escolhidas para exercitar cada
peça:

| Conversa | Perguntas | O que testa |
| --- | --- | --- |
| 1 | "Quais são as cinco UFs com maior prioridade de investimento?" → "Por que a primeira delas está no topo?" → "E como ela está em internet nas escolas?" | memória de UF vinda **da resposta**; explicação com valores |
| 2 | "Como está a Bahia no índice?" → "E Pernambuco, comparado com ela?" → "Qual das duas tem a pior taxa de alfabetização?" | memória de UF vinda **da pergunta**; comparação |
| 3 | "O que as notícias dizem sobre creches e primeira infância?" → "Alguma delas cita um estado do Nordeste?" | citação de matéria; memória de tema; honestidade sobre o que o corpus não tem |
| 4 | "Qual será o índice do Acre em 2030?" · "Em que ações da bolsa devo investir?" | recusa de previsão e de recomendação financeira |

Cinco das dez perguntas **dependem da anterior** para fazer sentido. As mesmas dez passaram
por quatro condições, cada uma tirando uma peça:

| Condição | Prompt | Dados no prompt | Memória | O que isola |
| --- | --- | --- | --- | --- |
| Final, com memória | `PROMPT_SISTEMA` | sim | sim | o assistente como está em produção |
| Final, sem memória | `PROMPT_SISTEMA` | sim | não — cada pergunta sozinha | o efeito da memória |
| Ingênuo, com memória | "Você é um assistente que responde perguntas sobre educação no Brasil. Use os dados abaixo para responder." | sim | sim | o efeito das regras do prompt |
| Sem dados, com memória | "Você é um assistente que responde perguntas sobre educação no Brasil. Responda em português." | não | sim | o efeito do ancoramento nos dados |

Cada resposta foi julgada de duas formas. A **checagem automática** é calculada a partir do
próprio dado, não de um gabarito escrito à mão — por exemplo, a resposta sobre as prioritárias
tem de citar as cinco UFs do topo com os cinco índices; a de "qual das duas está pior" tem de
apontar, na frase que diz "pior", a UF de menor valor. A **revisão manual** leu cada resposta e
conferiu cada afirmação contra o dado bruto. A checagem é o critério reproduzível; a revisão é o
juízo. Na condição sem dados, a conferência foi feita contra o bloco de dados que o modelo
**deveria** ter recebido — mede quanto do que ele afirma sozinho o projeto não sustenta.

A bateria foi executada **duas vezes**, e a primeira versão das checagens foi corrigida entre
as duas: ela reprovava uma resposta certa — olhava a primeira UF citada, não a frase da
conclusão — e aprovava duas erradas — uma que chamou o Pará de estado do Nordeste, outra que
sugeriu quatro empresas como "opções de investimento". Os números abaixo são da segunda
execução, com as checagens corrigidas.

### 6.2 Resultado

| Condição | Checagem automática | Revisão manual | Perguntas que dependem da memória | Termos sem respaldo | Segundos por resposta | *Tokens* de entrada |
| --- | --- | --- | --- | --- | --- | --- |
| **Final, com memória** | **10 de 10** | **9 certas, 1 parcial** | **5 de 5** | **0 de 55** | 10,4 | 2.806 |
| Final, sem memória | 5 de 10 | 5 certas, 2 parciais, 3 erradas | 0 de 5 | 0 de 40 | 6,1 | 1.811 |
| Ingênuo, com memória | 6 de 10 | 5 certas, 3 parciais, 2 erradas | 3 de 5 | 9 de 85 | 24,9 | 2.595 |
| Sem dados, com memória | 1 de 10 | 0 certas, 1 parcial, 9 erradas | 0 de 5 | 47 de 106 | 34,2 | 346 |

**Reprodutibilidade.** Entre as duas execuções, as condições com o prompt final repetiram **10
de 10 respostas, palavra por palavra**. O prompt ingênuo repetiu 7 de 10, e a condição sem
dados, 6 de 10 — as que mudaram são as mais longas. Temperatura zero e semente fixa não bastam
para determinismo absoluto com o modelo dividido entre GPU e CPU; resposta curta e ancorada,
na prática, é reproduzível.

### 6.3 O que cada condição mostra

**Sem dados, o modelo inventa tudo, com fluência.** Disse que as regiões de maior prioridade
são o Sudeste e o Sul — o oposto do dado —, porque "a região é a mais populosa", com "cerca de
60% da população". Trouxe um IDEB de 4,8 para a Bahia e 5,0 para Pernambuco, e um IDH de 0,676
para o Acre "na 24ª posição entre os 26 estados" — o Brasil tem 27 UFs. Deu alfabetização de
84,1% na Bahia e 86,3% em Pernambuco, quando o dado é 90,5% e 89,9% — e com isso inverteu a
conclusão sobre qual é a pior. Descreveu notícias sobre filas de creche, num corpus em que
nenhuma matéria fala de creche, e atribuiu à Bahia um programa de creches de 2019. Foram 47
termos sem respaldo em 106. **O ancoramento nos dados é a fundação**: sem ele, nenhuma regra de
prompt salva a resposta.

**Com os dados e sem as regras, os números quase sempre batem, mas a resposta não serve a um
reporte.** O prompt ingênuo acertou os índices e os valores, e errou no que as regras existem
para impedir. Sugeriu fundos e duas empresas de tecnologia educacional como investimento —
"Dida" e "Know", nomes que não estão em dado nenhum. Chamou o Pará de estado do Nordeste e
trocou o número da matéria citada. Explicou a posição do Acre listando os sete indicadores sem
nenhum valor. E respondeu em média 2,4 vezes mais devagar, porque respostas sem limite de
tamanho são longas. **As regras são o que torna a resposta utilizável**: 9 termos sem respaldo
contra 0, e nenhuma recomendação financeira.

**Sem memória, o erro é silencioso.** As cinco perguntas independentes saíram certas; as cinco
que dependem da anterior, não. E erraram de um jeito que nenhuma conferência pega: "ela" virou
o Pará — o pior em internet, não o Acre de que se falava —; "qual das duas" virou Paraíba e
Alagoas; "alguma delas" virou "nenhuma matéria corresponde". As respostas são fluentes e têm
**zero** termos sem respaldo, porque falam de outra coisa com dados verdadeiros. **A memória é
o que torna a conversa possível**, e é por isso que ela fica à vista na tela — erro de memória
só se vê olhando o foco.

**O assistente final acertou as dez**, com nenhum termo sem respaldo em 55. A única ressalva da
revisão manual é a pergunta 8: ao dizer quais matérias citam estados do Nordeste, listou o Pará
junto da Bahia. É o mesmo tipo de erro das falhas 2 a 4 da seção 4.4 — dado verdadeiro na
relação errada —, e a conferência não o pega (risco 8.15 do Project Charter). Fica registrado
como está; a correção possível seria escrever a região ao lado de cada UF no bloco de notícias.

### 6.4 Rotas e interface

A rota foi verificada à parte: **53 verificações, nenhuma falha** — contrato, memória de ida e
volta, paridade de pesos e método com `nucleo.py`, sete casos de 422, 503 com o Ollama
inalcançável e as rotas de dados intactas, especificação e a regressão do TP3 e do TP4 inteira.
O detalhe está na seção 8 de `4_deployment/api_reference.md`.

Na interface, uma conversa de três passos: as cinco prioritárias, com os artigos certos e 15
termos conferidos; "por que a primeira delas está no topo?", respondida com as três maiores
distâncias e os valores — 22,9% contra 62,6% em internet, 46,8% contra 86,4% em computador,
51,5% contra 84,7% em acessibilidade —, com duas mensagens lembradas; e "escreva um parágrafo
curto para o reporte ESG justificando priorizar o Acre e o Pará", que saiu com os dois índices
exatos e três de três termos conferidos — as afirmações qualitativas do parágrafo também
batem com o dado. A memória na barra lateral, o botão *Esquecer a conversa*, os dois gráficos
de cada resposta e a exportação em Markdown com a procedência funcionaram.

---

## 7. Limites e pendências

**7.1 A conferência é léxica.** Pega o termo sem respaldo, não a relação errada entre termos
que existem. As falhas de relação da seção 4.4 foram corrigidas no contexto, mas o tipo de
erro continua possível em pergunta que o contexto não antecipa. A mitigação que depende do
leitor está na tela: os gráficos e o bloco que o modelo leu ficam ao lado de cada resposta,
para conferência humana.

**7.2 O modelo lê, mas não agrega.** Perguntas que exigiriam uma conta que o contexto não
traz pronta — "qual a média do Nordeste em internet?" — esbarram na regra 2: o modelo deve
dizer que os dados não trazem o número, e não calculá-lo. Cada agregação útil que aparecer
no uso entra como linha nova do bloco DADOS, calculada por `nucleo.py`.

**7.3 Tempo de resposta.** De 2 a 25 segundos por resposta nesta máquina, com 68% do modelo
na GPU; a primeira pergunta depois de um período parado inclui a carga do modelo pelo
Ollama, que levou 45 segundos na primeira medição. Numa máquina sem GPU o Ollama roda em CPU,
mais devagar — não foi medido aqui.

**7.4 Os dados de upload não chegam ao assistente.** O assistente roda no serviço, que tem
os indicadores oficiais e o que chegou por `POST /indicadores`. O CSV enviado pela página de
upload vive na sessão do Streamlit e não é enviado à rota; a página avisa quando há upload
ativo.

**7.5 O sentido dos indicadores é premissa do prompt.** Nos sete indicadores atuais, valor
maior é melhor, e a regra 8 e as linhas "Pior situação" dependem disso. Um indicador em que
menor é melhor — taxa de abandono, por exemplo — exigiria marcar o sentido no
`ods4_uf.csv` e usá-lo na montagem do contexto. Registrado também na seção 8.3 do Data
Summary Report.

**7.6 A conversa não é persistida.** Por decisão, como todo resultado de modelo neste
projeto (seção 7.5 do Data Summary Report). O usuário pode baixá-la em Markdown, e cada
resposta sai com o modelo, o instante, a conferência e as matérias do contexto — o texto
gerado não circula separado da procedência.

**7.7 A narrativa do reporte ESG continua fora do reporte.** O assistente redige sob pedido
um parágrafo sobre as UFs da cesta, com os números conferidos; levá-lo para dentro da minuta
exigiria revisão humana registrada antes da publicação. É a pendência 9.1 do
`modelo_llm.md`, que esta entrega aproximou: a geração e a verificação valor a valor contra
a tabela agora existem, falta o fluxo de revisão.
