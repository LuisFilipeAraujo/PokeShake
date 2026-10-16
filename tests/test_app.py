"""Bandeja, menu overlay e a troca de modos."""
import pytest
from PyQt6.QtWidgets import QApplication

from pokeshake.app import PokeShake
from pokeshake.menu import MODOS, OverlayMenu, pokeball_icon


@pytest.fixture
def poke(app, entrada):
    p = PokeShake(app)
    yield p
    p.cleanup()
    p.menu.close()
    p.tray.hide()


def test_sobe_pausado(poke):
    assert poke.modo == "off"
    assert not poke.shake.ativo and not poke.catch.ativo
    assert poke.tray.isVisible()


def test_bandeja_lista_os_modos(poke):
    itens = [a.text() for a in poke.tray.contextMenu().actions() if a.text()]
    assert itens == ["Modo Agitada", "Modo Caçada", "Pausado", "Abrir menu", "Sair"]


def test_menu_tem_os_tres_modos(poke, processa):
    poke.menu.aparecer()
    processa(0.2)
    assert poke.menu.isVisible()
    assert list(poke.menu.botoes) == [chave for chave, _, _ in MODOS]


def test_menu_aparece_dentro_da_tela(poke, processa):
    poke.menu.aparecer()
    processa(0.2)
    tela = QApplication.primaryScreen().availableGeometry()
    assert tela.contains(poke.menu.geometry())


def test_botao_do_menu_liga_a_agitada(poke, processa):
    poke.menu.botoes["shake"].click()
    processa(0.1)
    assert poke.modo == "shake"
    assert poke.shake.ativo and not poke.catch.ativo


def test_botao_do_menu_liga_a_cacada(poke, processa):
    poke.menu.botoes["catch"].click()
    processa(0.3)
    assert poke.modo == "catch"
    assert poke.catch.ativo and poke.catch.canvas is not None
    assert poke.pointer.watch_gesture


def test_so_um_modo_por_vez(poke, processa):
    poke.menu.botoes["shake"].click()
    processa(0.1)
    poke.menu.botoes["catch"].click()
    processa(0.3)
    assert poke.catch.ativo and not poke.shake.ativo
    poke.menu.botoes["shake"].click()
    processa(0.3)
    assert poke.shake.ativo and not poke.catch.ativo
    assert poke.catch.canvas is None


def test_sprites_do_modo_anterior_saem_da_tela(poke, espera, processa):
    poke.set_modo("shake")
    poke.shake.summon_at_cursor()
    assert espera(lambda: len(poke.shake.popups) == 1)
    poke.set_modo("catch")
    processa(0.3)
    assert not poke.shake.popups


def test_modo_ativo_fica_marcado(poke, processa):
    poke.menu.botoes["catch"].click()
    processa(0.1)
    assert poke.menu.botoes["catch"].property("ativo") == "true"
    assert poke.menu.botoes["shake"].property("ativo") == "false"
    assert poke.acoes["catch"].isChecked()
    assert not poke.acoes["off"].isChecked()


def test_dica_do_menu_acompanha_o_modo(poke):
    poke.menu.marcar("catch")
    assert poke.menu.dica.text() == next(d for c, _, d in MODOS if c == "catch")


def test_esc_volta_para_pausado(poke, processa):
    poke.set_modo("catch")
    processa(0.3)
    poke.pointer.escape_pressed.emit()
    processa(0.2)
    assert poke.modo == "off"
    assert poke.catch.canvas is None
    assert not poke.pointer.watch_gesture


def test_modo_desconhecido_cai_para_pausado(poke):
    poke.set_modo("modo-que-nao-existe")
    assert poke.modo == "off"


def test_trocar_para_o_mesmo_modo_nao_reinicia(poke, processa):
    poke.set_modo("catch")
    processa(0.3)
    canvas = poke.catch.canvas
    poke.set_modo("catch")
    assert poke.catch.canvas is canvas


def test_captura_aparece_na_dica_da_bandeja(poke, processa):
    poke.set_modo("catch")
    processa(0.2)
    poke.catch.capturados = 3
    poke.catch.captured.emit("Snorlax")
    processa(0.1)
    assert "Snorlax" in poke.tray.toolTip()


def test_limpeza_desliga_tudo(poke, processa):
    poke.set_modo("catch")
    processa(0.3)
    poke.cleanup()
    assert not poke.catch.ativo and not poke.shake.ativo
    assert not poke.menu.isVisible()


def test_icone_da_bandeja_tem_desenho(app):
    icone = pokeball_icon(32)
    assert not icone.isNull()
    assert not icone.pixmap(32, 32).isNull()


def test_menu_pode_ser_arrastado(app, processa):
    menu = OverlayMenu()
    menu.aparecer()
    processa(0.2)
    antes = menu.pos()
    menu.move(antes.x() + 40, antes.y() + 30)
    assert menu.pos() != antes
    menu.close()


def test_modo_da_linha_de_comando(app):
    from pokeshake.app import modo_pedido
    assert modo_pedido(["prog"]) == "off"
    assert modo_pedido(["prog", "--mode", "catch"]) == "catch"
    assert modo_pedido(["prog", "--demo"]) == "shake"


def test_mode_sem_valor_nao_derruba_o_app(app):
    """Um `--mode` solto no fim da linha estourava o índice e matava o app."""
    from pokeshake.app import modo_pedido
    assert modo_pedido(["prog", "--mode"]) == "off"


def test_menu_pode_ter_o_fechar_escondido(app, processa):
    """Sem bandeja para reabrir, o menu não pode ser fechado."""
    menu = OverlayMenu()
    menu.aparecer()
    processa(0.2)
    assert menu.botao_fechar.isVisible()
    menu.permitir_fechar(False)
    assert not menu.botao_fechar.isVisible()
    menu.close()
