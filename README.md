# 🔄 Mattermost LDAP Group Sync

![GitHub](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Mattermost](https://img.shields.io/badge/Mattermost-5%2B-orange)
![LDAP](https://img.shields.io/badge/LDAP-support-green)

Сервис для автоматической синхронизации LDAP-групп с Mattermost через API.

## 🌟 Основные возможности

| 🛠 Функционал          | 📝 Описание |
|-----------------------|------------|
| **LDAP Integration**  | Получение актуального списка групп и состава пользователей из LDAP |
| **Mattermost API**    | Управление группами и членством через Mattermost API |
| **Smart Sync**        | Сравнение данных и точечное применение изменений |
| **Error Tracking**    | Интеграция с Sentry для мониторинга ошибок |

## 📊 Архитектура решения

```mermaid
graph LR
    A[LDAP Server] --> B[Sync Service] --> C[Mattermost CLI]
```
## 🚀 Как использовать
Замените имя-команды или имя-канала на фактические значения.

1. Синхронизация команд (Team)
Запуск синхронизации всех команд:

```bash
python command.py sync-team
```
Синхронизация конкретной команды:

```bash
python command.py sync-team --team-name "имя-команды"
```
2. Синхронизация каналов (Channel)
Синхронизация всех каналов:

```bash
python command.py sync-channels
```
Синхронизация конкретного канала:

```bash
python command.py sync-channels --channel-name "имя-канала"
```
🧪 Тестовый режим (Dry Run)
Для проверки изменений без фактического применения (имитация) добавьте флаг `--dry-run`:

**Для команды** - `python command.py sync-team --team-name "имя-команды" --dry-run`
**Для канала** - `python command.py sync-channels --channel-name "имя-канала" --dry-run`

* Примечание: Скрипт автоматически выявит отсутствующих пользователей и добавит их, а также удалит неактивных участников в соответствии с данными LDAP.


