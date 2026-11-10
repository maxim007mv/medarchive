# 02. Исследование: правила, на которых стоит продукт

Каждое правило ниже сформулировано как стандарт команды. Рядом указан источник, который был прочитан при подготовке пакета (10.11.2026). Правило без внешнего источника помечено «стандарт команды»: его основание объяснено в тексте.

## 1. Источники

| # | Источник | Что взяли |
|---|---|---|
| S1 | NN/g, «Modal & Nonmodal Dialogs: When (& When Not) to Use Them», T. Fessenden, 2017. https://www.nngroup.com/articles/modal-nonmodal-dialog/ | Модальное окно только для критичных предупреждений и для данных, без которых процесс не продолжить; ошибки формы показывать у поля, а не в модалке |
| S2 | NN/g, «Confirmation Dialogs Can Prevent User Errors, If Not Overused», J. Nielsen, 2018, пересмотрено 07.08.2026. https://www.nngroup.com/articles/confirmation-dialog/ | Подтверждать только необратимое; называть объект; кнопки с глаголом вместо «Да / Нет»; без ответа по умолчанию |
| S3 | NN/g, «Designing Empty States in Complex Applications», K. Kaplan, 2021. https://www.nngroup.com/articles/empty-state-interface-design/ | Пустое состояние сообщает статус, учит и даёт прямой путь к действию; нельзя показывать «Нет записей» до окончания загрузки |
| S4 | NN/g, «Dark Mode vs. Light Mode: Which Is Better?», R. Budiu, 2020. https://www.nngroup.com/articles/dark-mode/ | Светлая тема по умолчанию для людей с нормальным зрением; тёмную давать как выбор и уважать системную настройку |
| S5 | NN/g, «Skeleton Screens 101», S. Tankala, 2023, пересмотрено 02.09.2026. https://www.nngroup.com/articles/skeleton-screens/ | Скелетон только для загрузки целой страницы до 10 с; меньше 1 с ничего не показывать; для загрузки файла нужен прогресс-бар |
| S6 | NN/g, «Response Times: The 3 Important Limits», J. Nielsen, 1993. https://www.nngroup.com/articles/response-times-3-important-limits/ | Пороги 0,1 с, 1 с, 10 с; после 10 с нужен процент и возможность отменить |
| S7 | NN/g, «Error-Message Guidelines», T. Neusesser, E. Sunwall, 2023. https://www.nngroup.com/articles/error-message-guidelines/ | Ошибка рядом с источником, не только цветом, человеческим языком, без обвинения, с советом и сохранением ввода; не показывать ошибку до попытки ввода |
| S8 | Baymard Institute, «Display “Applied Filters” in an Overview», K. Reeves, обновлено 13.05.2026. https://baymard.com/blog/how-to-design-applied-filters | Применённые фильтры показывать отдельной строкой над списком, каждый снимается одним кликом, есть «Сбросить всё»; не ограничиваться счётчиком «Фильтры (2)» |
| S9 | W3C, Understanding WCAG 2.2 SC 1.4.3 Contrast (Minimum), обновлено 04.10.2026. https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html | Текст 4,5:1, крупный текст 3:1; формула относительной яркости; пороги не округлять |
| S10 | W3C, Understanding WCAG 2.2 SC 2.5.8 Target Size (Minimum), обновлено 02.11.2026. https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html | Цель нажатия не меньше 24 x 24 CSS px; для важных элементов ориентир 44 x 44 |
| S11 | Material Design 3, «Color system: how the system works». https://m3.material.io/styles/color/system/how-the-system-works | Цвет через семантические роли (primary, on-primary, surface), одни роли для светлой и тёмной темы; пары тонов с гарантированным контрастом 3:1 и 7:1 |
| S12 | MDN, «Storage quotas and eviction criteria». https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria | Данные в браузере по умолчанию best-effort, Safari удаляет данные сайта без взаимодействия за 7 дней; в приватном режиме данные стираются. Вывод: архив документов нельзя держать только в IndexedDB |
| S13 | MDN, «prefers-reduced-motion». https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion | Сокращать движение при системной настройке, заменять масштаб и сдвиг на растворение |
| S14 | Supabase Docs, «Storage Access Control». https://supabase.com/docs/guides/storage/security/access-control | Без политик RLS загрузка в bucket запрещена; сервисный ключ обходит RLS и хранится только на сервере |
| S15 | Medeo, репозиторий DNFDEVS/medeo-font и спецификация prtner.ai/font. https://github.com/DNFDEVS/medeo-font , https://prtner.ai/font/ru/ | Семейство существует, OFL 1.1, Sans + Mono + Pixel + Serif, кириллица, оси wght 100 до 900 и opsz 14 до 32, npm `medeo-font` |
| S16 | IETF RFC 9457 «Problem Details for HTTP APIs», 2023. https://www.rfc-editor.org/rfc/rfc9457.html | Формат ошибок `application/problem+json`: `type` (абсолютный URI, документация по нему), `title` (не меняется от случая к случаю), `status` совпадает с кодом ответа, расширения вроде `errors[]` с `pointer`; не раскрывать внутренности; тип может предписывать `Retry-After` |
| S17 | IETF RFC 9110 «HTTP Semantics», 2022. https://www.rfc-editor.org/rfc/rfc9110.html | ETag как валидатор против «lost update»; `If-Match` со строгим сравнением (13.1.1); 412 при несовпадении; `Retry-After` (10.2.3); идемпотентность методов |
| S18 | IETF RFC 6585 «Additional HTTP Status Codes», 2012. https://www.rfc-editor.org/rfc/rfc6585.html | 428 Precondition Required (требовать `If-Match`), 429 Too Many Requests c необязательным `Retry-After` |
| S19 | IETF draft-ietf-httpapi-idempotency-key-header-08, 22.10.2026. https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/ | Заголовок `Idempotency-Key` (UUID), отпечаток запроса; нет ключа = 400, тот же ключ с другим телом = 422, повтор во время обработки = 409; составной ключ поиска; срок жизни ключа публикуется |
| S20 | IETF draft-ietf-httpapi-ratelimit-headers. https://datatracker.ietf.org/doc/draft-ietf-httpapi-ratelimit-headers/ | Поля `RateLimit-Policy` и `RateLimit`: клиент видит квоту заранее и не доводит до 429 |
| S21 | Google AIP-158 «Pagination». https://google.aip.dev/158 | Пагинация с первого дня; `page_size` необязателен, превышение максимума урезается; `page_token` непрозрачный (base64 недостаточно), не даёт прав; другие параметры при листании должны совпадать, иначе ошибка; пустой `next_page_token` = конец |
| S22 | Google AIP-132 «Standard methods: List». https://google.aip.dev/132 | Поля `filter` и `order_by` в запросе списка; никаких других обязательных полей |
| S23 | Google AIP-185 «API Versioning». https://google.aip.dev/185 | Мажорная версия первой частью пути REST (`v1`), без минорных и патч-версий |
| S24 | Google AIP-154 «Resource freshness validation». https://google.aip.dev/154 | Несовпавший etag = ошибка ABORTED; без etag запрос по умолчанию допустим, но сервисы со строгой консистентностью могут требовать |
| S25 | Zalando RESTful API Guidelines. https://opensource.zalando.com/restful-api-guidelines/ | Ресурсы во множественном числе, kebab-case в путях, URL без глаголов, snake_case в параметрах; MUST support problem JSON; MUST use 429 with headers; SHOULD prefer cursor-based pagination; SHOULD avoid total count; не ломать обратную совместимость |
| S26 | Microsoft Azure REST API Guidelines. https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md | Заголовки kebab-case, `retry-after`, `maxpagesize`; повторяемость POST и оптимистичная конкурентность как условие отказоустойчивых клиентов |
| S27 | OWASP API Security Top 10, 2023. https://owasp.org/API-Security/editions/2023/en/0x11-t10/ | API1 BOLA, API2 Broken Authentication, API3 Property Level Authorization, API4 Unrestricted Resource Consumption, API5 Function Level Authorization, API6 Sensitive Business Flows, API7 SSRF, API8 Misconfiguration, API9 Inventory, API10 Unsafe Consumption |
| S28 | OWASP Session Management Cheat Sheet. https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html | Обязательные idle и absolute timeout, инвалидация на сервере, атрибуты cookie |
| S29 | OWASP File Upload Cheat Sheet. https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html | Список разрешённых расширений, проверка Content-Type и сигнатуры файла, безопасное имя, хранение вне веб-корня, лимиты загрузки и скачивания |
| S30 | IETF RFC 8725 «JSON Web Token Best Current Practices». https://www.rfc-editor.org/rfc/rfc8725.html | Атаки подменой `alg` (`none`, RS256 → HS256); фиксировать список алгоритмов |
| S31 | IETF draft-ietf-oauth-browser-based-apps, раздел 6.1 «Backend For Frontend». https://datatracker.ietf.org/doc/html/draft-ietf-oauth-browser-based-apps | BFF держит токены в серверной сессии на cookie, токены не попадают в браузерный код; при XSS атакующий не может вынести токены |
| S32 | PostgreSQL 17 Documentation, 5.9 «Row Security Policies». https://www.postgresql.org/docs/17/ddl-rowsecurity.html | Без политики действует default-deny; владелец обходит RLS, если не `FORCE ROW LEVEL SECURITY`; `BYPASSRLS` |
| S33 | PostgreSQL 17 Documentation, F.35 «pg_trgm». https://www.postgresql.org/docs/17/pgtrgm.html | GIN/GiST индексы триграмм ускоряют `LIKE`, `ILIKE`, регулярные выражения |
| S34 | PostgreSQL 17 Documentation, 11.8 «Partial Indexes». https://www.postgresql.org/docs/17/indexes-partial.html | Индекс по подмножеству строк, исключение частых значений |
| S35 | PostgreSQL 17 Documentation, F.26 «pgcrypto», раздел Security Limitations. https://www.postgresql.org/docs/17/pgcrypto.html | Функции pgcrypto выполняются на сервере, данные и пароли идут между клиентом и сервером в открытом виде |
| S36 | PostgreSQL 17 Documentation, 25.3 «Continuous Archiving and Point-in-Time Recovery». https://www.postgresql.org/docs/17/continuous-archiving.html | Базовая копия + архив WAL, восстановление на момент времени |
| S37 | PostgreSQL 17 Documentation, 14.1 «Using EXPLAIN». https://www.postgresql.org/docs/17/using-explain.html | Чтение планов, `ANALYZE`, `BUFFERS` |
| S38 | PostgreSQL 18 Documentation, 9.14 «UUID Functions». https://www.postgresql.org/docs/18/functions-uuid.html | `uuidv7()`: UUID версии 7, упорядоченный по времени |
| S39 | M. Winand, «We need tool support for keyset pagination», use-the-index-luke.com. https://use-the-index-luke.com/no-offset | Seek method (keyset) не дрейфует при вставках и быстрее OFFSET |
| S40 | SQLAlchemy 2.0 Documentation, «Relationship Loading Techniques». https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html | `selectinload` одним дополнительным запросом с `IN`; `raiseload` превращает случайную ленивую загрузку в ошибку |
| S41 | 152-ФЗ «О персональных данных», ст. 10 (КонсультантПлюс, Гарант, ред. от 26.07.2026). https://www.consultant.ru/document/cons_doc_LAW_61801/26edb2934b899bf9c74c3a8f7e574651c6565e6d/ | Сведения о состоянии здоровья = специальная категория; обработка допускается при согласии субъекта в письменной форме (ч. 2 п. 1); к письменной форме приравнено согласие, подписанное электронной подписью (комментарий) |
| S42 | 152-ФЗ, ст. 18 ч. 5 (ред. 28.02.2025 N 23-ФЗ). https://www.consultant.ru/document/cons_doc_LAW_61801/cbf4e15b7c330f9372e876cdf2bc928bad7950ef/ | Запись, хранение, обновление ПДн граждан РФ с использованием баз данных за пределами РФ не допускаются |
| S43 | Постановление Правительства РФ от 01.11.2012 № 1119, п. 10 е и п. 11 в. https://www.consultant.ru/document/cons_doc_LAW_137356/8c86cf6357879e861790a8a7ca8bea4227d56c72/ | Спецкатегории + угрозы 3-го типа: менее 100 000 субъектов = 3-й уровень защищённости, более 100 000 = 2-й |
| S44 | Yandex Cloud, «Шифрование по схеме envelope encryption» (KMS), обновлено 27.02.2025. https://yandex.cloud/ru/docs/kms/concepts/envelope | DEK + KEK; лимит прямого encrypt 32 КБ; открытый DEK только на время операции; разные DEK для разных данных; рекомендованы Tink или AWS Encryption SDK |
| S45 | Yandex Cloud, «Получить подписанную ссылку на загрузку объекта» и «Загрузка файла с помощью HTML формы» (Object Storage). https://yandex.cloud/ru/docs/storage/operations/objects/link-for-upload , https://yandex.cloud/ru/docs/storage/concepts/presigned-post-forms | Presigned POST с политикой `content-length-range`; при превышении `EntityTooLarge`; срок ссылки нельзя продлить |
| S46 | Yandex Cloud, «Резервные копии PostgreSQL» (Managed Service for PostgreSQL). https://yandex.cloud/ru/docs/managed-postgresql/concepts/backup | PITR включён по умолчанию, восстановление в новый кластер; копии 7 дней по умолчанию, 7 до 60 |
| S47 | AWS, «Uploading objects with presigned URLs» (Amazon S3 User Guide). https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html | Presigned URL даёт ограниченную по времени загрузку без раздачи ключей доступа |
| S48 | 152-ФЗ, ст. 5 ч. 7 (текст закона на сайте Минтруда России). https://mintrud.gov.ru/docs/laws/130 | Хранение ПДн не дольше, чем этого требуют цели обработки |
| S49 | OWASP ASVS 5.0, 17 глав (V1 до V17). https://github.com/OWASP/ASVS/tree/master/5.0/en | Структура проверочных требований: V2 Validation, V3 Web Frontend, V4 API, V5 File Handling, V6 Authentication, V7 Session, V8 Authorization, V11 Cryptography, V13 Configuration, V14 Data Protection, V16 Logging |

