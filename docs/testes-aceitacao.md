# Plano de testes de qualidade — Calendário de atividades

Rastreabilidade entre o plano de testes (seção 2, Calendário de atividades) e os testes
automatizados em `tests/test_aceitacao_calendario.py`. Para rodar só estes testes:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest tests/test_aceitacao_calendario.py
```

Os testes que usam a interface abrem a `MainWindow` real (PyQt6, modo offscreen), acionam os
controles pelos sinais dos botões visíveis (com o diálogo modal substituído por um dublê que
devolve os dados "digitados") e conferem a tela, a mensagem exibida e o arquivo persistido
no servidor.

## Padrões demonstrados

| Tipo | Padrão | Comportamento observável testado |
|------|--------|----------------------------------|
| Criacional | Builder | Atividade só com campos obrigatórios recebe padrões; com todos os opcionais encadeados é montada corretamente; dados malformados são recusados na montagem. |
| Estrutural | Facade | Criar, editar, consultar e buscar eventos por uma interface única, no servidor (`CalendarFacade`) e no cliente (`ClientFacade`). |
| Comportamental | Observer | Calendário e lembretes se redesenham após criar, editar, desfazer e excluir; o repositório notifica eventos na ordem e deixa de notificar após `unsubscribe`. |

## Cenários

| Cenário | Classe de teste | O que verifica |
|---------|-----------------|----------------|
| T2.1 Criar e exibir atividade | `TestT21CriarEExibir` | Criação por API (201) e pela interface; atividade aparece no painel do dia e na célula do mês corretos, e não em outro dia ou mês; todos os tipos são criados. |
| T2.2 Validar período e campos obrigatórios | `TestT22ValidarPeriodoECamposObrigatorios` | 24 entradas inválidas (ausentes, vazias, malformadas, inexistentes como 31/02, fora de faixa) respondem 400 com mensagem e nada é persistido; limites válidos (título de 80 caracteres, 24 h, lembrete 0 e 10080) são aceitos; atividade duplicada, conflito entre reuniões, edição inválida, 404 e 409; a interface mostra todos os erros e o servidor não grava. |
| T2.3 Persistência e atualização entre clientes | `TestT23PersistenciaEAtualizacaoEntreClientes` | Dados sobrevivem a reinício do servidor, sem arquivo temporário e com JSON íntegro; um segundo cliente enxerga criação, edição e exclusão feitas pelo primeiro após "Atualizar"; falha de gravação não deixa dado parcial (500, arquivo e memória intactos); falha de rede é informada sem travar a janela e a operação volta a funcionar quando a rede volta. |
| T2.4 Builder e Observer | `TestT24BuilderEObserver` | Builder com obrigatórios e opcionais, Factory usando o Builder, Facade e Observer (servidor e cliente), incluindo operações rejeitadas que não geram eventos e transições de estado refletidas na tela. |

## Critérios gerais do plano

- **Dados:** entradas válidas, ausentes, fora de faixa, malformadas, duplicadas e limites de negócio (T2.2).
- **Persistência:** sem gravações parciais; o arquivo é substituído de forma atômica (T2.3).
- **Cliente-servidor:** códigos 400, 404, 405, 409 e 500 com corpo JSON; consistência após nova consulta; comportamento em falha de rede (T2.2 e T2.3).
- **Design patterns:** responsabilidade isolada e resultado correto em casos válidos e inválidos (T2.4).
- **Interface QT:** ações pelos controles visíveis, mensagens, atualização da tela e ausência de travamentos (T2.1 a T2.3).

## Observações

- O aplicativo não tem contas nem papéis de usuário, então os critérios de autenticação e
  autorização não se aplicam. O que o teste confere é o tratamento de rotas e métodos
  inexistentes (404 e 405).
- O arquivo do plano de testes traz, para o Calendário, os padrões e os títulos de T2.1 a
  T2.4, mas as áreas de detalhe de cada cenário estavam em branco. Os testes seguem os
  títulos e os critérios gerais; ajuste-os se o professor tiver passos específicos.
