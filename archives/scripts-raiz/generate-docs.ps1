$project = "C:\Users\lezin\Downloads\project\alca-financas"
Set-Location $project

$prompt = @"
Gere o BLOCO 1 do ARCHITECTURE.md do projeto Alça Finanças.

Conteúdo:
- visão geral
- componentes
- diagrama ASCII

máximo 60 linhas
markdown final
"@

$prompt | ollama run qwen2.5-coder:14b > ARCHITECTURE.md