## 2. Правила интерфейса, принятые как стандарт команды

### 2.1. Темы и поверхности
1. **Глубже значит темнее, выше значит светлее, в обеих темах.** Фон страницы на тон темнее карточек: светлая `#F4F4F5` под белыми `#FFFFFF`, тёмная `#0A0A0A` под `#171717`, модальные окна `#1F1F22`. Так карточки отделяются без линий (S11: роли surface; стандарт команды).
2. **Никакого бежевого фона.** Тёплая подложка в рабочем интерфейсе читается как блёклая и шаблонная. Фон нейтрально-серый.
3. **Светлая тема по умолчанию, тёмная по `prefers-color-scheme` и переключателю, выбор запоминается** (S4).
4. **96 / 4.** Около 96% площади экрана нейтральны, акцент занимает не больше 4%: логотип, полоска 2 px у выбранного сегмента, фокус, ссылки. Тёмная тема без точечного акцента складывает соседние карточки в одну серую стену.
5. **Цвет только как сигнал**: бренд для выбранного и фокуса, зелёный для успеха, красный для ошибки и разрушительных действий, янтарный для «дата не указана». Главная кнопка почти чёрная `#171717`, в тёмной теме почти белая `#F4F4F5`. Радуги из кнопок нет (S11).

### 2.2. Активное и неактивное
6. **Активный и заблокированный элементы никогда не делят один серый.** Активный сегмент: белая плашка, чёрный текст `#171717`, полоска 2 px бренд-цвета снизу. Заблокированная кнопка: заливка `#EBEBED`, текст `#6B6B74`, без тени. В тёмной теме активный: заливка заметно светлее фона, белый текст, полоска 2 px акцента.
7. Блокированная кнопка всегда сопровождается причиной рядом («Заполните название») или заменяется валидацией по нажатию (S7).

