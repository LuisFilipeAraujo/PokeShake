"""Pokédex: o registro em disco, a integração com a caçada e a tela.

É o progresso do usuário: perder ou corromper aqui custa mais que um sprite que
não apareceu.
"""
import json
import time

from PyQt6.QtWidgets import QLabel

from pokeshake import config as cfg
from pokeshake import sprites
from pokeshake.menu import PokedexPanel
from pokeshake.pokedex import Pokedex


# ---------------- registro em disco ----------------

def test_registra_e_sobrevive_ao_fechamento(tmp_path):
    """O ponto da etapa: o contador zerava a cada execução."""
    caminho = tmp_path / "pokedex.json"
    Pokedex(caminho=caminho).registrar(25, "Pikachu")

    outra_sessao = Pokedex(caminho=caminho)
    assert outra_sessao.tem(25)
    assert outra_sessao.lista()[0]["nome"] == "Pikachu"


def test_primeira_captura_e_nova_a_segunda_nao(pokedex):
    assert pokedex.registrar(25, "Pikachu") is True
    assert pokedex.registrar(25, "Pikachu") is False


def test_repetida_soma_as_vezes(pokedex):
    for _ in range(3):
        pokedex.registrar(25, "Pikachu")
    assert pokedex.vezes(25) == 3
    assert pokedex.especies == 1
    assert pokedex.total == 3


def test_especies_e_total_contam_coisas_diferentes(pokedex):
    pokedex.registrar(25, "Pikachu")
    pokedex.registrar(25, "Pikachu")
    pokedex.registrar(6, "Charizard")
    assert pokedex.especies == 2
    assert pokedex.total == 3


def test_lista_vem_em_ordem_de_pokedex(pokedex):
    for pid, nome in [(25, "Pikachu"), (1, "Bulbasaur"), (150, "Mewtwo")]:
        pokedex.registrar(pid, nome)
    assert [i["pid"] for i in pokedex.lista()] == [1, 25, 150]


def test_nome_real_substitui_o_reserva(pokedex):
    """Capturar offline grava "Pokémon #25"; quando o nome chega, ele entra."""
    pokedex.registrar(25, "Pokémon #25")
    pokedex.registrar(25, "Pikachu")
    assert pokedex.lista()[0]["nome"] == "Pikachu"


def test_reserva_nao_apaga_o_nome_real(pokedex):
    pokedex.registrar(25, "Pikachu")
    pokedex.registrar(25, "Pokémon #25")
    assert pokedex.lista()[0]["nome"] == "Pikachu"


def test_guarda_quando_foi_a_captura(pokedex):
    pokedex.registrar(25, "Pikachu")
    registro = pokedex.lista()[0]
    assert registro["primeira"][:4].isdigit()
    assert registro["ultima"] >= registro["primeira"]


# ---------------- arquivo estragado ----------------

def test_arquivo_corrompido_nao_derruba_e_fica_guardado(tmp_path):
    """Começar limpo é aceitável; apagar o progresso do usuário sem deixar
    cópia não é."""
    caminho = tmp_path / "pokedex.json"
    caminho.write_text("{isso nao e json", encoding="utf-8")

    dex = Pokedex(caminho=caminho)
    assert dex.especies == 0
    assert (tmp_path / "pokedex.json.quebrado").exists()


def test_formato_inesperado_tambem_e_guardado(tmp_path):
    caminho = tmp_path / "pokedex.json"
    caminho.write_text(json.dumps({"versao": 1, "capturas": []}), encoding="utf-8")

    dex = Pokedex(caminho=caminho)
    assert dex.especies == 0
    assert (tmp_path / "pokedex.json.quebrado").exists()


def test_arquivo_sem_capturas_e_tolerado(tmp_path):
    caminho = tmp_path / "pokedex.json"
    caminho.write_text(json.dumps({"versao": 1}), encoding="utf-8")
    assert Pokedex(caminho=caminho).especies == 0


def test_entrada_estranha_no_arquivo_e_ignorada(tmp_path):
    caminho = tmp_path / "pokedex.json"
    caminho.write_text(json.dumps({"versao": 1, "capturas": {
        "25": {"nome": "Pikachu", "vezes": 1},
        "lixo": {"nome": "?", "vezes": 1},
        "6": "nem dicionario",
    }}), encoding="utf-8")

    dex = Pokedex(caminho=caminho)
    assert [i["pid"] for i in dex.lista()] == [25]


def test_escrita_nao_deixa_arquivo_temporario(pokedex):
    pokedex.registrar(25, "Pikachu")
    assert not list(pokedex.caminho.parent.glob("*.tmp"))


def test_disco_cheio_nao_mata_o_jogo(pokedex, monkeypatch):
    """Falha de gravação é ruim, mas derrubar a captura no meio é pior."""
    def explode(*a, **k):
        raise OSError("sem espaço")

    monkeypatch.setattr("pathlib.Path.write_text", explode)
    assert pokedex.registrar(25, "Pikachu") is True        # não levanta
    assert pokedex.tem(25)                                  # vale na sessão


def test_pokedex_vive_ao_lado_do_cache():
    assert Pokedex().caminho.parent == cfg.CACHE_DIR


# ---------------- integração com a caçada ----------------

