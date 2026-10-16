"""Dry run: exercita o aplicativo inteiro sozinho e diz se passou.

Roda dentro do processo de verdade (mesma `main`, mesma bandeja, mesmo menu,
mesmo event loop), trocando só a leitura do dispositivo por um roteiro. Assim
nada é feito com o mouse da máquina e o resultado vira código de saída, o que
deixa o dry run utilizável tanto na mão quanto dentro dos testes.

    python pokeshake_init.py --dry-run
"""
import time

from PyQt6.QtCore import QObject, QPoint, QTimer

from . import config as cfg
from . import pointer as ptr
from . import sprites
from .catch import Wild
from PyQt6.QtCore import QPointF


class EntradaVirtual:
    """Cursor e botão roteirizados no lugar da leitura do dispositivo."""

    def __init__(self, pos=QPoint(400, 400)):
        self.pos = QPoint(pos)
        self.segurando = False
        self._cursor_real = None
        self._botao_real = None

    def instalar(self):
        self._cursor_real = ptr.ler_cursor
        self._botao_real = ptr.pressionado
        ptr.ler_cursor = lambda: QPoint(self.pos)
        ptr.pressionado = lambda vk: self.segurando if vk == ptr.VK[cfg.THROW_GESTURE] else False

    def restaurar(self):
        if self._cursor_real is not None:
            ptr.ler_cursor = self._cursor_real
            ptr.pressionado = self._botao_real

    def mover(self, x, y):
        self.pos = QPoint(int(x), int(y))


