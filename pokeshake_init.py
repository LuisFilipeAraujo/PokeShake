"""
PokeShake - Pokémon aparecem por cima da sua área de trabalho.

Modos (escolha no menu overlay ou no ícone da bandeja):
    Agitada  sacuda o mouse e um Pokémon aparece por alguns segundos
    Caçada   Pokémon aparecem pela tela; segure Ctrl e arremesse o mouse
             para lançar uma pokébola. Acertou, capturou.

Dependências:
    pip install -r requirements.txt

Execute:
    python pokeshake_init.py                 # abre o menu de modos
    python pokeshake_init.py --mode catch    # já começa caçando
    python pokeshake_init.py --mode shake
    python pokeshake_init.py --demo          # mostra um Pokémon e sai
    python pokeshake_init.py --dry-run       # roteiro automático; sai 0 se passou

Para sair: "Sair" no menu, no ícone da bandeja, ou Ctrl+C no terminal.
Os ajustes finos (sensibilidade, tempos, gesto de arremesso) estão em
pokeshake/config.py.
"""
import sys

from pokeshake.app import main

if __name__ == "__main__":
    sys.exit(main())