def test_captura_entra_na_pokedex(catch, arremesso_certeiro, rapido):
    arremesso_certeiro(catch)
    assert catch.pokedex.tem(25)
    assert catch.pokedex.vezes(25) == 1


def test_banner_marca_especie_nova(catch, arremesso_certeiro, rapido):
    arremesso_certeiro(catch)
    assert "novo na Pokédex" in catch.banners[0]["texto"]


def test_banner_de_repetida_nao_anuncia_novidade(catch, arremesso_certeiro, rapido):
    catch.pokedex.registrar(25, "Pikachu")
    arremesso_certeiro(catch)
    assert "novo na Pokédex" not in catch.banners[0]["texto"]
    assert "foi capturado" in catch.banners[0]["texto"]


def test_hud_mostra_o_progresso(catch):
    catch.pokedex.registrar(25, "Pikachu")
    catch.pokedex.registrar(6, "Charizard")
    assert f"Pokédex: 2/{cfg.MAX_ID}" in catch._linhas_hud(time.monotonic())[0]


def test_regiao_suja_cobre_o_progresso(catch):
    """Pokédex cheia deixa a primeira linha mais longa; a região acompanha."""
    for pid in range(1, 40):
        catch.pokedex.registrar(pid, "Pokémon Com Nome Comprido")
    area = catch._area_hud()
    for texto, caixa in catch.caixas_hud(time.monotonic()):
        assert area.contains(caixa.toRect()), f"{texto!r} fica fora da região"


# ---------------- a tela ----------------

def test_tela_lista_os_capturados(app, pokedex, processa):
    pokedex.registrar(25, "Pikachu")
    pokedex.registrar(6, "Charizard")
    painel = PokedexPanel(pokedex)
    painel.atualizar()
    processa(0.1)
    try:
        assert painel.grade.count() == 2
        assert painel.resumo.text().startswith(f"2 de {cfg.MAX_ID}")
    finally:
        painel.close()


def test_tela_vazia_explica_o_que_fazer(app, pokedex, processa):
    painel = PokedexPanel(pokedex)
    painel.atualizar()
    processa(0.1)
    try:
        textos = [w.text() for w in painel.corpo.findChildren(QLabel)]
        assert any("Nada capturado ainda" in t for t in textos)
        assert any(cfg.GESTO_NOME in t for t in textos)
    finally:
        painel.close()


def test_tela_mostra_quantas_vezes(app, pokedex, processa):
    for _ in range(4):
        pokedex.registrar(25, "Pikachu")
    painel = PokedexPanel(pokedex)
    painel.atualizar()
    processa(0.1)
    try:
        textos = [w.text() for w in painel.corpo.findChildren(QLabel)]
        assert "4x" in textos
        assert "Pikachu" in textos
    finally:
        painel.close()


def test_tela_nao_baixa_nada(app, pokedex, processa, monkeypatch):
    """A tela abre com dezenas de sprites: baixar ali travaria a interface."""
    from pokeshake.testing import SessaoFalsa
    proibida = SessaoFalsa(erro=AssertionError("a tela não pode usar a rede"))
    monkeypatch.setattr(sprites, "_session", proibida)
    for pid in (25, 6, 94):
        pokedex.registrar(pid, f"Pokémon #{pid}")
    painel = PokedexPanel(pokedex)
    painel.atualizar()
    processa(0.1)
    try:
        assert painel.grade.count() == 3
    finally:
        painel.close()


def test_tela_remonta_sem_duplicar(app, pokedex, processa):
    pokedex.registrar(25, "Pikachu")
    painel = PokedexPanel(pokedex)
    painel.atualizar()
    pokedex.registrar(6, "Charizard")
    painel.atualizar()
    processa(0.1)
    try:
        assert painel.grade.count() == 2
    finally:
        painel.close()


def test_miniatura_vem_do_cache(app, pikachu):
    mini = sprites.miniatura(25, lado=64)
    assert mini is not None and not mini.isNull()
    assert max(mini.width(), mini.height()) == 64


def test_miniatura_sem_cache_devolve_nada(app, tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "CACHE_DIR", tmp_path)
    assert sprites.miniatura(25) is None


# ---------------- menu e bandeja ----------------

def test_menu_mostra_o_progresso(app, pokedex, processa):
    from pokeshake.menu import OverlayMenu
    menu = OverlayMenu()
    try:
        menu.marcar_pokedex(7)
        assert f"7/{cfg.MAX_ID}" in menu.botao_pokedex.text()
    finally:
        menu.close()


def test_captura_atualiza_menu_e_bandeja(poke, processa):
    poke.pokedex.registrar(25, "Pikachu")
    poke.catch.captured.emit("Pikachu")
    processa(0.1)
    assert f"1/{cfg.MAX_ID}" in poke.menu.botao_pokedex.text()
    assert "Pokédex: 1" in poke.tray.toolTip()


def test_bandeja_abre_a_pokedex(poke, processa):
    acoes = [a.text() for a in poke.tray.contextMenu().actions() if a.text()]
    assert "Pokédex" in acoes
    poke._mostrar_pokedex()
    processa(0.2)
    assert poke.pokedex_panel.isVisible()
    poke.pokedex_panel.hide()
