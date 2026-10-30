# AGENTS.md

Projeto: rede social generalista (estilo Twitter), fork 1:1 do Lumem sem os temas de sonhos, em repositório limpo. Desenvolvedor solo.

## Regras gerais
- Nenhum segredo no repositório, nos logs ou na documentação. `.env.example` só com nomes de variáveis.
- CORS restrito por padrão; bloqueio bidirecional; mídia sempre com checagem de autorização; testes obrigatórios no CI.
- Texto de documentação impessoal, em português do Brasil. O produto não é rede de política nem de debates e não é "microblog".
- Nunca declare que algo funciona sem ter rodado a verificação. Se não verificou, escreva "não verificado".

## Especialistas consultivos
Subagentes em `.agents/agents/` (E1 a E10). Eles **não escrevem arquivos**: devolvem propostas curtas ao agente principal, que decide e implementa.
Para decisões grandes, invoque os especialistas relevantes **em paralelo** (3 ramos cada), peça crítica cruzada e deixe o E1 pontuar e podar.
