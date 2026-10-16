"""Leitura do cursor e do gesto de arremesso.

Tudo por polling do estado das teclas (GetAsyncKeyState), sem hook global:
nada é interceptado nem escondido de outros programas, e nenhuma tecla além
das configuradas aqui é consultada.

As duas leituras do dispositivo ficam nas funções `ler_cursor` e `pressionado`,
de propósito: são o único ponto que os testes e o dry run trocam para roteirizar
a entrada sem mexer no mouse da máquina.
"""
import ctypes
import sys
import time
from collections import deque

from PyQt6.QtCore import QObject, QPoint, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor

from . import config as cfg

VK = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12, "middle": 0x04, "right": 0x02}
VK_ESCAPE = 0x1B

def ler_cursor() -> QPoint:
    return QCursor.pos()


if sys.platform == "win32":
    _user32 = ctypes.windll.user32
    _user32.GetAsyncKeyState.restype = ctypes.c_short

    def pressionado(vk: int) -> bool:
        return bool(_user32.GetAsyncKeyState(vk) & 0x8000)
else:  # o app é de Windows; fora dele o gesto simplesmente nunca dispara
    def pressionado(vk: int) -> bool:
        return False


class Pointer(QObject):
    """Fonte única de eventos de mouse para todos os modos."""

    moved = pyqtSignal(QPoint)
    gesture_pressed = pyqtSignal(QPoint)
    gesture_released = pyqtSignal(QPoint)
    escape_pressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.vk = VK.get(cfg.THROW_GESTURE, VK["ctrl"])
        self.pos = ler_cursor()
        self.segurando = False
        self.escape = False
        self.watch_gesture = False   # só o modo caçada liga isso
        self.historico = deque()     # (instante, QPoint) recente, para o arremesso
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(cfg.POLL_MS)

    def tick(self):
        agora = time.monotonic()
        pos = ler_cursor()
        if pos != self.pos:
            self.pos = pos
            self.moved.emit(pos)
        self.historico.append((agora, pos))
        while self.historico and agora - self.historico[0][0] > cfg.FLICK_WINDOW * 2:
            self.historico.popleft()

        if not self.watch_gesture:
            return
        segurando = pressionado(self.vk)
        if segurando != self.segurando:
            self.segurando = segurando
            (self.gesture_pressed if segurando else self.gesture_released).emit(pos)
        escape = pressionado(VK_ESCAPE)
        if escape and not self.escape:
            self.escape_pressed.emit()
        self.escape = escape

    def velocity(self):
        """Velocidade recente do cursor em px/s, para dar direção ao arremesso."""
        agora = time.monotonic()
        recentes = [(t, p) for t, p in self.historico if agora - t <= cfg.FLICK_WINDOW]
        if len(recentes) < 2:
            return 0.0, 0.0
        (t0, p0), (t1, p1) = recentes[0], recentes[-1]
        dt = t1 - t0
        if dt <= 0:
            return 0.0, 0.0
        return (p1.x() - p0.x()) / dt, (p1.y() - p0.y()) / dt