### 2.3. Модальные окна
8. Модалка только для: подтверждения необратимого (удаление), короткой формы добавления, выбора объёма экспорта (S1). Ошибки формы показываются у поля внутри формы, не отдельной модалкой (S1, S7).
9. Заголовок «Глагол + объект?»: «Удалить документ?». Текст выровнен влево, называет объект и прямо говорит «без возможности восстановления» (S2).
10. Кнопки: слева «Отмена», справа глагол действия. Для разрушительного действия кнопка красная. Ни одна кнопка не в фокусе по умолчанию для удаления (S2). Крестик закрытия в правом верхнем углу. Большой иконки-вопроса нет.
11. Esc и клик по подложке закрывают модалку без действия, кроме формы с введёнными данными: там спрашиваем «Закрыть без сохранения?».

### 2.4. Формы и выбор
12. **2 до 4 вариантов показываем радиокнопками или сегментом, выпадающий список только с 5 вариантов** или при нехватке места. Тип документа (3 варианта) = сегмент с ролью `radiogroup`. Объём экспорта (3 варианта) = радио-строки.
13. **Вся строка выбора кликабельна** и растянута на ширину контейнера, не только кружок.
14. Дату вводим текстовым полем с маской `дд.мм.гггг` и календарём как дополнением; для известной даты из бумаги ввод с клавиатуры быстрее, чем пролистывание календаря (стандарт команды).
15. Ошибки появляются после попытки сохранить или после ухода с заполненного поля, не при первом фокусе (S7).

