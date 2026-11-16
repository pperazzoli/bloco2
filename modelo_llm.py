# modelo_llm.py - carga e uso dos modelos de linguagem que rodam na propria maquina
# criado 16-11-2026 (TP4)
# edited 16-11-2026 (TP4): passou de um modelo para dois. A entrada da tarefa de resumo, que
# e gerativa, exigiu generalizar o que antes era um estado unico num registro por tarefa:
# cada modelo carrega sozinho, falha sozinho e e relatado sozinho.
#
# Por que este arquivo existe, pela mesma razao de nucleo.py: um modelo e recurso caro de
# carregar - centenas de megabytes lidos do disco para a memoria - e so pode ser carregado
# uma vez por processo. A carga, o cache em memoria e a traducao de falha em erro nomeado
# ficam aqui. Nao ha import de fastapi nem de streamlit neste arquivo, de proposito: os
# modelos sao do projeto, nao do servico HTTP; api.py apenas os consome.
#
# Nada aqui chama servico externo. Os pesos sao baixados uma vez do HuggingFace Hub para o
# cache local do usuario e dali em diante a carga e offline. A escolha de cada modelo e os
# criterios que levaram a ela estao em 3_modeling/modelo_llm.md.

import os
import time
from datetime import datetime
from pathlib import Path

import texto as tx

# ---------------------------------------------------------------- registro das tarefas

# Uma entrada por tarefa. 'gerativo' nao e rotulo decorativo: separa o modelo que escolhe
# entre rotulos fixos daquele que produz texto novo, e e essa distincao que decide quais
# regras de contencao do risco 8.4 do Project Charter se aplicam a cada um.
MODELOS = {
    "sentimento": {
        "modelo": "cardiffnlp/twitter-xlm-roberta-base-sentiment",
        "tarefa_hf": "sentiment-analysis",
        "descricao": "classificação de sentimento",
        "limite_tokens": 512,
        "gerativo": False,
        "rotulos": ["negativo", "neutro", "positivo"],
    },
    "resumo": {
        "modelo": "recogna-nlp/ptt5-base-summ-xlsum",
        "tarefa_hf": "summarization",
        "descricao": "resumo abstrativo",
        "limite_tokens": 512,
        "gerativo": True,
        "rotulos": [],
    },
}

TAREFAS = list(MODELOS)

# o modelo de sentimento rotula em ingles; a aplicacao e em portugues. as chaves LABEL_n
# cobrem o caso de o repositorio vir sem id2label nomeado, quando o pipeline devolve o indice.
ROTULOS = {
    "positive": "positivo", "negative": "negativo", "neutral": "neutro",
    "LABEL_0": "negativo", "LABEL_1": "neutro", "LABEL_2": "positivo",
}

# parametros de geracao do resumo, fixos e declarados. num_beams e a busca em feixe que o
# modelo recomenda; no_repeat_ngram_size evita a repeticao de trecho que modelos pequenos
# produzem quando a entrada e curta. Sao fixos de proposito: resumo que muda de forma a cada
# chamada nao serve a um reporte, e deixar o usuario mexer nisso so acrescentaria variacao
# sem acrescentar controle.
GERACAO = {"max_new_tokens": 90, "min_new_tokens": 20, "num_beams": 4, "no_repeat_ngram_size": 2}

AVISOS = {
    "sentimento": (
        "Classificação automática por modelo de linguagem, não revisada por pessoa. Mede o "
        "tom do texto, não a situação do território: não entra, em nenhuma hipótese, no "
        "cálculo do Índice de Prioridade de Investimento."
    ),
    "resumo": (
        "Texto gerado por modelo de linguagem, não revisado por pessoa. Resumo abstrativo "
        "reescreve em vez de recortar, e pode afirmar o que não está no original — inclusive "
        "números. Toda resposta traz a conferência automática dos números, datas e nomes "
        "próprios do resumo contra o texto de origem; o que ela aponta como ausente não está "
        "no original. Nenhum valor usado pelo projeto vem daqui: os indicadores e o índice "
        "são apurados por `nucleo.py` a partir dos dados oficiais."
    ),
}


