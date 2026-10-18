"""Grito do Pokémon no momento da captura.

Os gritos vêm do repositório PokeAPI/cries e chegam em formatos misturados —
a maioria Ogg Vorbis, alguns MP3, com a extensão .ogg nos dois casos. O backend
de mídia do Qt (FFmpeg) decodifica ambos, e é ele quem decide pelo conteúdo, não
pela extensão.
"""
import atexit
import os
import re
import sys
import threading
import time
import traceback

from PyQt6.QtCore import QObject, QUrl, pyqtSignal

from . import config as cfg
from . import sprites

try:
    from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
    AUDIO = True
except ImportError:                 # build de PyQt6 sem QtMultimedia
    AUDIO = False

# o backend escreve direto no descritor 2, fora do log do Qt, uma ou duas linhas
# por decodificação: "[mp3float @ 0x...] Could not update timestamps..."
RUIDO_DO_BACKEND = re.compile(rb"^\[[\w/]+ @ [0-9A-Fa-fx]+\] ")
_filtro_instalado = False


def filtrar_ruido_do_backend():
    """Desvia o stderr por um cano e descarta só as linhas do FFmpeg.

    Calar o descritor inteiro durante a reprodução seria mais simples, mas
    engoliria um traceback de verdade que caísse no mesmo instante — e um
    traceback engolido mata o app em silêncio. Aqui tudo o que não é ruído do
    backend é repassado, linha por linha.
    """
    global _filtro_instalado
    if _filtro_instalado:
        return
    _filtro_instalado = True
    try:
        original = os.dup(2)
        leitura, escrita = os.pipe()
        os.dup2(escrita, 2)
        os.close(escrita)
    except OSError:
        return                      # sem stderr utilizável (pythonw, serviço)

    def bombeia():
        with os.fdopen(leitura, "rb", buffering=0) as cano:
            for linha in iter(cano.readline, b""):
                if not RUIDO_DO_BACKEND.match(linha):
                    os.write(original, linha)
    leitor = threading.Thread(target=bombeia, daemon=True, name="filtro-stderr")
    leitor.start()

    def drenar():
        """Devolve o descritor e espera o cano esvaziar: a última linha escrita
        antes da saída se perderia com o processo."""
        try:
            sys.stderr.flush()
        except (OSError, ValueError):
            pass
        os.dup2(original, 2)        # sem lado de escrita, o leitor vê o fim
        leitor.join(timeout=1.0)
    atexit.register(drenar)

    def excecao_nao_tratada(tipo, valor, tb):
        """Traceback vai direto ao descritor original.

        O PyQt aborta o processo logo depois de imprimir uma exceção que escapou
        de um slot, sem rodar atexit: pelo cano, a mensagem morreria com ele e o
        app cairia em silêncio.
        """
        texto = "".join(traceback.format_exception(tipo, valor, tb))
        os.write(original, texto.encode("utf-8", "replace"))
    sys.excepthook = excecao_nao_tratada


class Gritos(QObject):
    """Toca o grito do Pokémon capturado.

    Um player só, reaproveitado: criar um por captura acumularia recursos de
    áudio. O arquivo normalmente já está no cache, porque o grito é baixado
    junto com o sprite quando o Pokémon aparece — assim a captura não espera
    download nenhum para soar.
    """

    baixado = pyqtSignal(int, float)

    def __init__(self, volume=None, ligado=None, parent=None):
        super().__init__(parent)
        self.volume = cfg.CRY_VOLUME if volume is None else volume
        # volume e liga/desliga são coisas diferentes: dá para silenciar na hora
        # de uma reunião sem perder o volume escolhido
        self.ligado = (self.volume > 0) if ligado is None else ligado
        self.player = None
        self.saida = None
        self.baixado.connect(self._tocar_baixado)

    @property
    def disponivel(self) -> bool:
        return AUDIO and self.ligado

    def alternar(self) -> bool:
        """Liga ou desliga o som. Devolve o novo estado."""
        self.ligado = not self.ligado
        return self.ligado

    def tocar(self, pid: int):
        """Toca o grito agora, ou assim que ele chegar."""
        if not self.disponivel:
            return
        caminho = sprites.arquivo_do_grito(pid)
        if caminho is not None:
            self._toca(caminho)
            return

        pedido = time.monotonic()

        def worker():
            if sprites.fetch_cry(pid):
                self.baixado.emit(pid, pedido)
        threading.Thread(target=worker, daemon=True).start()

    def _tocar_baixado(self, pid, pedido):
        # chegou depois da comemoração: soar agora seria um grito solto na mesa
        if not self.disponivel or time.monotonic() - pedido > cfg.CRY_ATRASO_MAX_S:
            return
        caminho = sprites.arquivo_do_grito(pid)
        if caminho is not None:
            self._toca(caminho)

    def _toca(self, caminho):
        if self.player is None:
            self._montar()
        self.player.setSource(QUrl.fromLocalFile(str(caminho)))
        self.player.setPosition(0)
        self.player.play()

    def _montar(self):
        """Monta o player na primeira vez, não no arranque do app: quem nunca
        captura nada não paga a inicialização do backend de mídia."""
        filtrar_ruido_do_backend()
        self.saida = QAudioOutput(self)
        self.saida.setVolume(self.volume)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.saida)