### 2.5. Сетка и ритм
16. **Сетка 8 px**: отступы раскладки 8 / 16 / 24 / 32 / 48. Внутри компонентов допустимы 4, 6, 10, 12. Нечётных значений нет.
17. **Закон близости**: заголовок и его текст 8, текст и кнопка 16, между блоками 24 до 32. Каждый уровень вложенности задаёт свой gap, а не наследует отступы потомков.

### 2.6. Кнопки и цели нажатия
18. Главная кнопка: заливка `#171717`, текст белый, скругление 12 px, высота 40 (48 на мобильном). На тёмной кнопке никогда не бывает тёмного текста. Неоморфизм запрещён: он проваливает контраст границ (S9, SC 1.4.11 по аналогии).
19. Минимальная цель 24 x 24 px, иконки-кнопки 32 и 40 px, на мобильном главные действия 48 px (S10).
20. Строка списка кликабельна целиком (открывает документ); чекбокс и меню «...» перехватывают клик отдельно.

### 2.7. Мобильный и безопасные зоны
21. Ни одна кнопка не прижимается к нижнему краю. Интерактив остаётся внутри безопасной зоны с запасом сверху; фон и подложки уходят под края. В коде только `env(safe-area-inset-*)` и `viewport-fit=cover`, никаких фиксированных 34 px.

