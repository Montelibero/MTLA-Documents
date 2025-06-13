# ~~Программа супераппа Монтелиберо~~

> Документ отменён решением Совета Ассоциации [№ 180](https://t.me/c/2042260878/502).

## 0. Ответственность

- **Координатор**: `GD5GTXUSBYEKLN242J2QWPTPGRXXV7KKW4FP4YQPP5ZZQ3AA25HNHN3A`
- **Исполнитель**: `GDRLJC6EOKRR3BPKWGJPGI5GUN4GZFZRWQFDG3RJNZJEIBYA7B3EPROG`
- **Счет программы**: `GDL7IY5RPCYUFF7637LQS6JGQAAH5W35WRQCG4HEG4MS2GC7RA6ISAPP`

## 1. Проблематизация

### 1.1. Суть проблемы

- Текущая коммуникация и взаимодействие внутри Ассоциации Монтелиберо разрознены: часть активности проходит в чатах, часть — в таблицах или сторонних ресурсах.
- Референдумы, слушания Совета, ведение программ в Распределенном правлении не имеют единого понятного интерфейса, что снижает прозрачность и вовлечённость.
- Привлечение новых участников и инвесторов затруднено отсутствием «витрины», демонстрирующей возможности Ассоциации.
- Нет единого «точки входа», где бы пользователь мог сразу увидеть все доступные услуги, финансовые инструменты, социальные механизмы.

### 1.2. Предыдущие попытки и сложности

- Отдельные боты не образуют целостностную экосистему.
- Традиционные мессенджеры и форумы не учитывают блокчейн-функции и не решают задачу единой токеномики.

## 2. Концептуализация

### 2.1. Идея и общая концепция

- Создать **MVP-суперапп**, в котором будут объединены все важные процессы Ассоциации: голосования (в т.ч. референдумы), финансовые переводы, уровни членства, распределенная репутация, создание и координация программ, а также база для геймификации и краудфандинга.
- В рамках MVP ограничиться чат-ботом и Telegram-приложением, что будет агрегировать данные из блокчейна и фокусировать внимание пользователя на ключевых событиях Ассоциации, перенаправляя на релевантные площадки.
- Показать «витрину» возможностей Монтелиберо для **новых пользователей, инвесторов, партнёров**: удобный интерфейс, работающий на телефоне и не требующий глубоких знаний о блокчейне.
- Важно сохранять все процессы Монтелиберо на блокчейне и не выносить в суперапп, чтобы не создавать себе централизованную зависимость.

### 2.2. Польза и востребованность

- Повышенная прозрачность и вовлечённость участников: все решения и финансы внутри одного интерфейса.
- Более лёгкий онбординг новичков: человек видит, как устроены услуги «виртуального сообщества», и может сразу поучаствовать.
- Демонстрация реальной децентрализации и панархического подхода Монтелиберо.

## 3. Проектирование

### 3.1. Определение целей и KPI

- Сделать суперапп максимально **удобным инструментом** пользования и управления основными процессами Ассоциации.
- Повысить **конверсию онбординга**: из числа тех, кто скачал приложение, не менее 30–40% должны стать активными участниками.
- Увеличить **финансовую активность** (количество транзакций, объём обмена токенами).

### 3.2. Техническая архитектура и функционал MVP

- **Чат-бот** для Telegram, который даёт справку, приветствует новых людей, приводит ссылки на профиль и операции внутри супераппа.
- **Приложение в Telegram** (или веб-интерфейс), где пользователь видит:
	- Свой **профиль** и данные (уровень участия, рейтинг, достижения).
    - Список **корпоратов**, к которым он может присоединиться или создать нового.
    - Баланс и возможность совершать **переводы** другим участникам.
    - Список основных **голосований** и суммаризацию обсуждений.
- **Административная панель**: учёт пользователей, ограниченный набор метрик (активность, переводы), базовые инструменты для модерации.

### 3.3. Ресурсы и сроки

- Разработка будет вестись в составе **Unified Humankind Technological Consortium (UHTC)**.
- **Гильдия программистов**: разработка бэкенда, блокчейн-интеграции, настройка кошелька.
- **Команда фронтенда/маркетинга**: дизайн интерфейса, удобство использования, презентационные материалы.
- **Совет Ассоциации**: согласование правил (как считать репутацию, как работать с голосованиями), утверждение итогового функционала.
- **Предварительный таймлайн**:
    - 1–3 месяца на прототип чат-бота и базовое приложение (MVP)
    - 3–4 месяц — развёртывание геймификации, подписок, расширенного функционала.

### 3.4. Индикаторы и проверка результата

- Количество активных пользователей (учитывая рост от базового уровня).
- Число проведённых внутри супераппа референдумов, решений Совета.
- Транзакционный объём в системе.

## 4. Проектная реализация

### 4.1. Запуск чат-бота и MVP-приложения

- Подготовить бота, который в каждом чате Ассоциации периодически напоминает о функционале супераппа и даёт ссылки для авторизации.
- Организовать базовую модель кошелька (внутренняя валюта), простейшие переводы между участниками.

### 4.2. Интеграция с существующей системой MTL

- Синхронизировать данные о пользователях, чтобы избежать повторной регистрации.
- В админ-панели отобразить основные метрики (например, активность, участие в референдумах).

### 4.3. Внедрение социальной и геймификационной части

- Настроить рейтинг одобрения, достижения за полезные действия, профили с датой регистрации, списком проектов.
- Внедрить тестовое голосование (референдум) целиком через приложение.

### 4.4. Регулярные обзоры/коррекции

- Каждые 2–3 недели проводить спринт-ретроспективу: анализировать результаты, собирать обратную связь от пользователей и Совета Ассоциации.
- При выявлении серьёзных ошибок или потребностей — оперативно дорабатывать функционал.

## 5. Масштабирование

### 5.1. Переход в полноценный суперапп

- Добавить краудфандинговый модуль, расширенную токеномику (стейкинг, смарт-контракты).
- Полностью закрыть внешние зависимости: все ключевые процессы Ассоциации перевести в приложение, сохраняя при этом их на блокчейне.

### 5.2. Распространение на другие сообщества

- Предложить MVP-платформу другим волюнтаристским сообществам, которые смогут развернуть использовать суперапп с учётом своих нужд.
- Открыть часть кода по модели open-source, чтобы ускорить развитие и привлекать сторонних разработчиков.

### 5.3. Официальная интеграция и поддержка от Ассоциации Монтелиберо

- Совет Ассоциации принимает эту программу и дает ей статус стретагически важной.
- Совет Ассоциации делегирует руководящие функции координатору (Стасу Каркавину), а техническую реализацию исполнителю (Гильдии программистов).
- Совет Ассоциации предоставляет площадку для координации разработки в виде соответствующего топика в Распределенном правлении.
- Активисты Распределенного правления могут обращаться к координатору и исполнителю программы для совместной коллаборации, запросов реализации, обсуждения текущего функционала.
- Участники Ассоциации могут участвовать в поддержке кодовой базы через Распределённое правление в рамках утверждённых Советом программ.
