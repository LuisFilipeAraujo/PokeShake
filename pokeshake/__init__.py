"""PokeShake: Pokémon da PokeAPI como overlay na área de trabalho."""
import os

# precisa valer antes de qualquer import de PyQt6: o backend de mídia despeja
# o cabeçalho do arquivo decodificado a cada grito, pelo log do Qt
os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.*=false")

__version__ = "0.3.0"
