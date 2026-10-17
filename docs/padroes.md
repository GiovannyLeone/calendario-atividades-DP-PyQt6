# Mapa dos 23 padrões de projeto (GoF)

Cada linha indica onde o padrão está no código e qual problema do calendário ele resolve.

## Criacionais

| Padrão | Onde | Para que serve no projeto |
|--------|------|---------------------------|
| **Singleton** | `server/singleton.py` (`SingletonMeta`), `server/repository.py` (`ActivityRepository`) | Garante um único repositório de atividades, evitando duas instâncias gravando o mesmo arquivo JSON. |
| **Factory Method** | `server/factory.py` (`ActivityCreator` e `TaskCreator`, `MeetingCreator`, `ReminderCreator`, `EventCreator`) | Cada criador decide a classe concreta (`Task`, `Meeting`, `Reminder`, `Event`) e seus valores padrão; `creator_for(kind)` escolhe o criador. |
| **Abstract Factory** | `client/themes.py` (`ThemeFactory`, `LightThemeFactory`, `DarkThemeFactory`) | Cria a família coerente de produtos do tema (`Palette`, `ButtonStyle`, `CellStyle`); trocar de tema troca a família inteira. |
| **Builder** | `server/builder.py` (`ActivityBuilder`) | Monta atividades com muitos campos opcionais em passos encadeados (`with_title().starting_at().lasting().build()`), validando ao final. |
| **Prototype** | `server/activity.py` (`Activity.clone`) | Duplicar uma atividade copia o objeto (deep copy) e ajusta id, datas e status em vez de recriar campo a campo. |

## Estruturais

| Padrão | Onde | Para que serve no projeto |
|--------|------|---------------------------|
| **Adapter** | `server/exporters.py` (`ActivityIcsAdapter` → `IcsComponent`) | Adapta `Activity` à interface `to_ics()` exigida pelo formato iCalendar, sem alterar a classe de domínio. |
| **Bridge** | `server/bridge.py` (`Report` × `ReportFormatter`) | Separa a abstração (relatório diário, semanal, mensal) da implementação de formato (texto, JSON, HTML); as duas hierarquias crescem de forma independente. |
| **Composite** | `server/composite.py` (`CategoryComponent`, `ActivityLeaf`, `CategoryNode`) | Categorias hierárquicas (`Trabalho/Reuniões`): nós e folhas respondem a `count()` e `total_minutes()` do mesmo jeito. |
| **Decorator** | `server/decorators.py` (`ActivityDecorator`, `PriorityDecorator`, `RecurrenceDecorator`, `ReminderDecorator`, `StatusDecorator`) | Compõe o rótulo exibido de uma atividade ("repete semanalmente", "lembrar 15 min antes") empilhando decoradores. |
| **Facade** | `server/facade.py` (`CalendarFacade`), `client/facade.py` (`ClientFacade`) | Interface única sobre os subsistemas: as rotas Flask e a interface PyQt chamam a fachada em vez de conhecer repositório, validação, histórico, etc. |
| **Flyweight** | `client/flyweight.py` (`ItemStyleFactory`, `ItemStyle`) | Os estilos visuais por tipo/status são compartilhados em um pool; centenas de ocorrências no calendário reutilizam poucos objetos de estilo. |
| **Proxy** | `server/repository.py` (`AuditedRepositoryProxy`), `client/proxy.py` (`CachingApiProxy`) | No servidor, proxy de auditoria registra cada operação do repositório. No cliente, proxy de cache evita requisições repetidas e invalida o cache a cada escrita. |

## Comportamentais

| Padrão | Onde | Para que serve no projeto |
|--------|------|---------------------------|
| **Chain of Responsibility** | `server/validation.py` (`Validator` e sete validadores encadeados) | Título → enums → intervalo de tempo → recorrência → lembrete → duplicidade → conflito de horário; cada elo acumula erros e repassa ao próximo. |
| **Command** | `client/commands.py` (`Command`, `CreateActivityCommand`, `UpdateActivityCommand`, `DeleteActivityCommand`, `TransitionCommand`, `DuplicateActivityCommand`, `CommandHistory`) | Cada ação do usuário é um objeto com `execute()` e `undo()`, o que permite desfazer e refazer. |
| **Interpreter** | `server/interpreter.py` (`QueryParser`, `TermExpression`, `AndExpression`, `OrExpression`, `NotExpression`) | Gramática da busca (`priority:high AND (category:Trabalho OR status:done)`) transformada em árvore de expressões que avalia cada atividade. |
| **Iterator** | `server/iterators.py` (`DateRangeIterator`, `OccurrenceIterator`) | Percorre dias de um período e gera, de forma preguiçosa, as ocorrências de atividades recorrentes. |
| **Mediator** | `client/mediator.py` (`ActivityFormMediator`) | No formulário de atividade, os campos não se conhecem: o mediador habilita/desabilita término, local, participantes, data final da recorrência e antecedência do lembrete conforme o tipo e as opções escolhidas, e só libera o botão Salvar com título preenchido. |
| **Memento** | `server/memento.py` (`ActivityMemento`, `HistoryCaretaker`) e `Activity.create_memento` / `restore_from` | Guarda versões anteriores de cada atividade para reverter a última alteração e restaurar atividades excluídas. |
| **Observer** | `server/observer.py` (`Observable`, `NotificationCenter`), `client/observer.py` (`Subject`, `Observer`) | No servidor, o repositório notifica mudanças. No cliente, `CalendarModel` notifica `MainWindow`, `MonthView` e `DayPanel`, que se redesenham. |
| **State** | `server/state.py` (`ActivityState`, `PendingState`, `InProgressState`, `DoneState`, `CancelledState`) | Cada estado define quais transições são válidas e qual é o próximo estado; transições inválidas geram erro 409. |
| **Strategy** | `server/strategy.py` (`SortStrategy` e quatro estratégias, `ActivitySorter`) | A ordenação da listagem (início, prioridade, título, categoria) é escolhida em tempo de execução por parâmetro da API. |
| **Template Method** | `server/exporters.py` (`Exporter.export` com `CsvExporter`, `JsonExporter`, `IcsExporter`) | `export()` fixa o esqueleto (cabeçalho, itens, rodapé) e cada formato preenche só os passos que mudam. |
| **Visitor** | `server/visitor.py` (`ActivityVisitor`, `StatisticsVisitor`, `DetailsVisitor`), `Activity.accept` | Adiciona operações sobre a hierarquia de atividades (estatísticas, detalhes) sem alterar as classes `Task`, `Meeting`, `Reminder` e `Event`. |

## Verificação

Os testes que exercitam cada padrão estão em `tests/test_server_creational.py`,
`tests/test_server_structural.py`, `tests/test_server_behavioral.py` e
`tests/test_client_logic.py`; a integração por HTTP está em `tests/test_server_api.py`.
