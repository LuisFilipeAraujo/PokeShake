"""Download, cache em disco e preparo dos sprites para desenho."""
import json
import random
import threading
import time

import requests
from PyQt6.QtCore import Qt, QBuffer, QByteArray, QSize
from PyQt6.QtGui import QMovie, QPixmap

from . import config as cfg

cfg.CACHE_DIR.mkdir(exist_ok=True)

_session = requests.Session()
_session.headers["User-Agent"] = cfg.USER_AGENT
_lock = threading.Lock()
_names = None
_ultima_tentativa_nomes = 0.0

# bytes iniciais de PNG e GIF: rede com portal cativo responde 200 com a página
# de login, e gravar isso no cache cria um sprite invisível permanente
ASSINATURAS = (bytes.fromhex("89504e47"), b"GIF8")   # cabecalho de PNG e de GIF


class Falhas:
    """Lembra a última falha de download, para a interface poder avisar.

    Sem isso o app fica mudo quando não há rede: nenhum sprite aparece e nada
    explica o motivo, então sacudir o mouse parece defeito.

    Um 404 não entra aqui: ele prova que a rede está de pé, e a ausência do
    sprite animado é esperada e coberta pelo PNG estático.
    """

    def __init__(self):
        self.quando = 0.0
        self.motivo = ""
        self.assunto = "o sprite"

    def registrar(self, motivo: str, assunto: str = "o sprite"):
        with _lock:
            self.quando = time.monotonic()
            self.motivo = motivo
            self.assunto = assunto

    def limpar(self):
        with _lock:
            self.quando = 0.0
            self.motivo = ""

    def recente(self, janela=None) -> bool:
        janela = cfg.AVISO_FALHA_S if janela is None else janela
        return bool(self.quando) and time.monotonic() - self.quando < janela


falhas = Falhas()


def _parece_imagem(data: bytes) -> bool:
    return data.startswith(ASSINATURAS)


def _parece_audio(data: bytes) -> bool:
    """Ogg, MP3 com tag ID3, WAV, ou quadro de MP3 cru (11 bits de sincronismo)."""
    if data.startswith((b"OggS", b"ID3", b"RIFF")):
        return True
    return len(data) > 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0


def _download(url, path, assunto="o sprite", tumulo=True, valida=None, avisar=True):
    """Baixa para o cache. Devolve os bytes, ou None se não existir.

    `tumulo` diz se um 404 pode ser anotado em disco como ausência definitiva.
    Só vale para o que de fato pode faltar na Pokédex: anotar o que deveria
    existir mataria aquele Pokémon para sempre naquela máquina, caso o 404
    tenha vindo da rede e não do repositório.
    """
    valida = valida or _parece_imagem
    if path.exists():
        return path.read_bytes()
    if path.with_suffix(path.suffix + ".missing").exists():
        return None
    try:
        r = _session.get(url, timeout=8)
    except requests.RequestException:
        if avisar:
            falhas.registrar("sem conexão", assunto)
        return None
    if r.ok and r.content:
        if not valida(r.content):
            if avisar:
                falhas.registrar("a rede devolveu outra coisa no lugar da imagem",
                                 assunto)
            return None
        path.write_bytes(r.content)
        falhas.limpar()
        return r.content
    if r.status_code == 404 and tumulo:
        # nem todo Pokémon tem sprite animado; anota para não repetir o 404
        path.with_suffix(path.suffix + ".missing").touch()
        falhas.limpar()
        return None
    if avisar:
        falhas.registrar(f"o servidor respondeu {r.status_code}", assunto)
    return None


def fetch_pokemon(pid: int):
    """Devolve (bytes, is_gif) do sprite do Pokémon, animado se houver."""
    for url in cfg.SPRITE_URLS:
        ext = url.rsplit(".", 1)[-1]
        # só o GIF animado pode ganhar lápide: todo ID da Pokédex tem PNG, então
        # 404 nele é a rede mentindo, não ausência de verdade
        data = _download(url.format(id=pid), cfg.CACHE_DIR / f"{pid}.{ext}",
                         tumulo=(ext == "gif"))
        if data:
            return data, ext == "gif"
    return None, False


def fetch_ball(name: str):
    """Devolve os bytes do sprite de uma pokébola."""
    return _download(cfg.BALL_URL.format(name=name),
                     cfg.CACHE_DIR / f"ball-{name}.png",
                     assunto="a pokébola", tumulo=False)


def random_ball() -> str:
    return random.choice(cfg.BALLS)


def _caminho_do_grito(pid: int):
    return cfg.CACHE_DIR / f"cry-{pid}.ogg"


def fetch_cry(pid: int):
    """Grito do Pokémon.

    Falha aqui não vira aviso na tela: o som é enfeite, e dizer "não consegui
    baixar" por causa dele assustaria sem motivo.
    """
    return _download(cfg.CRY_URL.format(id=pid), _caminho_do_grito(pid),
                     assunto="o grito", valida=_parece_audio, avisar=False)


