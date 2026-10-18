"""Modo Caçada: Pokémon aparecem pela tela e você arremessa pokébolas neles.

Tudo é desenhado numa única janela transparente do tamanho da área de trabalho,
em vez de uma janela por sprite: assim a colisão, os efeitos e a ordem de
desenho ficam num lugar só.
"""
import math
import random
import threading
import time

from PyQt6.QtCore import Qt, QObject, QPointF, QRect, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QRegion
from PyQt6.QtWidgets import QApplication, QWidget

from . import config as cfg
from . import sprites
from .pokedex import Pokedex

BRANCO = QColor(255, 255, 255)
FAISCA = [QColor(255, 226, 120), QColor(255, 255, 255), QColor(255, 176, 60),
          QColor(140, 220, 255)]


class Wild:
    """Um Pokémon selvagem parado na tela, balançando de leve."""

    def __init__(self, pid: int, sprite: sprites.Sprite, pos: QPointF):
        self.pid = pid
        self.sprite = sprite
        self.base = pos                 # centro, sem o balanço
        self.pos = QPointF(pos)         # centro desenhado neste quadro
        self.nascido = time.monotonic()
        self.fase = random.uniform(0, math.tau)
        self.estado = "livre"           # livre | sugado | fora
        self.escala = 1.0
        self.alpha = 1.0
        self.t_estado = self.nascido

    def step(self, agora, dt):
        if self.estado == "livre":
            balanco = math.sin((agora - self.nascido) * cfg.BOB_SPEED + self.fase)
            self.pos = QPointF(self.base.x(), self.base.y() + balanco * cfg.BOB_PIXELS)
            if agora - self.nascido > cfg.WILD_TTL:
                self.estado = "fora"
                self.t_estado = agora
        elif self.estado == "fora":     # fugiu: sobe e some
            self.pos = QPointF(self.pos.x(), self.pos.y() - 220 * dt)
            self.alpha = max(0.0, 1.0 - (agora - self.t_estado) / 0.6)

    def rect(self) -> QRectF:
        w = self.sprite.size.width() * self.escala
        h = self.sprite.size.height() * self.escala
        return QRectF(self.pos.x() - w / 2, self.pos.y() - h / 2, w, h)

    def hit_rect(self) -> QRectF:
        r = self.rect()
        mw = r.width() * (1 - cfg.HIT_SHRINK) / 2
        mh = r.height() * (1 - cfg.HIT_SHRINK) / 2
        return r.adjusted(mw, mh, -mw, -mh)

    def morto(self) -> bool:
        return self.alpha <= 0.01

    def draw(self, p: QPainter):
        if self.alpha <= 0.01:
            return
        p.save()
        p.setOpacity(self.alpha)
        p.drawPixmap(self.rect().toRect(), self.sprite.frame())
        p.restore()


