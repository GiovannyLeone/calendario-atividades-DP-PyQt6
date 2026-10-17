# Diagramas de classes

Os diagramas usam [Mermaid](https://mermaid.js.org/), que o GitHub renderiza automaticamente.

## Servidor — domínio, estados e criação

```mermaid
classDiagram
    direction LR
    class Describable {
        <<abstract>>
        +describe() str
    }
    class Activity {
        +id
        +title
        +start
        +end
        +category
        +priority
        +recurrence
        +reminder_minutes
        +status
        +transition(action)
        +clone(days) Activity
        +accept(visitor)
        +create_memento(reason)
        +restore_from(memento)
        +to_dict() dict
    }
    class Task
    class Meeting
    class Reminder
    class Event
    Describable <|-- Activity
    Activity <|-- Task
    Activity <|-- Meeting
    Activity <|-- Reminder
    Activity <|-- Event

    class ActivityState {
        <<abstract>>
        +start(activity)
        +pause(activity)
        +complete(activity)
        +cancel(activity)
        +reopen(activity)
    }
    ActivityState <|-- PendingState
    ActivityState <|-- InProgressState
    ActivityState <|-- DoneState
    ActivityState <|-- CancelledState
    Activity --> ActivityState : estado atual

    class ActivityCreator {
        <<abstract>>
        +create(data) Activity
        +make_activity(data)*
    }
    ActivityCreator <|-- TaskCreator
    ActivityCreator <|-- MeetingCreator
    ActivityCreator <|-- ReminderCreator
    ActivityCreator <|-- EventCreator
    class ActivityBuilder {
        +with_title()
        +starting_at()
        +ending_at()
        +lasting()
        +in_category()
        +with_priority()
        +repeating()
        +reminding()
        +build() Activity
    }
    ActivityCreator ..> ActivityBuilder : usa
    ActivityCreator ..> Activity : cria
```

## Servidor — persistência, fachada e API

```mermaid
classDiagram
    direction LR
    class Flask_app {
        <<create_app>>
        /api/activities
        /api/calendar
        /api/search
        /api/reports
        /api/export
    }
    class CalendarFacade {
        +list_activities()
        +create_activity(data)
        +update_activity(id, data)
        +delete_activity(id)
        +duplicate_activity(id, days)
        +transition(id, action)
        +revert(id)
        +restore(id)
        +calendar(start, end)
        +search(query)
        +stats()
        +report(kind, ref, fmt)
        +export(fmt)
    }
    Flask_app --> CalendarFacade

    class ActivityStore {
        <<interface>>
        +all()
        +get(id)
        +add(activity)
        +update(activity)
        +remove(id)
    }
    class ActivityRepository {
        <<Singleton>>
        -arquivo JSON
    }
    class AuditedRepositoryProxy {
        +audit_entries()
    }
    class Observable {
        +subscribe(observer)
        +notify(event)
    }
    class Observer {
        <<interface>>
        +update(event)
    }
    class NotificationCenter
    ActivityStore <|.. ActivityRepository
    ActivityStore <|.. AuditedRepositoryProxy
    AuditedRepositoryProxy o--> ActivityRepository : delega
    Observable <|-- ActivityRepository
    Observer <|.. NotificationCenter
    Observable --> Observer : notifica
    CalendarFacade --> AuditedRepositoryProxy
    CalendarFacade --> NotificationCenter

    class HistoryCaretaker
    class ActivityMemento
    HistoryCaretaker o--> ActivityMemento
    CalendarFacade --> HistoryCaretaker
```

## Servidor — consulta, relatórios e exportação

```mermaid
classDiagram
    direction LR
    class Validator {
        <<abstract>>
        +set_next(v)
        +handle(activity, ctx)
        +check(activity, ctx)*
    }
    Validator <|-- TitleValidator
    Validator <|-- EnumValidator
    Validator <|-- TimeRangeValidator
    Validator <|-- RecurrenceValidator
    Validator <|-- ReminderValidator
    Validator <|-- DuplicateValidator
    Validator <|-- ConflictValidator
    Validator --> Validator : próximo

    class Expression {
        <<abstract>>
        +interpret(activity) bool
    }
    Expression <|-- TermExpression
    Expression <|-- AndExpression
    Expression <|-- OrExpression
    Expression <|-- NotExpression
    class QueryParser {
        +parse() Expression
    }
    QueryParser ..> Expression

    class SortStrategy {
        <<abstract>>
        +key(activity)*
        +sort(list)
    }
    SortStrategy <|-- ByStartSort
    SortStrategy <|-- ByPrioritySort
    SortStrategy <|-- ByTitleSort
    SortStrategy <|-- ByCategorySort
    ActivitySorter o--> SortStrategy

    class DateRangeIterator
    class OccurrenceIterator

    class CategoryComponent {
        <<abstract>>
        +count()
        +total_minutes()
        +to_dict()
    }
    CategoryComponent <|-- ActivityLeaf
    CategoryComponent <|-- CategoryNode
    CategoryNode o--> CategoryComponent : filhos

    class ActivityVisitor {
        <<abstract>>
        +visit_task()
        +visit_meeting()
        +visit_reminder()
        +visit_event()
    }
    ActivityVisitor <|-- StatisticsVisitor
    ActivityVisitor <|-- DetailsVisitor

    class Describable {
        <<abstract>>
        +describe()
    }
    Describable <|-- ActivityDecorator
    ActivityDecorator <|-- PriorityDecorator
    ActivityDecorator <|-- RecurrenceDecorator
    ActivityDecorator <|-- ReminderDecorator
    ActivityDecorator <|-- StatusDecorator
    ActivityDecorator o--> Describable

    class Exporter {
        <<abstract>>
        +export(activities)
        +header()
        +item(activity)*
        +footer()
    }
    Exporter <|-- CsvExporter
    Exporter <|-- JsonExporter
    Exporter <|-- IcsExporter
    class IcsComponent {
        <<interface>>
        +to_ics()
    }
    IcsComponent <|.. ActivityIcsAdapter
    ActivityIcsAdapter o--> Activity : adapta
    IcsExporter ..> ActivityIcsAdapter

    class Report {
        <<abstract>>
        +period(ref)*
        +render(ref)
    }
    Report <|-- DailyReport
    Report <|-- WeeklyReport
    Report <|-- MonthlyReport
    class ReportFormatter {
        <<interface>>
        +format(...)
    }
    ReportFormatter <|.. TextFormatter
    ReportFormatter <|.. JsonFormatter
    ReportFormatter <|.. HtmlFormatter
    Report o--> ReportFormatter : ponte
```

## Cliente — API, fachada, comandos e modelo

```mermaid
classDiagram
    direction LR
    class CalendarApi {
        <<interface>>
        +list_activities()
        +calendar(start, end)
        +create(data)
        +update(id, data)
        +delete(id)
        +transition(id, action)
        +search(q)
        +report()
        +export()
    }
    class HttpCalendarApi
    class CachingApiProxy {
        +invalidate()
    }
    CalendarApi <|.. HttpCalendarApi
    CalendarApi <|.. CachingApiProxy
    CachingApiProxy o--> CalendarApi : delega

    class ClientFacade {
        +create_activity()
        +edit_activity()
        +delete_activity()
        +duplicate_activity()
        +change_status()
        +undo()
        +redo()
        +search()
        +stats()
        +export_to_file()
    }
    class Command {
        <<abstract>>
        +execute()
        +undo()
    }
    Command <|-- CreateActivityCommand
    Command <|-- UpdateActivityCommand
    Command <|-- DeleteActivityCommand
    Command <|-- TransitionCommand
    Command <|-- DuplicateActivityCommand
    class CommandHistory {
        +execute(cmd)
        +undo()
        +redo()
    }
    CommandHistory o--> Command
    ClientFacade --> CommandHistory
    ClientFacade --> CalendarApi
    Command --> CalendarApi : receptor

    class Subject {
        +attach(observer)
        +detach(observer)
        +notify(change)
    }
    class Observer {
        <<interface>>
        +on_change(subject, change)
    }
    class CalendarModel {
        +refresh()
        +select(day)
        +next_month()
        +go_today()
    }
    Subject <|-- CalendarModel
    ClientFacade --> CalendarModel
    CalendarModel --> CalendarApi
```

## Cliente — interface gráfica

```mermaid
classDiagram
    direction LR
    class Observer {
        <<interface>>
        +on_change(subject, change)
    }
    class MainWindow
    class MonthView
    class DayCell
    class DayPanel
    class ActivityDialog
    class ActivityFormMediator {
        +changed()
    }
    Observer <|.. MainWindow
    Observer <|.. MonthView
    Observer <|.. DayPanel
    MainWindow *--> MonthView
    MainWindow *--> DayPanel
    MonthView *--> DayCell
    MainWindow ..> ActivityDialog
    ActivityDialog --> ActivityFormMediator : colegas do formulário

    class ThemeFactory {
        <<abstract factory>>
        +create_palette()
        +create_button_style()
        +create_cell_style()
    }
    ThemeFactory <|-- LightThemeFactory
    ThemeFactory <|-- DarkThemeFactory
    class Palette
    class ButtonStyle
    class CellStyle
    Palette <|-- LightPalette
    Palette <|-- DarkPalette
    ButtonStyle <|-- FlatButtonStyle
    ButtonStyle <|-- FilledButtonStyle
    CellStyle <|-- LightCellStyle
    CellStyle <|-- DarkCellStyle
    ThemeFactory ..> Palette
    ThemeFactory ..> ButtonStyle
    ThemeFactory ..> CellStyle
    MainWindow --> ThemeFactory

    class ItemStyleFactory {
        <<Flyweight factory>>
        +get(kind, status) ItemStyle
    }
    class ItemStyle {
        <<Flyweight>>
        +css()
    }
    ItemStyleFactory o--> ItemStyle : pool compartilhado
    MonthView --> ItemStyleFactory
    DayPanel --> ItemStyleFactory
```