### 2.8. Цифры и сводки
22. Числа не выводим голыми: у каждого счётчика есть подпись («6 документов», «Найдено 2»). Если однажды появится сводка архива, категории делятся вкладками, данные во времени показываются графиком, а не таблицей. Даты и размеры набираются Medeo Mono с табличными цифрами, чтобы столбцы не прыгали.

### 2.9. Загрузка и ожидание
23. До 1 с ничего не показываем, 1 до 10 с скелетон страницы или спиннер в кнопке, загрузка файла всегда с процентом (S5, S6).
24. «Ничего не найдено» показываем только после ответа сервера, никогда во время загрузки (S3).

### 2.10. Фильтры
25. Применённые фильтры видны чипами над списком: «Поиск: анализ», «Дата документа: 01.04.2026 – 30.04.2026». У каждого крестик, рядом «Сбросить всё», слева «2 из 6» (S8).
26. Документы без даты при фильтре по дате документа не скрываются молча: под списком подсказка с числом и ссылкой «Показать».

## 3. Цветовые пары, которые рассматривали и отвергли

Для акцента проверялись выразительные пары «цвет по цвету» (коралловый по графиту, лавандовый по баклажану, ультрамарин по персиковому, горчичный по сливовому). Для медицинского архива, где главное содержание это документы, они перетягивают внимание и спорят с цветами типов документов. Решение: монохромный интерфейс, один спокойный бирюзовый акцент `#0F766E` / `#2DD4BF`. Если продукт однажды будет оптимизироваться под конверсию (лендинг), допускается синий акцент на главной кнопке; внутри архива нет.

