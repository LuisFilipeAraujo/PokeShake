"""Leitura do cursor e do gesto de arremesso."""
import ctypes
import os
import sys

import pytest
from PyQt6.QtCore import QPoint

from pokeshake import config as cfg
from pokeshake import pointer as ptr


def test_gesto_configurado_vira_a_tecla_certa(pointer):
    assert cfg.THROW_GESTURE in ptr.VK
    assert pointer.vk == ptr.VK[cfg.THROW_GESTURE]


def test_gesto_tem_nome_legivel():
    """O HUD e o menu mostram esse texto; 'MIDDLE' não diria nada a ninguém."""
    assert cfg.GESTO_NOME == cfg.GESTO_NOMES[cfg.THROW_GESTURE]
    assert cfg.GESTO_NOME.strip()


def test_cursor_vem_da_costura(pointer, entrada, processa):
    entrada.mover(742, 318)
    processa(0.1)
    assert pointer.pos == QPoint(742, 318)


def test_movimento_emite_sinal(pointer, entrada, processa):
    vistos = []
    pointer.moved.connect(lambda p: vistos.append(p))
    entrada.mover(100, 100)
    processa(0.1)
    entrada.mover(200, 100)
    processa(0.1)
    assert [p.x() for p in vistos][-2:] == [100, 200]


def test_parado_nao_emite_movimento(pointer, entrada, processa):
    entrada.mover(500, 500)
    processa(0.1)
    vistos = []
    pointer.moved.connect(lambda p: vistos.append(p))
    processa(0.2)
    assert not vistos


def test_velocidade_acompanha_o_gesto(pointer, entrada, processa):
    entrada.mover(300, 400)
    processa(0.05)
    for i in range(10):
        entrada.mover(300 + (i + 1) * 40, 400)
        processa(0.016)
    vx, vy = pointer.velocity()
    assert vx > 800, f"esperava movimento rápido para a direita, veio {vx:.0f} px/s"
    assert abs(vy) < 200


def test_velocidade_zera_quando_para(pointer, entrada, processa):
    entrada.mover(400, 400)
    processa(0.4)
    vx, vy = pointer.velocity()
    assert (vx, vy) == (0.0, 0.0)


def test_gesto_so_e_lido_quando_o_modo_pede(pointer, entrada, processa):
    eventos = []
    pointer.gesture_pressed.connect(lambda p: eventos.append("segurou"))
    entrada.segurando = True
    processa(0.15)
    assert not eventos, "sem modo caçada ligado, o botão não deve ser consultado"

    pointer.watch_gesture = True
    processa(0.15)
    assert eventos == ["segurou"]


def test_gesto_emite_apenas_nas_bordas(pointer, entrada, processa):
    eventos = []
    pointer.watch_gesture = True
    pointer.gesture_pressed.connect(lambda p: eventos.append("segurou"))
    pointer.gesture_released.connect(lambda p: eventos.append("soltou"))
    entrada.segurando = True
    processa(0.2)
    entrada.segurando = False
    processa(0.2)
    assert eventos == ["segurou", "soltou"]


@pytest.mark.skipif(sys.platform != "win32", reason="leitura de tecla é do Windows")
def test_leitura_real_nao_ve_botao_solto():
    assert not ptr.pressionado(ptr.VK["middle"])
    assert not ptr.pressionado(ptr.VK_ESCAPE)


@pytest.mark.skipif(os.environ.get("POKESHAKE_TEST_INPUT") != "1",
                    reason="mexe no dispositivo de verdade; rode com POKESHAKE_TEST_INPUT=1")
def test_clique_real_da_roda_e_percebido(app, entrada, pointer, processa):
    """Injeta um clique de verdade, com o cursor sobre a janela do próprio
    PokeShake, para o evento não vazar para os programas do usuário."""
    from PyQt6.QtGui import QCursor
    from pokeshake.menu import OverlayMenu

    entrada.restaurar()          # este é o único teste que quer o dispositivo
    menu = OverlayMenu()
    menu.aparecer()
    processa(0.4)
    origem = QCursor.pos()
    QCursor.setPos(menu.geometry().center())
    processa(0.2)
    assert app.widgetAt(QCursor.pos()) is not None, "cursor não está sobre o PokeShake"

    eventos = []
    pointer.watch_gesture = True
    pointer.gesture_pressed.connect(lambda p: eventos.append("segurou"))
    pointer.gesture_released.connect(lambda p: eventos.append("soltou"))
    u32 = ctypes.windll.user32
    try:
        u32.mouse_event(0x0020, 0, 0, 0, 0)      # MOUSEEVENTF_MIDDLEDOWN
        processa(0.15)
    finally:
        u32.mouse_event(0x0040, 0, 0, 0, 0)      # MOUSEEVENTF_MIDDLEUP
    processa(0.15)
    QCursor.setPos(origem)
    menu.hide()
    assert eventos == ["segurou", "soltou"]
    assert not ptr.pressionado(ptr.VK["middle"]), "botão ficou preso"
