"""Modo Agitada: sacuda o mouse e um Pokémon aparece por alguns segundos."""
import random
import threading
import time
from collections import deque

from PyQt6.QtCore import (Qt, QObject, QPoint, QTimer, QEasingCurve,
                          QParallelAnimationGroup, QPropertyAnimation, pyqtSignal)
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from . import config as cfg
from . import sprites


class ShakeDetector:
    """Conta zigue-zagues horizontais: cada inversão precisa de um trecho de
    SHAKE_SEGMENT_PX a partir do extremo anterior, então movimento normal de
    mouse nunca dispara."""

    def __init__(self, on_shake):
        self.on_shake = on_shake
        self.points = deque()
        self.last_trigger = 0.0

    def on_move(self, x, y):
        now = time.time()
        self.points.append((now, x, y))
        while self.points and now - self.points[0][0] > cfg.SHAKE_WINDOW:
            self.points.popleft()
        if now - self.last_trigger < cfg.SHAKE_COOLDOWN or len(self.points) < 5:
            return

        reversals, direction, anchor = 0, 0, self.points[0][1]
        for _, px, _ in self.points:
            dx = px - anchor
            if abs(dx) >= cfg.SHAKE_SEGMENT_PX:
                d = 1 if dx > 0 else -1
                if direction and d != direction:
                    reversals += 1
                direction, anchor = d, px
            elif direction and dx * direction > 0:
                anchor = px  # acompanha o extremo na direção atual

        if reversals >= cfg.SHAKE_REVERSALS:
            self.last_trigger = now
            self.points.clear()
            self.on_shake(x, y)


class SpritePopup(QWidget):
    """Janelinha sem borda, sempre no topo e transparente a cliques."""

    def __init__(self, data: bytes, is_gif: bool, x: int, y: int):
        super().__init__(None, Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool
                         | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        label = QLabel(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label)

        self.sprite = sprites.Sprite(data, is_gif, scale=cfg.SHAKE_SCALE)
        size = self.sprite.size
        if self.sprite.movie is not None:
            label.setMovie(self.sprite.movie)
        else:
            label.setPixmap(self.sprite.frame())

        self.resize(size)
        start = self.clamp(QPoint(x - size.width() // 2, y - size.height() // 2), size)
        self.move(start)
        self.show()

        move = QPropertyAnimation(self, b"pos", self)
        move.setDuration(cfg.SHAKE_DISPLAY_MS)
        move.setStartValue(start)
        move.setEndValue(start + QPoint(random.randint(-60, 60), -120))
        move.setEasingCurve(QEasingCurve.Type.OutCubic)

        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(cfg.SHAKE_DISPLAY_MS)
        fade.setKeyValueAt(0.0, 0.0)
        fade.setKeyValueAt(0.1, 1.0)
        fade.setKeyValueAt(0.7, 1.0)
        fade.setKeyValueAt(1.0, 0.0)

        self.anim = QParallelAnimationGroup(self)
        self.anim.addAnimation(move)
        self.anim.addAnimation(fade)
        # fecha fora do sinal: o grupo é filho da janela e morreria junto com ela
        self.anim.finished.connect(lambda: QTimer.singleShot(0, self.close))
        self.anim.start()

    def closeEvent(self, event):
        self.sprite.stop()
        super().closeEvent(event)

    @staticmethod
    def clamp(p: QPoint, size) -> QPoint:
        screen = QApplication.screenAt(p) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        x = min(max(p.x(), area.left()), area.right() - size.width())
        y = min(max(p.y(), area.top()), area.bottom() - size.height())
        return QPoint(x, y)


class ShakeMode(QObject):
    """Liga o detector de agitada ao download e à exibição do sprite."""

    sprite_ready = pyqtSignal(bytes, bool, int, int)

    def __init__(self, pointer, parent=None):
        super().__init__(parent)
        self.pointer = pointer
        self.popups = []
        self.detector = ShakeDetector(self.summon)
        self.ativo = False
        self.sprite_ready.connect(self._show)

    def start(self):
        if not self.ativo:
            self.pointer.moved.connect(self._on_move)
            self.ativo = True

    def stop(self):
        if self.ativo:
            self.pointer.moved.disconnect(self._on_move)
            self.ativo = False
        self.cleanup()

    def _on_move(self, pos):
        self.detector.on_move(pos.x(), pos.y())

    def summon(self, x, y):
        """Baixa um Pokémon aleatório sem travar a interface."""
        def worker():
            pid = random.randint(1, cfg.MAX_ID)
            data, is_gif = sprites.fetch_pokemon(pid)
            if data:
                self.sprite_ready.emit(data, is_gif, int(x), int(y))
        threading.Thread(target=worker, daemon=True).start()

    def summon_at_cursor(self):
        pos = self.pointer.pos
        self.summon(pos.x(), pos.y())

    def _show(self, data, is_gif, x, y):
        popup = SpritePopup(data, is_gif, x, y)
        self.popups.append(popup)
        # a lista só pode guardar janelas vivas: mexer numa já destruída quebra o Qt
        popup.destroyed.connect(lambda: self._forget(popup))

    def _forget(self, popup):
        if popup in self.popups:
            self.popups.remove(popup)

    def cleanup(self):
        for popup in list(self.popups):
            popup.close()
