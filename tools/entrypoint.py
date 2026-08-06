"""Ponto de entrada do executável empacotado.

O PyInstaller carrega o script inicial como ``__main__`` de nível
superior, onde os imports relativos de ``macropad/__main__.py`` não
resolveriam. Este arquivo apenas importa o pacote e chama ``main()``.
"""

from macropad.__main__ import main

raise SystemExit(main())