class Ball:
    """Pokébola: na mão, voando, sugando o Pokémon ou balançando."""

    def __init__(self, kind: str, pixmap: QPixmap, pos: QPointF):
        self.kind = kind
        self.pixmap = pixmap
        self.pos = QPointF(pos)
        self.vel = QPointF(0, 0)
        self.giro = 0.0
        self.escala = 1.0
        self.alpha = 1.0
        self.estado = "mao"             # mao | voando | sugando | balancando | comemorando | fim
        self.t_estado = time.monotonic()
        self.alvo = None

    @property
    def raio(self) -> float:
        return self.pixmap.width() * self.escala / 2

    def vai_para(self, estado, agora):
        self.estado = estado
        self.t_estado = agora

    def draw(self, p: QPainter):
        if self.alpha <= 0.01:
            return
        p.save()
        p.setOpacity(self.alpha)
        p.translate(self.pos)
        p.rotate(self.giro)
        p.scale(self.escala, self.escala)
        p.drawPixmap(-self.pixmap.width() // 2, -self.pixmap.height() // 2, self.pixmap)
        p.restore()


class Canvas(QWidget):
    """Tela inteira, transparente e transparente a cliques."""

    def __init__(self, desenhar):
        super().__init__(None, Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool
                         | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.desenhar = desenhar
        self.setGeometry(QApplication.primaryScreen().virtualGeometry())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.desenhar(p)
        p.end()


class CatchMode(QObject):
    """Regras do modo: aparição, arremesso, captura e comemoração."""

    pokemon_ready = pyqtSignal(int, bytes, bool)
    ball_ready = pyqtSignal(str, bytes)
    captured = pyqtSignal(str)

    def __init__(self, pointer, pokedex=None, parent=None):
        super().__init__(parent)
        self.pointer = pointer
        self.pokedex = pokedex if pokedex is not None else Pokedex()
        self.canvas = None
        self.wilds = []
        self.voando = []
        self.ball = None
        self.particulas = []
        self.banners = []
        self.capturados = 0
        self.carregando = False
        self.pressionado_em = QPointF(0, 0)
        self.proxima_bola = 0.0
        self.silencio_ate = 0.0
        self.primeira_bola = True
        self.iniciado = 0.0
        self.ativo = False
        self._ultimo = time.monotonic()
        self._sujo = QRegion()

        self.pokemon_ready.connect(self._nasce_pokemon)
        self.ball_ready.connect(self._nasce_bola)

        self.frame = QTimer(self)
        self.frame.timeout.connect(self.step)
        self.spawn = QTimer(self)
        self.spawn.setSingleShot(True)      # cada aparição reagenda a próxima
        self.spawn.timeout.connect(self.solta_pokemon)

    # ---------------- ciclo de vida ----------------
    def start(self):
        if self.ativo:
            return
        self.ativo = True
        self.iniciado = self._ultimo = time.monotonic()
        self.silencio_ate = 0.0
        self.primeira_bola = True
        self.canvas = Canvas(self.draw)
        self.canvas.show()
        self.pointer.watch_gesture = True
        self.pointer.gesture_pressed.connect(self._segurou)
        self.pointer.gesture_released.connect(self._soltou)
        self.frame.start(cfg.FRAME_MS)
        self._reagenda_spawn()
        self.solta_pokemon()
        self.pede_bola()
        self.proxima_bola = self.iniciado + 5.0   # o step não pede de novo junto

    def stop(self):
        if not self.ativo:
            return
        self.ativo = False
        self.frame.stop()
        self.spawn.stop()
        self.pointer.watch_gesture = False
        self.pointer.gesture_pressed.disconnect(self._segurou)
        self.pointer.gesture_released.disconnect(self._soltou)
        for w in self.wilds:
            w.sprite.stop()
        self.wilds.clear()
        self.voando.clear()
        self.particulas.clear()
        self.banners.clear()
        self.ball = None
        self.carregando = False
        if self.canvas is not None:
            self.canvas.close()
            self.canvas = None

    # ---------------- aparições ----------------
    def _reagenda_spawn(self):
        espera = random.uniform(cfg.SPAWN_MIN, cfg.SPAWN_MAX)
        # depois de uma captura a mata fica quieta, para dar expectativa
        espera = max(espera, self.silencio_ate - time.monotonic())
        self.spawn.start(int(espera * 1000))

    def solta_pokemon(self):
        self._reagenda_spawn()
        if not self.ativo or len(self.wilds) >= cfg.WILD_MAX:
            return
        if time.monotonic() < self.silencio_ate or self._em_captura():
            return

        def worker():
            pid = random.randint(1, cfg.MAX_ID)
            data, is_gif = sprites.fetch_pokemon(pid)
            if data:
                self.pokemon_ready.emit(pid, data, is_gif)
                # o nome vem depois de entregar o sprite, e aqui na thread de
                # fundo: na frente do emit, a aparição esperaria o timeout da
                # lista de nomes; na thread da interface, congelaria a captura
                sprites.prefetch_names()
        threading.Thread(target=worker, daemon=True).start()

    def _em_captura(self) -> bool:
        return any(b.estado in ("sugando", "balancando", "comemorando")
                   for b in self.voando)

    def _nasce_pokemon(self, pid, data, is_gif):
        if not self.ativo or len(self.wilds) >= cfg.WILD_MAX:
            return
        if time.monotonic() < self.silencio_ate:   # chegou atrasado, já no silêncio
            return
        sprite = sprites.Sprite(data, is_gif, target_h=cfg.WILD_HEIGHT)
        self.wilds.append(Wild(pid, sprite, self._lugar_livre(sprite)))

    def _lugar_livre(self, sprite) -> QPointF:
        """Sorteia um ponto numa tela real, tentando não empilhar sprites."""
        origem = self.canvas.geometry().topLeft()
        ponto = QPointF(0, 0)
        for _ in range(12):
            tela = random.choice(QApplication.screens()).geometry()
            mx = sprite.size.width() // 2 + 20
            my = sprite.size.height() // 2 + 20
            ponto = QPointF(
                random.uniform(tela.left() + mx, tela.right() - mx) - origem.x(),
                random.uniform(tela.top() + my, tela.bottom() - my) - origem.y())
            if all(math.hypot(ponto.x() - w.pos.x(), ponto.y() - w.pos.y()) > 160
                   for w in self.wilds):
                break
        return ponto

    # ---------------- pokébola ----------------
    def pede_bola(self):
        def worker():
            kind = sprites.random_ball()
            data = sprites.fetch_ball(kind)
            if data:
                self.ball_ready.emit(kind, data)
        threading.Thread(target=worker, daemon=True).start()

    def _nasce_bola(self, kind, data):
        if not self.ativo or self.ball is not None:
            return
        pix = QPixmap()
        pix.loadFromData(data)
        pix = pix.scaled(int(pix.width() * cfg.BALL_SCALE),
                         int(pix.height() * cfg.BALL_SCALE),
                         Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
        self.ball = Ball(kind, pix, self._cursor())
        self.ball.escala = 0.1          # cresce ao aparecer
        if self.primeira_bola:
            # a dica só faz sentido com bola na mão: sem rede, o relógio dela
            # venceria antes de existir o que arremessar
            self.primeira_bola = False
            self.iniciado = time.monotonic()

    def _cursor(self) -> QPointF:
        pos = self.pointer.pos
        origem = self.canvas.geometry().topLeft() if self.canvas else pos
        return QPointF(pos.x() - origem.x() + cfg.BALL_OFFSET[0],
                       pos.y() - origem.y() + cfg.BALL_OFFSET[1])

    def _segurou(self, pos):
        if self.ball is not None and self.ball.estado == "mao":
            self.carregando = True
            self.pressionado_em = self._cursor()

    def _soltou(self, pos):
        if not self.carregando or self.ball is None or self.ball.estado != "mao":
            self.carregando = False
            return
        self.carregando = False
        vx, vy = self.pointer.velocity()
        vel = math.hypot(vx, vy)
        if vel < cfg.THROW_SPEED_MIN:
            # gesto fraco: usa o trajeto desde que segurou, ou joga para cima
            destino = self._cursor() - self.pressionado_em
            d = math.hypot(destino.x(), destino.y())
            vx, vy = (destino.x() / d, destino.y() / d) if d > 8 else (0.0, -1.0)
            vel = cfg.THROW_SPEED_MIN
        else:
            vx, vy = vx / vel, vy / vel
            vel = min(vel, cfg.THROW_SPEED_MAX)

        bola = self.ball
        bola.vel = QPointF(vx * vel, vy * vel)
        bola.escala = 1.0
        bola.vai_para("voando", time.monotonic())
        self.voando.append(bola)
        self.ball = None
        self.proxima_bola = time.monotonic() + cfg.BALL_REDRAW_S

    # ---------------- quadro a quadro ----------------
    def step(self):
        agora = time.monotonic()
        dt = min(agora - self._ultimo, 0.05)
        self._ultimo = agora

        for w in self.wilds:
            w.step(agora, dt)
        self.wilds = [w for w in self.wilds if not w.morto()]

        self._step_bola_na_mao(agora, dt)
        for bola in list(self.voando):
            self._step_bola(bola, agora, dt)
        self.voando = [b for b in self.voando if b.estado != "fim"]

        for parte in self.particulas:
            parte["vel"] = QPointF(parte["vel"].x(), parte["vel"].y() + 520 * dt)
            parte["pos"] = parte["pos"] + parte["vel"] * dt
            parte["vida"] -= dt
        self.particulas = [p for p in self.particulas if p["vida"] > 0]
        self.banners = [b for b in self.banners
                        if agora - b["nascido"] < cfg.CELEBRATE_S]

        if self.ball is None and not self.carregando and agora >= self.proxima_bola:
            self.proxima_bola = agora + 5.0     # não pede de novo antes de chegar
            self.pede_bola()

        if self.canvas is not None:
            # a janela cobre a área de trabalho inteira: repintar tudo a cada
            # quadro custaria dezenas de MB de recomposição por segundo, então
            # só o que mudou (agora e no quadro anterior) é marcado como sujo
            regiao = self._regiao_suja()
            self.canvas.update(regiao.united(self._sujo))
            self._sujo = regiao

    def _regiao_suja(self) -> QRegion:
        regiao = QRegion()
        for w in self.wilds:
            regiao = regiao.united(w.rect().toRect().adjusted(-10, -10, 10, 10))
        for bola in self.voando:
            regiao = regiao.united(self._area_bola(bola))
            if bola.estado == "sugando" and bola.alvo is not None:
                feixe = QRectF(bola.pos, bola.alvo.pos).normalized()
                regiao = regiao.united(feixe.toRect().adjusted(-90, -90, 90, 90))
        if self.ball is not None:
            margem = 190 if self.carregando else 0
            regiao = regiao.united(self._area_bola(self.ball, margem))
        for parte in self.particulas:
            r = int(parte["r"]) + 2
            regiao = regiao.united(QRect(int(parte["pos"].x()) - r,
                                         int(parte["pos"].y()) - r, r * 2, r * 2))
        for b in self.banners:
            regiao = regiao.united(QRect(int(b["pos"].x()) - 500,
                                         int(b["pos"].y()) - 140, 1000, 160))
        return regiao.united(self._area_hud())

    @staticmethod
    def _area_bola(bola, margem=0) -> QRect:
        # a bola gira, então a caixa precisa caber na diagonal do sprite
        raio = bola.pixmap.width() * max(1.0, bola.escala) * 0.75 + 6 + margem
        return QRect(int(bola.pos.x() - raio), int(bola.pos.y() - raio),
                     int(raio * 2), int(raio * 2))

    def _area_hud(self) -> QRect:
        tela = QApplication.primaryScreen().geometry()
        origem = self.canvas.geometry().topLeft()
        # a altura acompanha as linhas de agora: uma linha fora da região suja
        # apareceria cortada, ou só quando outra coisa sujasse aquele pedaço
        linhas = len(self._linhas_hud(time.monotonic()))
        return QRect(tela.center().x() - origem.x() - 500,
                     tela.top() - origem.y() + 16, 1000, 24 + 38 * linhas)

    def _step_bola_na_mao(self, agora, dt):
        bola = self.ball
        if bola is None:
            return
        bola.escala = min(1.0, bola.escala + dt * 6)
        alvo = self._cursor()
        if self.carregando:
            # puxa a bola para trás do movimento, como quem toma impulso
            vx, vy = self.pointer.velocity()
            v = math.hypot(vx, vy)
            if v > 40:
                k = min(26.0, v / 45.0)
                alvo = alvo - QPointF(vx / v * k, vy / v * k)
            bola.giro += 220 * dt
        else:
            bola.giro *= 0.85
        bola.pos = bola.pos + (alvo - bola.pos) * min(1.0, dt * 22)

    def _step_bola(self, bola, agora, dt):
        if bola.estado == "voando":
            self._voa(bola, agora, dt)
        elif bola.estado == "sugando":
            self._suga(bola, agora)
        elif bola.estado == "balancando":
            self._balanca(bola, agora)
        elif bola.estado == "comemorando":
            p = (agora - bola.t_estado) / cfg.CELEBRATE_S
            bola.escala = 1.0 + max(0.0, 0.5 - p) * 0.8
            bola.alpha = max(0.0, 1.0 - p)
            if p >= 1.0:
                bola.vai_para("fim", agora)

    def _voa(self, bola, agora, dt):
        velocidade = math.hypot(bola.vel.x(), bola.vel.y())
        passos = min(8, int(velocidade * dt / 12) + 1)   # passo curto não atravessa o alvo
        for _ in range(passos):
            bola.pos = bola.pos + bola.vel * (dt / passos)
            bola.vel = QPointF(bola.vel.x(),
                               bola.vel.y() + cfg.GRAVITY * (dt / passos))
            alvo = self._acertou(bola)
            if alvo is not None:
                self._acerto(bola, alvo, agora)
                return
        bola.giro += cfg.BALL_SPIN * dt * (1 if bola.vel.x() >= 0 else -1)
        limites = self.canvas.rect().adjusted(-300, -300, 300, 300)
        if not limites.contains(bola.pos.toPoint()) or agora - bola.t_estado > cfg.MISS_TTL:
            bola.alpha -= dt * 3
            if bola.alpha <= 0:
                bola.vai_para("fim", agora)

    def _suga(self, bola, agora):
        p = min(1.0, (agora - bola.t_estado) / cfg.SUCK_S)
        alvo = bola.alvo
        alvo.escala = max(0.02, 1.0 - p)
        alvo.alpha = max(0.0, 1.0 - p * 0.9)
        alvo.pos = alvo.pos + (bola.pos - alvo.pos) * min(1.0, p * 0.5)
        if p >= 1.0:
            if alvo in self.wilds:
                alvo.sprite.stop()
                self.wilds.remove(alvo)
            bola.vai_para("balancando", agora)

    def _balanca(self, bola, agora):
        t = agora - bola.t_estado
        volta = int(t / cfg.WOBBLE_S)
        if volta >= cfg.WOBBLES:
            self._captura(bola, agora)
            return
        fase = (t % cfg.WOBBLE_S) / cfg.WOBBLE_S
        lado = 1 if volta % 2 == 0 else -1
        bola.giro = math.sin(fase * math.pi) * 20 * lado

    def _acertou(self, bola):
        for w in self.wilds:
            if w.estado != "livre":
                continue
            r = w.hit_rect()
            cx = max(r.left(), min(bola.pos.x(), r.right()))
            cy = max(r.top(), min(bola.pos.y(), r.bottom()))
            if math.hypot(bola.pos.x() - cx, bola.pos.y() - cy) <= bola.raio:
                return w
        return None

    def _acerto(self, bola, alvo, agora):
        alvo.estado = "sugado"
        alvo.t_estado = agora
        bola.alvo = alvo
        bola.vel = QPointF(0, 0)
        bola.giro = 0.0
        bola.vai_para("sugando", agora)

    def _captura(self, bola, agora):
        pid = bola.alvo.pid
        nome = sprites.pokemon_name(pid)
        novo = self.pokedex.registrar(pid, nome)
        self.capturados += 1
        self.silencio_ate = agora + random.uniform(cfg.PAUSE_MIN, cfg.PAUSE_MAX)
        self._reagenda_spawn()
        bola.giro = 0.0
        bola.vai_para("comemorando", agora)
        for _ in range(cfg.PARTICLES):
            ang = random.uniform(0, math.tau)
            v = random.uniform(120, 420)
            self.particulas.append({
                "pos": QPointF(bola.pos), "vida": random.uniform(0.5, 1.1),
                "vel": QPointF(math.cos(ang) * v, math.sin(ang) * v - 160),
                "cor": random.choice(FAISCA), "r": random.uniform(2.5, 5.5)})
        texto = (f"Gotcha! {nome} é novo na Pokédex!" if novo
                 else f"Gotcha! {nome} foi capturado!")
        self.banners.append({"texto": texto, "pos": QPointF(bola.pos),
                             "nascido": agora})
        self.captured.emit(nome)

    # ---------------- desenho ----------------
    def draw(self, p: QPainter):
        agora = time.monotonic()
        for w in self.wilds:
            w.draw(p)
        for bola in self.voando:
            if bola.estado == "sugando" and bola.alvo is not None:
                self._raio(p, bola, agora)
            bola.draw(p)
        if self.ball is not None:
            if self.carregando:
                self._mira(p)
            self.ball.draw(p)
        p.setPen(Qt.PenStyle.NoPen)
        for parte in self.particulas:
            cor = QColor(parte["cor"])
            cor.setAlphaF(max(0.0, min(1.0, parte["vida"])))
            p.setBrush(cor)
            p.drawEllipse(parte["pos"], parte["r"], parte["r"])
        for b in self.banners:
            self._banner(p, b, agora)
        self._hud(p, agora)

    def _raio(self, p: QPainter, bola, agora):
        """Facho de luz entre a bola e o Pokémon sendo sugado."""
        p.setPen(QPen(QColor(255, 240, 160, 150), 6, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawLine(bola.pos, bola.alvo.pos)
        t = min(1.0, (agora - bola.t_estado) / cfg.SUCK_S)
        raio = 10 + t * 70
        p.setPen(QPen(QColor(255, 255, 255, int(160 * (1 - t))), 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(bola.pos, raio, raio)

    def _mira(self, p: QPainter):
        """Setinha mostrando para onde a bola vai sair."""
        vx, vy = self.pointer.velocity()
        v = math.hypot(vx, vy)
        if v < 60:
            return
        forca = min(1.0, v / cfg.THROW_SPEED_MAX)
        ini = self.ball.pos
        fim = ini + QPointF(vx / v, vy / v) * (40 + forca * 120)
        p.setPen(QPen(QColor(255, 255, 255, 170), 3, Qt.PenStyle.DashLine))
        p.drawLine(ini, fim)

    def _banner(self, p: QPainter, b, agora):
        t = (agora - b["nascido"]) / cfg.CELEBRATE_S
        alpha = int(255 * max(0.0, min(1.0, (1 - t) * 2.2)))
        p.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        texto = b["texto"]
        largura = p.fontMetrics().horizontalAdvance(texto) + 36
        caixa = QRectF(b["pos"].x() - largura / 2,
                       b["pos"].y() - 70 - t * 50, largura, 46)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(20, 22, 30, int(alpha * 0.82)))
        p.drawRoundedRect(caixa, 23, 23)
        p.setPen(QColor(255, 255, 255, alpha))
        p.drawText(caixa, Qt.AlignmentFlag.AlignCenter, texto)

    def _linhas_hud(self, agora):
        linhas = [f"Capturados: {self.capturados}  ·  "
                  f"Pokédex: {self.pokedex.especies}/{cfg.MAX_ID}"]
        if sprites.falhas.recente():
            # sem este aviso o modo fica mudo: nada aparece na tela e nada
            # explica o motivo, então parece que o programa travou
            linhas.append(f"Não consegui baixar {sprites.falhas.assunto}: "
                          f"{sprites.falhas.motivo}. Tentando de novo...")
        elif agora - self.iniciado < cfg.HUD_HINT_S:
            linhas.append(f"Segure {cfg.GESTO_NOME} e arremesse na direção do "
                          f"Pokémon  ·  Esc sai do modo")
        elif agora < self.silencio_ate and not self.wilds:
            # a espera precisa parecer proposital, não travamento
            pontos = "." * (1 + int(agora * 2) % 3)
            linhas.append("Procurando o próximo Pokémon" + pontos)
        return linhas

    def _hud(self, p: QPainter, agora):
        tela = QApplication.primaryScreen().geometry()
        origem = self.canvas.geometry().topLeft()
        cx = tela.center().x() - origem.x()
        topo = tela.top() - origem.y() + 24

        linhas = self._linhas_hud(agora)
        p.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        for i, linha in enumerate(linhas):
            largura = p.fontMetrics().horizontalAdvance(linha) + 28
            caixa = QRectF(cx - largura / 2, topo + i * 38, largura, 32)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(20, 22, 30, 190))
            p.drawRoundedRect(caixa, 16, 16)
            p.setPen(BRANCO)
            p.drawText(caixa, Qt.AlignmentFlag.AlignCenter, linha)