def arquivo_do_grito(pid: int):
    """Caminho do grito já em cache, ou None."""
    caminho = _caminho_do_grito(pid)
    return caminho if caminho.exists() else None


def miniatura(pid: int, lado: int = 64):
    """Miniatura do sprite já em cache, ou None.

    Não toca na rede de propósito: a tela da Pokédex abre com dezenas de
    sprites de uma vez, e baixar ali travaria a interface. Quem foi capturado
    já passou pelo cache.
    """
    for ext in ("png", "gif"):
        caminho = cfg.CACHE_DIR / f"{pid}.{ext}"
        if not caminho.exists():
            continue
        pix = QPixmap()
        try:
            pix.loadFromData(caminho.read_bytes())
        except OSError:
            continue
        if not pix.isNull():
            return pix.scaled(lado, lado, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
    return None


def pokemon_name(pid: int) -> str:
    """Nome do Pokémon, sem tocar na rede.

    É chamado da thread da interface no instante da captura: um timeout aqui
    congelaria o overlay no meio da comemoração. Quem busca a lista é o
    prefetch_names, de uma thread de fundo.
    """
    global _names
    with _lock:
        if _names is None:
            _names = _nomes_do_disco() or {}
        nomes = _names
    nome = nomes.get(str(pid))
    return nome.replace("-", " ").title() if nome else f"Pokémon #{pid}"


def prefetch_names() -> bool:
    """Garante a lista de nomes em memória. Faz rede: chame de thread de fundo.

    Uma lista vazia nunca é memoizada como definitiva, senão a sessão que
    começasse sem internet mostraria "Pokémon #25" para sempre, mesmo com a
    rede voltando no minuto seguinte.
    """
    global _names, _ultima_tentativa_nomes
    with _lock:
        if _names:
            return True
        # sem recuo, cada aparição pagaria o timeout inteiro de novo
        if time.monotonic() - _ultima_tentativa_nomes < cfg.NOMES_RETRY_S:
            return False
        _ultima_tentativa_nomes = time.monotonic()
    nomes = _nomes_do_disco() or _baixar_nomes()
    if not nomes:
        return False
    with _lock:
        _names = nomes
    return True


def _nomes_do_disco():
    path = cfg.CACHE_DIR / "names.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return None


def _baixar_nomes():
    """Os 1025 nomes vêm numa chamada só, de uns 68 KB."""
    try:
        r = _session.get(f"{cfg.POKEAPI}/pokemon?limit={cfg.MAX_ID}", timeout=10)
        if r.ok:
            nomes = {str(i + 1): p["name"] for i, p in enumerate(r.json()["results"])}
            (cfg.CACHE_DIR / "names.json").write_text(json.dumps(nomes), encoding="utf-8")
            return nomes
    except (requests.RequestException, ValueError, KeyError, OSError):
        pass
    return None


class Sprite:
    """Sprite pronto para desenhar, animado ou não.

    O QBuffer e o QMovie ficam sob o mesmo dono em Python de propósito: se o
    buffer morresse antes, o filme ainda rodando leria memória já liberada.
    """

    def __init__(self, data: bytes, is_gif: bool, scale=None, target_h=None):
        self.movie = None
        self.buf = None
        if is_gif:
            self.buf = QBuffer()
            self.buf.setData(QByteArray(data))
            self.buf.open(QBuffer.OpenModeFlag.ReadOnly)
            self.movie = QMovie(self.buf, QByteArray(b"gif"))
            self.movie.setCacheMode(QMovie.CacheMode.CacheAll)
            self.movie.jumpToFrame(0)
            bruto = self.movie.currentImage().size()
            self.size = _escalar(bruto, scale, target_h)
            self.movie.setScaledSize(self.size)
            self.movie.start()
        else:
            pix = QPixmap()
            pix.loadFromData(data)
            self.size = _escalar(pix.size(), scale, target_h)
            self.pixmap = pix.scaled(self.size, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.FastTransformation)
            self.size = self.pixmap.size()

    def frame(self) -> QPixmap:
        """Quadro atual, para o paintEvent."""
        return self.movie.currentPixmap() if self.movie else self.pixmap

    def stop(self):
        if self.movie is not None:
            self.movie.stop()


def _escalar(size: QSize, scale, target_h) -> QSize:
    """Sprites da Pokédex variam muito de tamanho; target_h uniformiza os alvos."""
    if not size.isValid() or size.height() <= 0:
        return QSize(96, 96)
    if target_h:
        fator = max(1.0, min(4.0, target_h / size.height()))
    else:
        fator = scale or 1
    return QSize(int(size.width() * fator), int(size.height() * fator))