class DryRun(QObject):
    """Executa os passos em ordem, cada um com seu tempo de espera."""

    def __init__(self, app, poke, parent=None):
        super().__init__(parent)
        self.app = app
        self.poke = poke
        self.entrada = EntradaVirtual()
        self.codigo = 0
        self.resultados = []
        self.passos = []
        self.voo = None
        self.i = 0
        self._t0 = 0.0

    # ---------------- infraestrutura ----------------
    def start(self):
        self.entrada.instalar()
        tela = self.app.primaryScreen().geometry()
        self.centro = tela.center()
        self.entrada.mover(self.centro.x() - 400, self.centro.y())
        self.passos = self._roteiro()
        self._t0 = time.monotonic()
        print(f"dry run: {len(self.passos)} passos\n")
        QTimer.singleShot(300, self._proximo)

    def _proximo(self):
        if self.i >= len(self.passos):
            return self._fim()
        nome, acao, espera = self.passos[self.i]
        self.i += 1
        try:
            erro = acao()
        except Exception as exc:                     # o passo não pode derrubar o dry run
            erro = f"{type(exc).__name__}: {exc}"
        self._anota(nome, erro)
        QTimer.singleShot(int(espera * 1000), self._proximo)

    def _anota(self, nome, erro):
        ok = not erro
        self.resultados.append((nome, erro))
        if not ok:
            self.codigo = 1
        print(f"  {'ok  ' if ok else 'FALHA'}  {nome}" + ("" if ok else f"\n         {erro}"))

    def _fim(self):
        falhas = [n for n, e in self.resultados if e]
        dur = time.monotonic() - self._t0
        print(f"\ndry run: {len(self.resultados) - len(falhas)}/{len(self.resultados)} "
              f"passos em {dur:.1f}s")
        if falhas:
            print("falhou em: " + ", ".join(falhas))
        self.entrada.restaurar()
        self.app.quit()

    # ---------------- ajudantes ----------------
    def _agita(self):
        """Zigue-zague pelo cursor virtual, como uma agitada de verdade."""
        x, y = self.centro.x(), self.centro.y()
        caminho = []
        for varredura in range(8):
            for _ in range(3):
                x += 80 if varredura % 2 == 0 else -80
                caminho.append((x, y))
        self._caminho(caminho)

    def _caminho(self, pontos, ao_terminar=None):
        """Anda o cursor virtual um ponto por leitura do Pointer.

        Marcar os pontos no relógio parecia mais simples, mas sob carga os
        timers se atropelam: o roteiro inteiro cai numa única leitura, o gesto
        sai sem velocidade nenhuma e o arremesso vira um falso negativo.
        """
        fila = list(pontos)
        timer = self.poke.pointer.timer

        def passo():
            if fila:
                x, y = fila.pop(0)
                self.entrada.mover(x, y)
                return
            timer.timeout.disconnect(passo)
            if ao_terminar is not None:
                ao_terminar()

        timer.timeout.connect(passo)

    def _planta_alvo(self):
        """Põe um Pokémon num lugar conhecido, para o arremesso ter alvo certo."""
        catch = self.poke.catch
        data, is_gif = sprites.fetch_pokemon(25)
        if not data:
            return None
        origem = catch.canvas.geometry().topLeft()
        sprite = sprites.Sprite(data, is_gif, target_h=cfg.WILD_HEIGHT)
        alvo = Wild(25, sprite, QPointF(self.centro.x() + 450 - origem.x(),
                                        self.centro.y() - origem.y()))
        catch.wilds.append(alvo)
        return alvo

    # ---------------- roteiro ----------------
    def _roteiro(self):
        poke, catch, shake = self.poke, self.poke.catch, self.poke.shake

        def comeca_pausado():
            if poke.modo != "off":
                return f"modo inicial é {poke.modo!r}"
            if not poke.tray.isVisible():
                return "ícone da bandeja não apareceu"
            if not poke.menu.isVisible():
                return "menu não abriu sozinho"

        def escolhe_agitada():
            poke.menu.botoes["shake"].click()
            if poke.modo != "shake" or not shake.ativo:
                return f"modo ficou {poke.modo!r}"
            if catch.ativo:
                return "modo caçada continuou ligado"

        def agita():
            self._agita()

        def confere_sprite():
            if not shake.popups:
                return "nenhum Pokémon apareceu depois da agitada"
            janela = shake.popups[0]
            if janela.width() < 20 or janela.height() < 20:
                return f"janela pequena demais: {janela.width()}x{janela.height()}"

        def escolhe_cacada():
            poke.menu.botoes["catch"].click()
            if poke.modo != "catch" or not catch.ativo:
                return f"modo ficou {poke.modo!r}"
            if shake.ativo:
                return "modo agitada continuou ligado"
            if catch.canvas is None or not catch.canvas.isVisible():
                return "tela da caçada não apareceu"
            if not poke.pointer.watch_gesture:
                return "gesto de arremesso não está sendo lido"

        def confere_limpeza():
            # as janelas do modo anterior somem quando o Qt processa o destroyed
            if shake.popups:
                return f"{len(shake.popups)} sprites da agitada continuam na tela"

        def confere_selvagem():
            if not catch.wilds:
                return "nenhum Pokémon selvagem apareceu"
            if catch.ball is None:
                return "pokébola não apareceu na mão"

        def prepara_arremesso():
            catch.spawn.stop()                  # o alvo do arremesso é plantado
            for w in catch.wilds:               # a aparição sorteada já foi conferida
                w.sprite.stop()
            catch.wilds.clear()
            self.alvo = self._planta_alvo()
            if self.alvo is None:
                return "não consegui baixar o sprite do alvo"
            self.entrada.mover(self.centro.x() - 450, self.centro.y() + 20)
            self.capturas = []
            catch.captured.connect(self.capturas.append)

        def arremessa():
            if catch.ball is None:
                return "sem pokébola na mão para arremessar"
            self.entrada.segurando = True
            x, y = self.centro.x() - 450, self.centro.y() + 20
            self._caminho([(x + 42 * (i + 1), y) for i in range(11)],
                          ao_terminar=self._solta)

        def confere_voo():
            if self.voo is None:
                return "nenhuma pokébola saiu da mão"
            quantas, vx, vy = self.voo
            if quantas != 1:
                return f"{quantas} bolas no ar, esperava 1"
            if vx < 300:
                return f"bola não foi para a direita: {vx:.0f} px/s"

        def confere_captura():
            if not self.capturas:
                return "a bola acertou mas nada foi capturado"
            if catch.capturados < 1:
                return "contador de capturas não subiu"
            if self.alvo in catch.wilds:
                return "Pokémon capturado continua na tela"

        def confere_intervalo():
            falta = catch.silencio_ate - time.monotonic()
            if falta <= 0:
                return "nenhum intervalo foi aberto depois da captura"
            if falta > cfg.PAUSE_MAX + 1:
                return f"intervalo longo demais: {falta:.1f}s"
            agendado = catch.spawn.remainingTime() / 1000
            if agendado < falta - 0.5:
                return f"próxima aparição ({agendado:.1f}s) cai dentro do intervalo"
            self.wilds_no_intervalo = len(catch.wilds)

        def confere_silencio():
            if len(catch.wilds) > self.wilds_no_intervalo:
                return "apareceu Pokémon novo durante o intervalo"
            if not catch.wilds and not any("Procurando" in l
                                           for l in catch._linhas_hud(time.monotonic())):
                return "HUD não avisou que está procurando"

        def sai_com_esc():
            poke.pointer.escape_pressed.emit()
            if poke.modo != "off":
                return f"Esc não pausou: modo {poke.modo!r}"
            if catch.canvas is not None:
                return "tela da caçada continuou aberta"
            if poke.pointer.watch_gesture:
                return "continuou lendo o gesto"

        return [
            ("aplicativo sobe pausado, com bandeja e menu", comeca_pausado, 0.2),
            ("menu liga o modo Agitada", escolhe_agitada, 0.2),
            ("agitada do mouse", agita, 1.8),
            ("Pokémon aparece na agitada", confere_sprite, 0.3),
            ("menu troca para o modo Caçada", escolhe_cacada, 0.5),
            ("sprites da agitada saíram da tela", confere_limpeza, 2.5),
            ("Pokémon selvagem e pokébola na mão", confere_selvagem, 0.2),
            ("alvo posicionado para o arremesso", prepara_arremesso, 0.4),
            ("arremesso com o gesto", arremessa, 0.8),
            ("pokébola voando na direção certa", confere_voo, 5.0),
            ("captura confirmada", confere_captura, 0.2),
            ("intervalo de expectativa aberto", confere_intervalo, 2.5),
            ("nada aparece durante o intervalo", confere_silencio, 0.2),
            ("Esc volta para pausado", sai_com_esc, 0.2),
        ]

    def _solta(self):
        self.entrada.segurando = False
        # a velocidade precisa ser lida em pleno voo: ao acertar, o impacto zera
        QTimer.singleShot(30, self._registra_voo)

    def _registra_voo(self):
        bolas = self.poke.catch.voando
        self.voo = (len(bolas), bolas[0].vel.x(), bolas[0].vel.y()) if bolas else None
