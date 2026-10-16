"""Download, cache em disco e preparo dos sprites para desenho."""
import json
import random
import threading

import requests
from PyQt6.QtCore import Qt, QBuffer, QByteArray, QSize
from PyQt6.QtGui import QMovie, QPixmap

from . import config as cfg

cfg.CACHE_DIR.mkdir(exist_ok=True)

_session = requests.Session()
_session.headers["User-Agent"] = cfg.USER_AGENT
_lock = threading.Lock()
_names = None


def _download(url, path):
    """Baixa para o cache. Devolve os bytes, ou None se não existir."""
    if path.exists():
        return path.read_bytes()
    if path.with_suffix(path.suffix + ".missing").exists():
        return None
    try:
        r = _session.get(url, timeout=8)
    except requests.RequestException:
        return None
    if r.ok and r.content:
        path.write_bytes(r.content)
        return r.content
    if r.status_code == 404:
        # nem todo Pokémon tem sprite animado; anota para não repetir o 404
        path.with_suffix(path.suffix + ".missing").touch()
    return None


def fetch_pokemon(pid: int):
    """Devolve (bytes, is_gif) do sprite do Pokémon, animado se houver."""
    for url in cfg.SPRITE_URLS:
        ext = url.rsplit(".", 1)[-1]
        data = _download(url.format(id=pid), cfg.CACHE_DIR / f"{pid}.{ext}")
        if data:
            return data, ext == "gif"
    return None, False


def fetch_ball(name: str):
    """Devolve os bytes do sprite de uma pokébola."""
    return _download(cfg.BALL_URL.format(name=name), cfg.CACHE_DIR / f"ball-{name}.png")


def random_ball() -> str:
    return random.choice(cfg.BALLS)


def pokemon_name(pid: int) -> str:
    """Nome do Pokémon. A lista inteira vem numa chamada só e fica em cache."""
    global _names
    with _lock:
        if _names is None:
            _names = _load_names()
    nome = _names.get(str(pid))
    return nome.replace("-", " ").title() if nome else f"Pokémon #{pid}"


def _load_names() -> dict:
    path = cfg.CACHE_DIR / "names.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    try:
        r = _session.get(f"{cfg.POKEAPI}/pokemon?limit={cfg.MAX_ID}", timeout=15)
        if r.ok:
            nomes = {str(i + 1): p["name"] for i, p in enumerate(r.json()["results"])}
            path.write_text(json.dumps(nomes), encoding="utf-8")
            return nomes
    except (requests.RequestException, ValueError, KeyError, OSError):
        pass
    return {}


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
