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
#
# edited 25-11-2026 (TP5): entrou a terceira tarefa, 'conversa', usada pelo assistente com
# memoria de assistente.py. O modelo e o llama3.1:8b, servido pelo Ollama - programa que
# roda nesta mesma maquina e responde por HTTP em 127.0.0.1:11434. Continua valendo a regra
# do arquivo: nada sai da maquina. A diferenca e quem segura os pesos: nas duas tarefas do
# TP4 e este processo, pelo transformers; na conversa e o processo do Ollama, que carrega o
# modelo na GPU quando ha uma. A escolha esta em 3_modeling/assistente_llm.md.

import os
import time
from datetime import datetime
from pathlib import Path

import requests

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
    # edited 25-11-2026 (TP5): 'servidor' marca o modelo que nao e carregado por este
    # processo. limite_tokens aqui e a janela pedida ao Ollama (num_ctx), nao o maximo do
    # modelo, que e 131 mil: 8192 cabe o contexto de dados, a janela de memoria e a resposta.
    "conversa": {
        "modelo": "llama3.1:8b",
        "tarefa_hf": "não se aplica — servido pelo Ollama",
        "descricao": "conversa com memória",
        "limite_tokens": 8192,
        "gerativo": True,
        "rotulos": [],
        "servidor": "ollama",
    },
}

TAREFAS = list(MODELOS)

# edited 25-11-2026 (TP5): endereco do Ollama nesta maquina. A variavel de ambiente existe
# para quem roda o Ollama em outra porta; o padrao e o do proprio Ollama.
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")

