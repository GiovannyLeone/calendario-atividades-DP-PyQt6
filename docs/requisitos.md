# Requisitos e condições de aceitação

## Requisitos funcionais

| ID | Requisito |
|----|-----------|
| RF01 | O sistema deve permitir criar atividades dos tipos tarefa, reunião, lembrete e evento, com título, descrição, início, término, categoria, prioridade, recorrência e antecedência de lembrete. |
| RF02 | O sistema deve permitir consultar, alterar e excluir atividades. |
| RF03 | O cliente deve exibir o calendário em visão mensal e o detalhe do dia selecionado, com navegação entre meses. |
| RF04 | O sistema deve expandir atividades recorrentes (diária, semanal, mensal) em ocorrências dentro do período consultado, respeitando a data final da recorrência. |
| RF05 | O sistema deve controlar o ciclo de vida da atividade (pendente, em andamento, concluída, cancelada) e recusar transições inválidas. |
| RF06 | O sistema deve validar cada atividade antes de gravá-la e retornar todos os erros encontrados, incluindo conflito de horário entre reuniões. |
| RF07 | O usuário deve poder duplicar uma atividade, deslocando a cópia em N dias. |
| RF08 | O cliente deve permitir desfazer e refazer criação, edição, exclusão, duplicação e mudança de status. |
| RF09 | O servidor deve guardar o histórico de alterações de cada atividade e permitir reverter a última alteração e restaurar uma atividade excluída. |
| RF10 | O sistema deve permitir buscar atividades por uma linguagem de consulta com campos (`title`, `description`, `category`, `priority`, `status`, `kind`, `date`) e operadores `AND`, `OR`, `NOT` e parênteses. |
| RF11 | O sistema deve organizar as atividades em uma árvore de categorias hierárquicas e exibir totais por categoria. |
| RF12 | O sistema deve gerar estatísticas e relatórios diário, semanal e mensal em texto, JSON e HTML. |
| RF13 | O sistema deve exportar o calendário em iCalendar (`.ics`), CSV e JSON. |
| RF14 | O servidor deve registrar notificações de criação, alteração e exclusão e uma trilha de auditoria das operações. |
| RF15 | O cliente deve oferecer tema claro e escuro. |
| RF16 | O servidor deve expor um endpoint REST para cada recurso e o cliente deve consumi-los para enviar e receber dados. |
| RF17 | O sistema deve rejeitar atividade idêntica (mesmo tipo, título sem diferenciar maiúsculas, início e término) a outra já existente. |
| RF18 | O cliente deve reconsultar o servidor ao acionar "Atualizar" (F5) e periodicamente (15 s), ignorando o cache, para refletir alterações feitas por outros clientes. |

## Requisitos não funcionais

| ID | Requisito |
|----|-----------|
| RNF01 | O servidor deve ser implementado em Python com Flask; o cliente em Python com PyQt6. |
| RNF02 | Não é permitido usar banco de dados, APIs de terceiros, serviços de nuvem ou de IA; a persistência é um arquivo JSON local. |
| RNF03 | A aplicação deve executar apenas com `pip install -r requirements.txt`, sem outras configurações ou softwares. |
| RNF04 | A gravação do arquivo JSON deve ser atômica (arquivo temporário seguido de substituição) para evitar corrupção. |
| RNF05 | O código deve aplicar os 23 padrões de projeto do GoF, cada um documentado em `docs/padroes.md`. |
| RNF06 | A API deve responder em JSON com códigos HTTP coerentes (200, 201, 400, 404, 409) e mensagens de erro em português. |
| RNF07 | O cliente deve reduzir chamadas repetidas ao servidor usando cache invalidado a cada alteração. |
| RNF08 | O sistema deve ter testes automatizados do servidor, do cliente e da integração entre os dois. |
| RNF10 | Falha ao gravar o arquivo não pode deixar estado parcial: o servidor desfaz a alteração em memória, mantém o arquivo anterior e responde 500 em JSON com mensagem clara. |
| RNF11 | Entradas malformadas (tipos errados, datas inexistentes, corpo que não é objeto JSON) devem gerar 400 com mensagem, nunca erro interno. |
| RNF09 | A interface não deve travar em caso de erro do servidor: erros são exibidos ao usuário e os dados são recarregados. |

## Condições de aceitação

| ID | Cenário | Resultado esperado |
|----|---------|--------------------|
| CA01 | Criar uma tarefa com título e horário válidos | Servidor responde 201; a atividade aparece no dia correspondente do calendário. |
| CA02 | Criar atividade sem título ou com término antes do início | Servidor responde 400 com a lista de erros; nada é gravado; o cliente mostra os erros. |
| CA03 | Criar uma reunião que se sobrepõe a outra reunião não cancelada | Servidor responde 400 informando a reunião em conflito. |
| CA04 | Criar reunião semanal com data final | `/api/calendar` devolve uma ocorrência por semana (campos `date` e `occurrence_start`) até a data final e nenhuma depois; o cliente mostra cada uma no dia correspondente. |
| CA05 | Aplicar `start` em atividade pendente e depois `start` novamente | A primeira muda para "em andamento"; a segunda responde 409. |
| CA06 | Excluir uma atividade e usar Desfazer no cliente | A atividade volta com os mesmos dados e status. |
| CA07 | Editar uma atividade e chamar `/revert` | A atividade volta ao estado anterior à edição. |
| CA08 | Buscar `priority:high AND NOT status:done` | Retorna só atividades de prioridade alta que não estão concluídas. |
| CA09 | Buscar com sintaxe inválida (ex.: parêntese aberto) | Servidor responde 400 com mensagem explicativa. |
| CA10 | Exportar em `.ics` | Arquivo contém um `VEVENT` por atividade e abre em aplicativos de calendário. |
| CA11 | Duplicar uma atividade com deslocamento de 7 dias | Nova atividade com novo id, mesmo conteúdo, datas deslocadas e status pendente. |
| CA12 | Alternar para o tema escuro | Toda a interface muda de paleta sem recarregar dados. |
| CA13 | Iniciar o cliente com o servidor fora do ar | O cliente exibe a falha de conexão sem encerrar. |
| CA14 | Reiniciar o servidor após alterações | As atividades continuam disponíveis (persistência em `data/activities.json`). |
| CA15 | Criar atividade idêntica a uma existente | Servidor responde 400 ("Já existe uma atividade idêntica"); só uma permanece. |
| CA16 | Falha de gravação em disco durante criação, edição ou exclusão | Servidor responde 500 com mensagem; arquivo e memória permanecem como antes. |
| CA17 | Cliente B aciona "Atualizar" após o cliente A criar, editar ou excluir | B passa a exibir exatamente o estado atual do servidor. |
| CA18 | Servidor fica indisponível com o cliente aberto | Cliente exibe "Servidor indisponível", não trava e volta a funcionar quando o servidor retorna. |
