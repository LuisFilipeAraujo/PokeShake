"""Monta o aplicativo: bandeja, menu de modos e a troca entre eles."""
import signal
import sys

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import config as cfg
from .catch import CatchMode
from .menu import MODOS, OverlayMenu, pokeball_icon
from .pointer import Pointer
from .shake import ShakeMode


class PokeShake(QObject):
    """Só um modo roda por vez; a troca liga um e desliga o outro."""

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.pointer = Pointer(self)
        self.shake = ShakeMode(self.pointer, self)
        self.catch = CatchMode(self.pointer, self)
        self.modo = "off"

        self.menu = OverlayMenu()
        self.menu.modo_escolhido.connect(self.set_modo)
        self.menu.sair.connect(app.quit)
        self.pointer.escape_pressed.connect(lambda: self.set_modo("off"))
        self.catch.captured.connect(self._capturou)

        self.tray = self._montar_bandeja()
        app.aboutToQuit.connect(self.cleanup)

    def _montar_bandeja(self) -> QSystemTrayIcon:
        tray = QSystemTrayIcon(pokeball_icon(), self)
        tray.setToolTip("PokeShake")
        menu = QMenu()
        self.acoes = {}
        for chave, nome, _ in MODOS:
            a = QAction(nome, menu)
            a.setCheckable(True)
            a.triggered.connect(lambda _=False, c=chave: self.set_modo(c))
            menu.addAction(a)
            self.acoes[chave] = a
        menu.addSeparator()
        abrir = QAction("Abrir menu", menu)
        abrir.triggered.connect(self.menu.aparecer)
        menu.addAction(abrir)
        sair = QAction("Sair", menu)
        sair.triggered.connect(self.app.quit)
        menu.addAction(sair)
        tray.setContextMenu(menu)
        tray.menu = menu            # o menu precisa sobreviver a esta função
        tray.activated.connect(self._clique_na_bandeja)
        tray.show()
        return tray

    def _clique_na_bandeja(self, motivo):
        if motivo in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.menu.alternar()

    def set_modo(self, modo: str):
        if modo not in {c for c, _, _ in MODOS}:
            print(f"Modo desconhecido: {modo!r}. Use shake, catch ou off.")
            modo = "off"
        if modo == self.modo:
            return
        self.shake.stop()
        self.catch.stop()
        if modo == "shake":
            self.shake.start()
        elif modo == "catch":
            self.catch.start()
        self.modo = modo

        self.menu.marcar(modo)
        for chave, a in self.acoes.items():
            a.setChecked(chave == modo)
        nome = next(n for c, n, _ in MODOS if c == modo)
        self.tray.setToolTip(f"PokeShake — {nome}")

    def _capturou(self, nome):
        self.tray.setToolTip(f"PokeShake — {nome} capturado! "
                             f"({self.catch.capturados} no total)")

    def cleanup(self):
        self.shake.stop()
        self.catch.stop()
        self.menu.hide()


def modo_pedido(argv) -> str:
    """Lê o modo da linha de comando, sem derrubar o app por argumento torto."""
    if "--mode" in argv:
        i = argv.index("--mode") + 1
        if i >= len(argv):
            print("--mode precisa de um valor: shake, catch ou off.")
            return "off"
        return argv[i]
    if "--demo" in argv:
        return "shake"
    return "off"


def main(argv=None):
    argv = sys.argv if argv is None else argv
    app = QApplication(argv)
    app.setQuitOnLastWindowClosed(False)

    poke = PokeShake(app)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        # sem bandeja, fechar o menu deixaria o app sem nenhuma porta de entrada
        poke.menu.permitir_fechar(False)
        print("Sem área de notificação neste sistema: o menu na tela fica "
              "sempre disponível, e Ctrl+C encerra.")

    if "--dry-run" in argv:
        from .dryrun import DryRun
        dry = DryRun(app, poke)
        poke.menu.aparecer()
        dry.start()
        app.exec()
        return dry.codigo

    modo = modo_pedido(argv)
    poke.set_modo(modo)

    if modo == "off":
        poke.menu.aparecer()
    if "--demo" in argv:                        # execução curta, para teste
        poke.shake.summon_at_cursor()
        QTimer.singleShot(cfg.SHAKE_DISPLAY_MS + 1500, app.quit)

    # o timer do Pointer mantém o Ctrl+C funcionando durante o app.exec()
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    atual = next(n for c, n, _ in MODOS if c == poke.modo)
    print(f"PokeShake no ar - {atual}. Troque de modo no menu ou no ícone da "
          f"bandeja. (Ctrl+C para sair)")
    return app.exec()
