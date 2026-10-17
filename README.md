# Calendário de Atividades — Projeto de Design Patterns

Disciplina: Paradigmas de Programação (CC5AN) · Projeto sobre *design patterns*

Aplicação cliente-servidor em **Python** para gerenciar um calendário de atividades
(tarefas, reuniões, lembretes e eventos), construída para demonstrar os **23 padrões
de projeto do GoF**.

| Módulo   | Tecnologia                | Pasta      |
|----------|---------------------------|------------|
| Servidor | Flask (API REST em JSON)  | `server/`  |
| Cliente  | PyQt6 (interface gráfica) | `client/`  |

Sem banco de dados, APIs de terceiros, nuvem ou IA: a persistência é um arquivo JSON local
(`data/activities.json`, criado a partir de `data/activities_seed.json` na primeira execução).

## Como executar

**Windows (PowerShell), recomendado:** use um ambiente virtual em caminho curto.

```powershell
python -m venv C:\calvenv
C:\calvenv\Scripts\pip install -r requirements.txt
C:\calvenv\Scripts\python run.py          # sobe o servidor em segundo plano e abre o cliente
```

**Linux/macOS:**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt     # Flask, PyQt6, requests, pytest
python run.py
```

> **Erro `No such file or directory ... PyQt6\Qt6\qml\...` no Windows?** É o limite de 260
> caracteres de caminho (comum com o Python da Microsoft Store). Use o ambiente virtual em
> `C:\calvenv` como acima, ou habilite caminhos longos
> ([guia do pip](https://pip.pypa.io/warnings/enable-long-paths)) e reinstale.

Ou em dois terminais:

```bash
python run_server.py                # API em http://127.0.0.1:5055
python run_client.py                # interface PyQt6
```

## Testes

```bash
QT_QPA_PLATFORM=offscreen python -m pytest      # Windows (PowerShell): $env:QT_QPA_PLATFORM="offscreen"; python -m pytest
```

144 testes cobrindo: padrões do servidor (criacionais, estruturais e comportamentais),
endpoints Flask, lógica do cliente (comandos, proxy, mediator, observer, API HTTP real),
widgets PyQt e o plano de aceitação do Calendário (T2.1 a T2.4, em
`tests/test_aceitacao_calendario.py`; veja [`docs/testes-aceitacao.md`](docs/testes-aceitacao.md)). A demonstração final da aplicação em uso é o `python run.py`.

## Funcionalidades

- CRUD de atividades de quatro tipos (tarefa, reunião, lembrete, evento) com categorias
  hierárquicas (`Trabalho/Reuniões`), prioridade, recorrência (diária, semanal, mensal) e lembrete.
- Visão mensal do calendário, painel do dia e navegação entre meses.
- Ciclo de vida da atividade (iniciar, pausar, concluir, cancelar, reabrir).
- Validação em cadeia, com bloqueio de conflito de horário entre reuniões.
- Duplicar atividade, desfazer/refazer (cliente), reverter alterações e restaurar excluídas (servidor).
- Busca com linguagem de consulta: `priority:high AND (category:Trabalho OR status:done)`.
- Árvore de categorias, estatísticas, relatórios (dia/semana/mês em texto, JSON ou HTML).
- Exportação para `.ics`, `.csv` e `.json`.
- Tema claro/escuro, notificações de mudanças e trilha de auditoria.

## Estrutura

```
server/   API Flask + domínio + padrões (facade.py é o ponto de entrada da lógica)
client/   Cliente PyQt6: api, proxy, comandos, mediator, temas, ui/
tests/    Testes automatizados (pytest)
data/     Dados iniciais (activities_seed.json) e arquivo de persistência em execução
docs/     requisitos.md · diagramas.md · padroes.md
```

## Documentação

- [`docs/requisitos.md`](docs/requisitos.md): requisitos funcionais, não-funcionais e condições de aceitação.
- [`docs/diagramas.md`](docs/diagramas.md): diagramas de classes do servidor e do cliente (Mermaid).
- [`docs/testes-aceitacao.md`](docs/testes-aceitacao.md): rastreabilidade entre o plano de testes de qualidade e os testes automatizados.
- [`docs/padroes.md`](docs/padroes.md): onde cada um dos 23 padrões está e por que foi usado.

## Endpoints principais

| Método | Rota | Descrição |
|--------|------|-----------|
| GET/POST | `/api/activities` | Lista (`sort`, `status`, `kind`, `category`) / cria |
| GET/PUT/DELETE | `/api/activities/<id>` | Consulta / altera / exclui |
| POST | `/api/activities/<id>/duplicate` | Clona a atividade (Prototype) |
| POST | `/api/activities/<id>/transition` | `{"action": "start\|pause\|complete\|cancel\|reopen"}` |
| POST | `/api/activities/<id>/revert` · `/restore` | Reverte alteração / restaura excluída (Memento) |
| GET | `/api/activities/<id>/history` | Histórico de versões |
| GET | `/api/calendar?start=&end=` | Ocorrências no período (expande recorrências) |
| GET | `/api/search?q=` | Busca pela linguagem de consulta |
| GET | `/api/stats` · `/api/categories` | Estatísticas / árvore de categorias |
| GET | `/api/reports/<daily\|weekly\|monthly>?date=&format=` | Relatórios |
| GET | `/api/export/<ics\|csv\|json>` | Exportação |
| GET | `/api/notifications` · `/api/audit` | Notificações e auditoria |
| GET | `/api/health` | Verificação do servidor |
