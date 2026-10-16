"""Download, cache e preparo dos sprites."""
import pytest

from pokeshake import config as cfg
from pokeshake import sprites


def test_pokemon_animado_vem_como_gif(pikachu):
    data, is_gif = pikachu
    assert is_gif, "Pikachu tem sprite animado no repositório do Showdown"
    assert len(data) > 1000


def test_cai_para_png_quando_nao_ha_gif():
    """Os IDs mais novos não têm sprite animado; o estático precisa cobrir."""
    data, is_gif = sprites.fetch_pokemon(1025)
    if not data:
        pytest.skip("sem rede e sem cache")
    assert not is_gif
    assert (cfg.CACHE_DIR / "1025.png").exists()


def test_ausencia_de_gif_fica_anotada():
    """Sem essa marca, o 404 se repetiria a cada aparição do mesmo Pokémon."""
    sprites.fetch_pokemon(1025)
    assert (cfg.CACHE_DIR / "1025.gif.missing").exists()


def test_sprite_fica_em_cache_no_disco(pikachu):
    assert (cfg.CACHE_DIR / "25.gif").exists()


@pytest.mark.parametrize("bola", ["poke-ball", "master-ball", "quick-ball"])
def test_pokebolas_baixam(bola):
    data = sprites.fetch_ball(bola)
    if not data:
        pytest.skip("sem rede e sem cache")
    assert data[:4] == b"\x89PNG"


def test_todas_as_bolas_configuradas_existem():
    assert len(cfg.BALLS) == 15
    assert len(set(cfg.BALLS)) == len(cfg.BALLS)


def test_bola_sorteada_esta_na_lista():
    assert all(sprites.random_ball() in cfg.BALLS for _ in range(30))


@pytest.mark.parametrize("pid,nome", [(1, "Bulbasaur"), (6, "Charizard"), (25, "Pikachu")])
def test_nomes_vem_da_pokeapi(pid, nome):
    obtido = sprites.pokemon_name(pid)
    if obtido.startswith("Pokémon #"):
        pytest.skip("sem rede e sem cache para a lista de nomes")
    assert obtido == nome


def test_nome_desconhecido_tem_reserva():
    assert sprites.pokemon_name(999999) == "Pokémon #999999"


def test_altura_alvo_uniformiza_o_tamanho(app, pikachu):
    """Os sprites da Pokédex variam muito; no modo caçada todos viram alvos
    de tamanho parecido."""
    data, is_gif = pikachu
    sprite = sprites.Sprite(data, is_gif, target_h=cfg.WILD_HEIGHT)
    assert abs(sprite.size.height() - cfg.WILD_HEIGHT) <= cfg.WILD_HEIGHT * 0.5
    assert not sprite.frame().isNull()
    sprite.stop()


def test_escala_simples_multiplica(app, pikachu):
    data, is_gif = pikachu
    um = sprites.Sprite(data, is_gif, scale=1)
    dois = sprites.Sprite(data, is_gif, scale=2)
    assert dois.size.height() == um.size.height() * 2
    um.stop()
    dois.stop()


def test_sprite_estatico_tambem_desenha(app):
    data, is_gif = sprites.fetch_pokemon(1025)
    if not data:
        pytest.skip("sem rede e sem cache")
    sprite = sprites.Sprite(data, is_gif, target_h=cfg.WILD_HEIGHT)
    assert sprite.movie is None
    assert not sprite.frame().isNull()