class ModeloIndisponivel(RuntimeError):
    """Um modelo nao pode ser carregado. api.py traduz esta excecao em HTTP 503."""


class ErroDeInferencia(RuntimeError):
    """O modelo carregou mas falhou ao processar o texto. api.py traduz em HTTP 500."""


class TarefaDesconhecida(ValueError):
    """Tarefa que nao esta no registro. api.py traduz em HTTP 422."""


class MotorGerativo:
    """Tokenizador e modelo seq2seq carregados sem o atalho do pipeline.

    Por que nao ha pipeline aqui: o transformers 5 **removeu** a tarefa `summarization` do
    `pipeline`, que agora so aceita `text-generation` com modelo de chat. O modelo seq2seq
    continua suportado pela biblioteca - o que saiu foi o atalho. Carregar tokenizador e
    modelo e chamar `generate` e o caminho que restou, e tem a vantagem de deixar os
    parametros de geracao a vista, em GERACAO, em vez de escondidos num padrao de pipeline.

    Expoe `tokenizer`, `model` e `device` com os mesmos nomes do pipeline, de modo que a
    ficha do modelo nao precise saber de que tipo e o motor que esta relatando.
    """

    def __init__(self, tokenizador, modelo):
        self.tokenizer = tokenizador
        self.model = modelo

    @property
    def device(self):
        return self.model.device

    def gerar(self, textos, limite, **parametros):
        import torch

        entradas = self.tokenizer(
            textos, return_tensors="pt", padding=True, truncation=True, max_length=limite,
        )
        with torch.no_grad():       # sem gradiente: e inferencia, nao treino
            saidas = self.model.generate(**entradas, **parametros)
        return [self.tokenizer.decode(s, skip_special_tokens=True).strip() for s in saidas]


# estado da carga, por tarefa e por processo. 'motor' e o pipeline do transformers; 'erro'
# guarda a falha para que uma carga impossivel nao seja tentada de novo a cada requisicao.
_ESTADO = {
    tarefa: {"motor": None, "erro": None, "carregado_em": None, "segundos_de_carga": None}
    for tarefa in MODELOS
}


# ---------------------------------------------------------------- ambiente local

def versoes():
    # le a versao dos metadados do pacote, sem importar torch, que e import caro
    from importlib.metadata import PackageNotFoundError, version

    saida = {}
    for nome in ("transformers", "torch", "sentencepiece"):
        try:
            saida[nome] = version(nome)
        except PackageNotFoundError:
            saida[nome] = None
    return saida


def pasta_do_cache():
    # onde o HuggingFace guarda os pesos baixados nesta maquina. HUGGINGFACE_HUB_CACHE
    # aponta direto para a pasta dos modelos; HF_HOME aponta um nivel acima dela.
    if os.environ.get("HUGGINGFACE_HUB_CACHE"):
        return str(Path(os.environ["HUGGINGFACE_HUB_CACHE"]))
    if os.environ.get("HF_HOME"):
        return str(Path(os.environ["HF_HOME"]) / "hub")
    return str(Path.home() / ".cache" / "huggingface" / "hub")


def ja_baixado(tarefa):
    # se a pasta existe, a proxima carga daquele modelo nao precisa de rede
    nome = MODELOS[tarefa]["modelo"]
    return (Path(pasta_do_cache()) / f"models--{nome.replace('/', '--')}").exists()


def conferir_tarefa(tarefa):
    if tarefa not in MODELOS:
        raise TarefaDesconhecida(f"tarefa deve ser uma de {TAREFAS}")
    return tarefa


# ---------------------------------------------------------------- carga

