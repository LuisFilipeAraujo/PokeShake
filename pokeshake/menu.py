"""Menu overlay de seleção de modo e o ícone da bandeja."""
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QPushButton,
                             QVBoxLayout, QWidget)

from . import config as cfg

MODOS = [
    ("shake", "Modo Agitada", "Sacuda o mouse e um Pokémon aparece"),
    ("catch", "Modo Caçada",
     f"Segure {cfg.GESTO_NOME} e arremesse a pokébola no Pokémon"),
    ("off", "Pausado", "Nada acontece até você escolher um modo"),
]

ESTILO = """
#painel {
    background: rgba(24, 27, 38, 242);
    border: 1px solid rgba(120, 132, 168, 90);
    border-radius: 16px;
}
#titulo { color: #f4f6fb; font-size: 15px; font-weight: 600; }
#fechar {
    color: #aab3c9; background: transparent; border: none;
    font-size: 16px; font-weight: 600; padding: 0;
}
#fechar:hover { color: #ffffff; }
QPushButton[modo="true"] {
    text-align: left; padding: 9px 12px; border-radius: 10px;
    background: rgba(255, 255, 255, 14); border: 1px solid transparent;
    color: #e7ebf5; font-size: 13px;
}
QPushButton[modo="true"]:hover { background: rgba(255, 255, 255, 30); }
QPushButton[modo="true"][ativo="true"] {
    background: rgba(238, 21, 21, 55); border-color: #ee1515; color: #ffffff;
}
#dica { color: #98a1b8; font-size: 11px; }
#sair {
    color: #aab3c9; background: transparent; border: none; font-size: 12px;
}
#sair:hover { color: #ff8080; }
"""


def pokeball_icon(size: int = 64) -> QIcon:
    """Ícone desenhado na hora, para não depender de arquivo no disco."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = QRect(2, 2, size - 5, size - 5)
    p.setPen(QPen(QColor("#1b1b1b"), max(2, size // 16)))
    p.setBrush(QColor("#f5f5f5"))
    p.drawEllipse(r)
    p.setBrush(QColor("#ee1515"))
    p.drawChord(r, 0, 180 * 16)
    p.drawLine(r.left(), r.center().y(), r.right(), r.center().y())
    p.setBrush(QColor("#f5f5f5"))
    b = size // 5
    p.drawEllipse(r.center() - QPoint(b // 2, b // 2), b, b)
    p.end()
    return QIcon(pix)


class OverlayMenu(QWidget):
    """Painel flutuante para escolher o modo. Arrastável pelo corpo."""

    modo_escolhido = pyqtSignal(str)
    sair = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(ESTILO)
        self._arrasto = None
        self.botoes = {}

        painel = QWidget(self)
        painel.setObjectName("painel")
        fora = QVBoxLayout(self)
        fora.setContentsMargins(0, 0, 0, 0)
        fora.addWidget(painel)

        col = QVBoxLayout(painel)
        col.setContentsMargins(16, 14, 16, 14)
        col.setSpacing(8)

        topo = QHBoxLayout()
        marca = QLabel()
        marca.setPixmap(pokeball_icon(20).pixmap(20, 20))
        titulo = QLabel("PokeShake")
        titulo.setObjectName("titulo")
        fechar = QPushButton("✕")
        fechar.setObjectName("fechar")
        fechar.setFixedSize(22, 22)
        fechar.setCursor(Qt.CursorShape.PointingHandCursor)
        fechar.clicked.connect(self.hide)
        self.botao_fechar = fechar
        topo.addWidget(marca)
        topo.addWidget(titulo)
        topo.addStretch(1)
        topo.addWidget(fechar)
        col.addLayout(topo)

        for chave, nome, _ in MODOS:
            b = QPushButton(nome)
            b.setProperty("modo", "true")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=chave: self._escolher(c))
            col.addWidget(b)
            self.botoes[chave] = b

        self.dica = QLabel("")
        self.dica.setObjectName("dica")
        self.dica.setWordWrap(True)
        col.addWidget(self.dica)

        rodape = QHBoxLayout()
        rodape.addStretch(1)
        sair = QPushButton("Sair do PokeShake")
        sair.setObjectName("sair")
        sair.setCursor(Qt.CursorShape.PointingHandCursor)
        sair.clicked.connect(self.sair.emit)
        rodape.addWidget(sair)
        col.addLayout(rodape)

        self.setFixedWidth(300)
        self.marcar("off")

    def permitir_fechar(self, pode: bool):
        """Sem bandeja para reabrir o menu, ele não pode ser fechado."""
        self.botao_fechar.setVisible(pode)

    def _escolher(self, chave):
        self.modo_escolhido.emit(chave)

    def marcar(self, modo):
        """Destaca o modo ativo e mostra a dica correspondente."""
        for chave, b in self.botoes.items():
            b.setProperty("ativo", "true" if chave == modo else "false")
            b.style().unpolish(b)
            b.style().polish(b)
        self.dica.setText(next(d for c, _, d in MODOS if c == modo))

    def aparecer(self):
        """Mostra perto do canto inferior direito da tela sob o cursor."""
        if self.pos().isNull():
            tela = (QApplication.screenAt(self.cursor().pos())
                    or QApplication.primaryScreen()).availableGeometry()
            self.adjustSize()
            self.move(tela.right() - self.width() - 24,
                      tela.bottom() - self.height() - 24)
        self.show()
        self.raise_()

    def alternar(self):
        self.hide() if self.isVisible() else self.aparecer()

    # arrastar o painel
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._arrasto = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self._arrasto is not None:
            self.move(event.globalPosition().toPoint() - self._arrasto)

    def mouseReleaseEvent(self, event):
        self._arrasto = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