## 4. Почему не храним всё в браузере

Задание разрешает «выбранное окружение». Самый быстрый путь (IndexedDB + OPFS) проваливает главный критерий «сохраняется после повторного открытия» в реальных условиях проверки: данные best-effort, Safari стирает их через 7 дней без взаимодействия, приватное окно стирает их сразу, другой браузер их не видит (S12). Поэтому файлы и метаданные хранятся на сервере, а браузер держит только кэш для чтения.
| S50 | FastAPI, «Features»: OpenAPI и JSON Schema из типов, Pydantic-валидация, DI, OAuth2 и cookie-сессии. https://fastapi.tiangolo.com/features/ |
| S51 | OWASP Password Storage Cheat Sheet: Argon2id, минимум m=19 MiB, t=2, p=1. https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html |
| S52 | Google Tink, «Streaming AEAD»: сегментное шифрование файлов, associated data против переноса шифртекста между пользователями, AES256_GCM_HKDF_1MB. https://developers.google.com/tink/streaming-aead |
| S53 | Radix UI Primitives, «Dialog»: фокус-ловушка, Esc, возврат фокуса на триггер, паттерн WAI-ARIA Dialog. https://www.radix-ui.com/primitives/docs/components/dialog |
| S54 | Next.js Docs, «Font» (next/font/local): самохостинг шрифта без внешних запросов, display swap, adjustFontFallback против сдвига вёрстки. https://nextjs.org/docs/app/api-reference/components/font |
| S55 | OWASP Threat Modeling Cheat Sheet: четыре вопроса, STRIDE, ответы Mitigate / Eliminate / Transfer / Accept, LINDDUN для приватности. https://cheatsheetseries.owasp.org/cheatsheets/Threat_Modeling_Cheat_Sheet.html |
| S56 | TanStack Query, «Optimistic Updates»: onMutate со снимком и откатом в onError, инвалидация в onSettled. https://tanstack.com/query/latest/docs/framework/react/guides/optimistic-updates |
| S57 | 152-ФЗ, ст. 22 «Уведомление об обработке персональных данных» (КонсультантПлюс; полный текст сверен по bazanpa.ru): ч. 1 оператор уведомляет Роскомнадзор до начала обработки; ч. 3 состав уведомления, в т. ч. п. 7 меры и шифровальные средства, п. 10 трансграничная передача, п. 10.1 место нахождения БД с ПДн граждан РФ; ч. 3.1 категории ПДн и субъектов по каждой цели. https://www.consultant.ru/document/cons_doc_LAW_61801/d996966e22e1320c9de1ab82d9f6be12c3d9d765/ , https://bazanpa.ru/fz-o-persdannyh/glava4/statya22/ |