def carregar(tarefa, forcar=False):
    """Devolve o pipeline da tarefa, carregando-o na primeira chamada.

    Levanta ModeloIndisponivel quando a biblioteca falta ou os pesos nao podem ser obtidos.
    Com forcar=True, tenta de novo mesmo depois de uma falha anterior.
    """
    conferir_tarefa(tarefa)
    config = MODELOS[tarefa]
    estado = _ESTADO[tarefa]

    if forcar:
        estado.update({"motor": None, "erro": None})
    if estado["motor"] is not None:
        return estado["motor"]
    if estado["erro"] is not None:
        # falha ja conhecida: repetir a tentativa a cada requisicao tornaria toda chamada
        # lenta sem mudar o resultado. POST /modelo/carregar e o caminho da nova tentativa.
        raise ModeloIndisponivel(estado["erro"])

    inicio = time.perf_counter()

    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline
    except ImportError as erro:
        estado["erro"] = (
            f"a biblioteca transformers não está instalada ({erro}). Instale as dependências "
            "do projeto com `pip install -r requirements.txt`."
        )
        raise ModeloIndisponivel(estado["erro"]) from erro

    try:
        if config["gerativo"]:
            tokenizador = AutoTokenizer.from_pretrained(config["modelo"])
            seq2seq = AutoModelForSeq2SeqLM.from_pretrained(config["modelo"])
            seq2seq.eval()
            motor = MotorGerativo(tokenizador, seq2seq)
        else:
            motor = pipeline(
                config["tarefa_hf"],
                model=config["modelo"],
                top_k=None,                   # pontuacao de todos os rotulos, nao so a maior
                truncation=True,              # texto acima do limite e cortado, nao estoura
                max_length=config["limite_tokens"],
            )
    except Exception as erro:
        estado["erro"] = (
            f"falha ao carregar {config['modelo']} — {type(erro).__name__}: {erro}. Na primeira "
            "execução os pesos são baixados do HuggingFace Hub e isso exige rede; depois disso "
            f"ficam no cache local em `{pasta_do_cache()}` e a carga passa a ser offline."
        )
        raise ModeloIndisponivel(estado["erro"]) from erro

    estado.update({
        "motor": motor,
        "erro": None,
        "carregado_em": datetime.now().isoformat(timespec="seconds"),
        "segundos_de_carga": round(time.perf_counter() - inicio, 2),
    })
    return motor


def ficha(tarefa):
    """Ficha de um modelo e situacao da carga. Nao carrega o modelo, apenas relata."""
    conferir_tarefa(tarefa)
    config = MODELOS[tarefa]
    estado = _ESTADO[tarefa]
    motor = estado["motor"]
    return {
        "tarefa": tarefa,
        "descricao": config["descricao"],
        "modelo": config["modelo"],
        "tarefa_huggingface": config["tarefa_hf"],
        "gerativo": config["gerativo"],
        "carregado": motor is not None,
        "ja_baixado": ja_baixado(tarefa),
        "arquitetura": type(motor.model).__name__ if motor else None,
        "parametros": sum(p.numel() for p in motor.model.parameters()) if motor else None,
        "dispositivo": str(motor.device) if motor else None,
        "limite_de_tokens": config["limite_tokens"],
        "rotulos": config["rotulos"],
        "segundos_de_carga": estado["segundos_de_carga"],
        "carregado_em": estado["carregado_em"],
        "erro": estado["erro"],
        "aviso": AVISOS[tarefa],
    }


def informacoes():
    """Ficha de todos os modelos mais o ambiente local. Nao carrega nada."""
    return {
        "execucao": "local, nesta máquina, sem chamada a serviço externo",
        "cache_local": pasta_do_cache(),
        "bibliotecas": versoes(),
        "parametros_de_geracao": GERACAO,
        "modelos": [ficha(tarefa) for tarefa in TAREFAS],
    }


# ---------------------------------------------------------------- inferencia

def _contar_tokens(motor, textos):
    # tokenize em vez de encode: conta o tamanho real sem emitir aviso de sequencia longa
    return [len(motor.tokenizer.tokenize(t)) + 2 for t in textos]


