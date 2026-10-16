"""Modo Agitada: detecção da sacudida e a janelinha do sprite."""
import time

from pokeshake import config as cfg
from pokeshake.shake import ShakeDetector, ShakeMode, SpritePopup


def zigue_zague(detector, passos=10, trecho=12, varreduras=6, x=500):
    for v in range(varreduras):
        for _ in range(passos):
            x += trecho if v % 2 == 0 else -trecho
            detector.on_move(x, 400)
            time.sleep(0.004)
    return x


def test_zigue_zague_dispara_uma_vez():
    disparos = []
    detector = ShakeDetector(lambda x, y: disparos.append((x, y)))
    zigue_zague(detector)
    assert len(disparos) == 1


def test_movimento_reto_nao_dispara():
    """O caso que importa: usar o computador normalmente não invoca Pokémon."""
    disparos = []
    detector = ShakeDetector(lambda x, y: disparos.append(1))
    for i in range(60):
        detector.on_move(500 + i * 5, 400)
        time.sleep(0.004)
    assert not disparos


def test_tremida_curta_nao_dispara():
    """Zigue-zague de amplitude pequena (mão trêmula) fica abaixo do limiar."""
    disparos = []
    detector = ShakeDetector(lambda x, y: disparos.append(1))
    x = 500
    for v in range(8):
        for _ in range(4):
            x += 5 if v % 2 == 0 else -5
            detector.on_move(x, 400)
            time.sleep(0.004)
    assert not disparos


def test_cooldown_segura_o_segundo_disparo():
    disparos = []
    detector = ShakeDetector(lambda x, y: disparos.append(1))
    x = zigue_zague(detector)
    zigue_zague(detector, x=x)
    assert len(disparos) == 1, "duas agitadas coladas não podem virar dois Pokémon"


def test_movimento_lento_nao_dispara():
    """A mesma trajetória, devagar, sai da janela de tempo e não conta."""
    disparos = []
    detector = ShakeDetector(lambda x, y: disparos.append(1))
    x = 500
    for v in range(6):
        for _ in range(4):
            x += 60 if v % 2 == 0 else -60
            detector.on_move(x, 400)
            time.sleep(0.05)
    assert not disparos


def test_popup_desenha_o_sprite(app, pikachu, processa):
    data, is_gif = pikachu
    janela = SpritePopup(data, is_gif, 600, 400)
    processa(0.1)
    imagem = janela.grab().toImage()
    visiveis = sum(1 for x in range(0, imagem.width(), 4)
                   for y in range(0, imagem.height(), 4)
                   if imagem.pixelColor(x, y).alpha() > 0)
    assert janela.width() > 20 and janela.height() > 20
    assert visiveis > 20, "a janela apareceu vazia"
    janela.close()
    processa(0.1)


def cantos_dos_monitores():
    """Os quatro cantos de cada monitor ligado."""
    from PyQt6.QtWidgets import QApplication
    for tela in QApplication.screens():
        area = tela.availableGeometry()
        for x, y in [(area.left(), area.top()), (area.right(), area.top()),
                     (area.left(), area.bottom()), (area.right(), area.bottom())]:
            yield tela.name(), x, y


def test_popup_nasce_dentro_de_algum_monitor(app, pikachu, processa):
    """Sacudir num canto não pode fazer o sprite nascer fora das telas.

    A conta é contra o monitor que contém o ponto, não contra o principal: com
    monitor à esquerda, o canto esquerdo do principal cai na tela vizinha.
    Vale só para a posição inicial — depois a animação sobe e desliza de
    propósito.
    """
    from PyQt6.QtCore import QRect
    from PyQt6.QtWidgets import QApplication
    data, is_gif = pikachu
    areas = [t.availableGeometry() for t in QApplication.screens()]
    for nome, x, y in cantos_dos_monitores():
        janela = SpritePopup(data, is_gif, x, y)
        caixa = QRect(janela.x(), janela.y(), janela.width(), janela.height())
        assert any(area.contains(caixa) for area in areas),             f"sprite invocado em ({x},{y}) de {nome} nasceu em {caixa}"
        janela.close()
        processa(0.05)


def test_popup_some_sozinho(app, pikachu, espera, processa):
    data, is_gif = pikachu
    janela = SpritePopup(data, is_gif, 600, 400)
    vivo = {"sim": True}
    janela.destroyed.connect(lambda: vivo.update(sim=False))
    assert espera(lambda: not vivo["sim"], limite=cfg.SHAKE_DISPLAY_MS / 1000 + 4)


def test_modo_liga_e_desliga(app, pointer, entrada, processa):
    modo = ShakeMode(pointer)
    assert not modo.ativo
    modo.start()
    assert modo.ativo
    modo.stop()
    assert not modo.ativo
    modo.start()                    # ligar duas vezes não pode duplicar a ligação
    modo.start()
    modo.stop()
    assert not modo.ativo


def test_modo_reage_ao_movimento_do_cursor(app, pointer, entrada, processa):
    modo = ShakeMode(pointer)
    modo.start()
    disparos = []
    modo.detector.on_shake = lambda x, y: disparos.append(1)
    x = 500
    for v in range(6):
        for _ in range(4):
            x += 60 if v % 2 == 0 else -60
            entrada.mover(x, 400)
            processa(0.016)
    modo.stop()
    assert disparos, "a agitada do cursor precisa chegar ao detector"


def test_modo_baixa_e_mostra_o_pokemon(app, pointer, entrada, espera):
    modo = ShakeMode(pointer)
    modo.start()
    modo.summon_at_cursor()
    assert espera(lambda: len(modo.popups) == 1)
    modo.stop()
    assert not modo.ativo