# parametros da conversa, fixos e declarados pela mesma razao de GERACAO: temperatura zero e
# semente fixa fazem a mesma pergunta, sobre os mesmos dados, receber a mesma resposta - o
# que torna a verificacao reproduzivel. num_predict limita a resposta a ~300 palavras.
OPCOES_CONVERSA = {"temperature": 0, "seed": 42, "num_ctx": 8192, "num_predict": 450}
# quanto tempo o Ollama mantem o modelo na memoria depois da ultima chamada
MANTER_CARREGADO = "15m"

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
    "conversa": (
        "Resposta gerada por modelo de linguagem, não revisada por pessoa. O modelo recebe os "
        "dados do projeto já apurados por `nucleo.py` e é instruído a não calcular nem "
        "estimar; mesmo assim pode errar. Toda resposta traz a conferência dos seus números, "
        "datas e nomes próprios contra os dados que o modelo recebeu — o que ela aponta como "
        "ausente não está nos dados. Não é recomendação de investimento financeiro."
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
    if MODELOS[tarefa].get("servidor") == "ollama":
        return nome in modelos_no_ollama()
    return (Path(pasta_do_cache()) / f"models--{nome.replace('/', '--')}").exists()


# ---------------------------------------------------------------- ollama (TP5)

def _ollama(caminho, corpo=None, prazo=5):
    """Chamada ao Ollama local. Devolve o JSON da resposta.

    Traduz a falha nos mesmos erros nomeados das outras tarefas, para que api.py responda do
    mesmo jeito: Ollama fora do ar ou modelo nao baixado viram ModeloIndisponivel (503).
    """
    try:
        if corpo is None:
            resposta = requests.get(f"{OLLAMA}{caminho}", timeout=prazo)
        else:
            resposta = requests.post(f"{OLLAMA}{caminho}", json=corpo, timeout=prazo)
    except requests.exceptions.RequestException as erro:
        raise ModeloIndisponivel(
            f"o Ollama não respondeu em {OLLAMA} ({type(erro).__name__}). Inicie o Ollama nesta "
            "máquina — pelo aplicativo, ou com `ollama serve` num terminal."
        ) from erro
    if resposta.status_code == 404:
        nome = MODELOS["conversa"]["modelo"]
        raise ModeloIndisponivel(
            f"o modelo {nome} não está no Ollama. Baixe-o uma vez com `ollama pull {nome}` "
            "(4,9 GB, precisa de rede); depois disso a conversa roda offline."
        )
    if not resposta.ok:
        raise ErroDeInferencia(f"o Ollama respondeu HTTP {resposta.status_code}: {resposta.text[:300]}")
    return resposta.json()


def modelos_no_ollama():
    # nomes dos modelos baixados no Ollama; vazio se ele nao responde. Prazo curto de
    # proposito: e chamada por GET /saude, que tem de continuar barata.
    try:
        return {m.get("name") for m in _ollama("/api/tags", prazo=2).get("models", [])}
    except (ModeloIndisponivel, ErroDeInferencia):
        return set()


def _dispositivo(tamanho, na_gpu):
    # o Ollama informa quanto do modelo esta na memoria de video; o resto fica na RAM
    if not tamanho or not na_gpu:
        return "cpu"
    if na_gpu >= tamanho:
        return "gpu"
    return f"gpu ({na_gpu / tamanho:.0%}) + cpu"


def _ficha_ollama(tarefa):
    # mesma forma da ficha das outras tarefas. Aqui arquitetura e parametros vem do proprio
    # Ollama, que os conhece antes da carga; nas outras so se sabe depois dela.
    config = MODELOS[tarefa]
    estado = _ESTADO[tarefa]
    nome = config["modelo"]
    baixado = nome in modelos_no_ollama()
    carregado, arquitetura, parametros, dispositivo = False, None, None, None
    if baixado:
        try:
            info = _ollama("/api/show", {"model": nome})
            detalhes = info.get("details", {})
            arquitetura = f"{detalhes.get('family', '?')} · {detalhes.get('quantization_level', '?')}"
            parametros = info.get("model_info", {}).get("general.parameter_count")
            for item in _ollama("/api/ps", prazo=2).get("models", []):
                if item.get("name") == nome:
                    carregado = True
                    dispositivo = _dispositivo(item.get("size", 0), item.get("size_vram", 0))
        except (ModeloIndisponivel, ErroDeInferencia):
            pass
    return {
        "tarefa": tarefa,
        "descricao": config["descricao"],
        "modelo": nome,
        "tarefa_huggingface": config["tarefa_hf"],
        "gerativo": config["gerativo"],
        "carregado": carregado,
        "ja_baixado": baixado,
        "arquitetura": arquitetura,
        "parametros": parametros,
        "dispositivo": dispositivo,
        "limite_de_tokens": config["limite_tokens"],
        "rotulos": config["rotulos"],
        "segundos_de_carga": estado["segundos_de_carga"],
        "carregado_em": estado["carregado_em"],
        "erro": estado["erro"],
        "aviso": AVISOS[tarefa],
    }


def _carregar_ollama(tarefa):
    # pede ao Ollama que ponha o modelo na memoria, com a mesma janela que a conversa usa -
    # com outra janela ele recarregaria na primeira pergunta. A falha NAO e memorizada, ao
    # contrario das outras tarefas: conferir o Ollama custa uma requisicao local, e ele pode
    # ser iniciado a qualquer momento depois da subida do servico.
    config = MODELOS[tarefa]
    estado = _ESTADO[tarefa]
    inicio = time.perf_counter()
    try:
        _ollama(
            "/api/generate",
            {"model": config["modelo"], "keep_alive": MANTER_CARREGADO,
             "options": {"num_ctx": OPCOES_CONVERSA["num_ctx"]}},
            prazo=300,
        )
    except (ModeloIndisponivel, ErroDeInferencia) as erro:
        estado["erro"] = str(erro)
        raise ModeloIndisponivel(str(erro)) from erro
    estado.update({
        "motor": "ollama",
        "erro": None,
        "carregado_em": datetime.now().isoformat(timespec="seconds"),
        "segundos_de_carga": round(time.perf_counter() - inicio, 2),
    })
    return estado["motor"]


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

    if config.get("servidor") == "ollama":
        return _carregar_ollama(tarefa)

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
    if MODELOS[tarefa].get("servidor") == "ollama":
        return _ficha_ollama(tarefa)
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
        # edited 25-11-2026 (TP5): campos novos, acrescentados sem mudar os anteriores
        "parametros_da_conversa": OPCOES_CONVERSA,
        "servidor_da_conversa": OLLAMA,
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


def conversar(mensagens):
    """Envia uma conversa ao modelo local e devolve a resposta e o seu custo.

    `mensagens` ja vem no formato do Ollama - papeis system, user e assistant. Quem a monta,
    com os dados do projeto, a memoria e as regras do assistente, e assistente.py; aqui so
    ha o transporte e a contabilidade de tokens e de tempo.
    """
    config = MODELOS["conversa"]
    estado = _ESTADO["conversa"]
    inicio = time.perf_counter()
    try:
        bruto = _ollama(
            "/api/chat",
            {"model": config["modelo"], "messages": mensagens, "stream": False,
             "keep_alive": MANTER_CARREGADO, "options": OPCOES_CONVERSA},
            prazo=300,
        )
    except ModeloIndisponivel as erro:
        estado["erro"] = str(erro)
        raise
    estado["erro"] = None
    return {
        "resposta": str(bruto.get("message", {}).get("content", "")).strip(),
        "tokens_prompt": int(bruto.get("prompt_eval_count") or 0),
        "tokens_resposta": int(bruto.get("eval_count") or 0),
        # 'length' quer dizer que a resposta bateu em num_predict e saiu cortada
        "resposta_cortada": bruto.get("done_reason") == "length",
        "segundos_de_carga": round((bruto.get("load_duration") or 0) / 1e9, 2),
        "segundos": round(time.perf_counter() - inicio, 2),
    }


# despacho por tarefa, para que api.py nao precise de um if por rota. A conversa fica fora:
# ela recebe uma lista de mensagens, nao uma lista de textos, e tem rota propria.
EXECUTORES = {"sentimento": classificar, "resumo": resumir}


def processar(tarefa, textos):
    """Executa a tarefa pedida sobre a lista de textos."""
    conferir_tarefa(tarefa)
    if tarefa not in EXECUTORES:
        raise TarefaDesconhecida(f"a tarefa {tarefa} tem rota própria: POST /assistente")
    return EXECUTORES[tarefa](textos)
