"""Prévia de importação a partir de um artefato em quarentena.

``preview.build_preview`` gera a prévia (OFX pelo importador determinístico do
produto; CSV só como conferência). ``tools.build_import_tools`` expõe a
ferramenta ``imports.preview`` e ``tools.preview_provider`` entrega a mesma
função ao componente financeiro. Nada aqui grava transações.
"""
