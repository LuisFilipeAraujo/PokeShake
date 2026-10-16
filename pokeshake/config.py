"""Constantes de ajuste do PokeShake. Mexa aqui para mudar o comportamento."""
from pathlib import Path

# ---------------- Geral ----------------
MAX_ID = 1025                   # Pokédex nacional até a Gen 9
CACHE_DIR = Path.home() / ".poke_shake_cache"
POLL_MS = 16                    # leitura do cursor e do gesto (~60x por segundo)
FRAME_MS = 16                   # quadro do modo caçada
USER_AGENT = "PokeShake/0.2 (app de desktop, uso pessoal)"

SPRITES = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites"
POKEAPI = "https://pokeapi.co/api/v2"
SPRITE_URLS = [
    SPRITES + "/pokemon/other/showdown/{id}.gif",   # animado
    SPRITES + "/pokemon/{id}.png",                  # estático (reserva)
]
BALL_URL = SPRITES + "/items/{name}.png"
BALLS = ["poke-ball", "great-ball", "ultra-ball", "master-ball", "premier-ball",
         "timer-ball", "dusk-ball", "quick-ball", "net-ball", "heal-ball",
         "luxury-ball", "nest-ball", "repeat-ball", "dive-ball", "level-ball"]

# ---------------- Modo Agitada ----------------
SHAKE_WINDOW = 0.6              # segundos analisados
SHAKE_REVERSALS = 4             # inversões de direção necessárias
SHAKE_SEGMENT_PX = 40           # deslocamento mínimo entre inversões
SHAKE_COOLDOWN = 1.0            # segundos entre aparições
SHAKE_DISPLAY_MS = 2500         # quanto tempo o sprite fica na tela
SHAKE_SCALE = 2                 # ampliação do sprite

# ---------------- Modo Caçada ----------------
THROW_GESTURE = "middle"        # middle | ctrl | shift | alt | right
GESTO_NOMES = {"middle": "a roda do mouse", "ctrl": "Ctrl", "shift": "Shift",
               "alt": "Alt", "right": "o botão direito"}
GESTO_NOME = GESTO_NOMES.get(THROW_GESTURE, THROW_GESTURE)
WILD_HEIGHT = 150               # altura alvo do Pokémon na tela, em pixels
WILD_TTL = 30.0                 # segundos até o Pokémon fugir
WILD_MAX = 4                    # quantos podem estar na tela ao mesmo tempo
SPAWN_MIN, SPAWN_MAX = 3.0, 7.0 # intervalo entre aparições
PAUSE_MIN, PAUSE_MAX = 6.0, 12.0  # silêncio depois de uma captura, para dar expectativa
BOB_PIXELS = 10                 # balanço vertical parado
BOB_SPEED = 1.8

BALL_SCALE = 1.7                # ampliação da pokébola
BALL_OFFSET = (26, 26)          # deslocamento da bola em relação ao cursor
BALL_REDRAW_S = 0.45            # espera até a próxima bola aparecer
FLICK_WINDOW = 0.14             # segundos de movimento usados para a direção
THROW_SPEED_MIN = 450.0         # px/s: arremesso mínimo quando o gesto é fraco
THROW_SPEED_MAX = 2600.0        # px/s: teto, para a bola não sumir num quadro
GRAVITY = 950.0                 # px/s² puxando a bola para baixo
BALL_SPIN = 520.0               # graus por segundo
MISS_TTL = 2.5                  # segundos até a bola errada sumir
HIT_SHRINK = 0.82               # área de acerto do Pokémon (1.0 = sprite inteiro)

SUCK_S = 0.45                   # duração da sugada para dentro da bola
WOBBLE_S = 0.55                 # duração de cada balançada
WOBBLES = 3                     # quantas balançadas antes de confirmar
CELEBRATE_S = 2.2               # duração da comemoração
PARTICLES = 46                  # faíscas da comemoração

HUD_HINT_S = 6.0                # segundos mostrando a dica do gesto
AVISO_FALHA_S = 12.0            # por quanto tempo avisar que o download falhou
NOMES_RETRY_S = 60.0            # recuo antes de tentar a lista de nomes de novo