def _distribuicao(pontuacoes):
    # traduz os rotulos e ordena do mais provavel ao menos provavel
    itens = [
        {"rotulo": ROTULOS.get(p["label"], p["label"]), "pontuacao": round(float(p["score"]), 4)}
        for p in pontuacoes
    ]
    return sorted(itens, key=lambda item: -item["pontuacao"])


def classificar(textos):
    """Classifica uma lista de textos e devolve uma lista de resultados, na mesma ordem.

    Um unico caminho de codigo para um texto e para muitos: o pipeline recebe sempre lista,
    o que evita tratar duas formas de retorno diferentes.
    """
    motor = carregar("sentimento")
    textos = [str(t) for t in textos]
    if not textos:
        return []
    limite = MODELOS["sentimento"]["limite_tokens"]

    inicio = time.perf_counter()
    try:
        tamanhos = _contar_tokens(motor, textos)
        bruto = motor(textos)
    except Exception as erro:
        raise ErroDeInferencia(f"{type(erro).__name__}: {erro}") from erro
    decorrido = time.perf_counter() - inicio

    saida = []
    for texto, tokens, pontuacoes in zip(textos, tamanhos, bruto):
        distribuicao = _distribuicao(pontuacoes)
        saida.append({
            "rotulo": distribuicao[0]["rotulo"],
            "confianca": distribuicao[0]["pontuacao"],
            "distribuicao": distribuicao,
            "caracteres": len(texto),
            "tokens": tokens,
            "texto_truncado": tokens > limite,
            "limite_de_tokens": limite,
            "segundos": round(decorrido / len(textos), 3),
        })
    return saida


def resumir(textos):
    """Resume uma lista de textos e devolve uma lista de resultados, na mesma ordem.

    O resumo e **abstrativo**: o modelo reescreve, nao recorta. Por isso o resultado carrega
    a taxa de compressao e a marca de truncagem - quem le precisa saber de quanto texto o
    resumo saiu e se o modelo chegou a ver o texto inteiro.

    Carrega tambem a conferencia de texto.conferir_resumo, e carrega sempre: nenhum resumo
    sai desta funcao sem ela. Deixar a conferencia a cargo de quem chama seria confiar em
    que todo consumidor se lembre de pedi-la, e e justamente o resumo nao conferido que
    produz o dano descrito no risco 8.4 do Project Charter.
    """
    motor = carregar("resumo")
    textos = [str(t) for t in textos]
    if not textos:
        return []
    limite = MODELOS["resumo"]["limite_tokens"]

    inicio = time.perf_counter()
    try:
        tamanhos = _contar_tokens(motor, textos)
        bruto = motor.gerar(textos, limite, **GERACAO)
    except Exception as erro:
        raise ErroDeInferencia(f"{type(erro).__name__}: {erro}") from erro
    decorrido = time.perf_counter() - inicio

    saida = []
    for texto, tokens, resumo in zip(textos, tamanhos, bruto):
        palavras_entrada = len(texto.split())
        palavras_resumo = len(resumo.split())
        saida.append({
            "resumo": resumo,
            "palavras_entrada": palavras_entrada,
            "palavras_resumo": palavras_resumo,
            "taxa_de_compressao": round(palavras_resumo / palavras_entrada, 3) if palavras_entrada else 0.0,
            "conferencia": tx.conferir_resumo(resumo, texto),
            "caracteres": len(texto),
            "tokens": tokens,
            "texto_truncado": tokens > limite,
            "limite_de_tokens": limite,
            "segundos": round(decorrido / len(textos), 2),
        })
    return saida


# despacho por tarefa, para que api.py nao precise de um if por rota
EXECUTORES = {"sentimento": classificar, "resumo": resumir}


def processar(tarefa, textos):
    """Executa a tarefa pedida sobre a lista de textos."""
    conferir_tarefa(tarefa)
    return EXECUTORES[tarefa](textos)
