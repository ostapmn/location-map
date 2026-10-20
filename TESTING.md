# Гайд з тестування від А до Я

Усі команди нижче перевірені на чистій базі. Приклади відповідей наведено скорочено.

## Зміст
1. [Підготовка і запуск](#1-підготовка-і-запуск)
2. [Автоматичні тести](#2-автоматичні-тести)
3. [Ручне тестування: налаштування](#3-ручне-тестування-налаштування)
4. [Сценарій А: користувачі й автентифікація](#4-автентифікація)
5. [Сценарій Б: категорії](#5-категорії)
6. [Сценарій В: локації (CRUD, права, soft delete)](#6-локації)
7. [Сценарій Г: відгуки і голоси](#7-відгуки-і-голоси)
8. [Сценарій Д: рейтинг, популярність, перегляди](#8-рейтинг-популярність-перегляди)
9. [Сценарій Е: пошук, фільтри, сортування, пагінація](#9-пошук-фільтри-сортування-пагінація)
10. [Сценарій Є: кеш списку](#10-кеш-списку)
11. [Сценарій Ж: експорт CSV/JSON](#11-експорт)
12. [Сценарій З: скидання пароля](#12-скидання-пароля)
13. [Swagger](#13-swagger)
14. [Типові проблеми](#14-типові-проблеми)
15. [Прибирання](#15-прибирання)

---

## 1. Підготовка і запуск

Потрібні: Docker Desktop (запущений), `curl`, `python3` (лише для форматування JSON).

```bash
docker compose up --build -d
docker compose ps
```

Очікується: `web`, `db` (healthy), `redis` (healthy) у статусі `Up`. Міграції застосовуються автоматично.

Перевірка, що API живе:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/docs/
```

Очікується `200`.

**Чиста база** (потрібна, щоб id в прикладах збігалися; видаляє всі ваші дані):

```bash
docker compose down -v && docker compose up --build -d
```

Створіть адміністратора (використовується для категорій):

```bash
docker compose exec -e DJANGO_SUPERUSER_USERNAME=admin \
  -e DJANGO_SUPERUSER_EMAIL=admin@example.com \
  -e DJANGO_SUPERUSER_PASSWORD='Admin-pass-123' \
  web python manage.py createsuperuser --noinput
```

Очікується `Superuser created successfully.`

### Демо-дані (необов'язково)

Щоб одразу мати що фільтрувати, сортувати й пагінувати:

```bash
docker compose exec web python manage.py seed_demo           # 30 локацій, відгуки, голоси, перегляди
docker compose exec web python manage.py seed_demo --reset   # видалити й створити заново
```

Створюються користувачі `anna`, `oleh`, `iryna`, `taras`, `maria` (пароль `Demo-pass-123`), 5 категорій, 30 локацій
у різних містах України, ~70 відгуків, голоси та перегляди за останні 14 днів (частина старша за 7 днів,
тому видно різницю в `views_7d`). Повторний запуск без `--reset` нічого не дублює.
Сценарії нижче розраховані на чисту базу з id 1, 2, 3; з демо-даними id інші, тож для розділів 4-8 краще чиста база,
а розділи 9-11 (фільтри, кеш, експорт) зручніше перевіряти саме на демо-даних.

## 2. Автоматичні тести

```bash
docker compose exec web python manage.py test
```

Очікується: `Ran 57 tests ... OK`. Тести використовують пам'ять замість Redis і не чіпають ваші дані.

Окремі модулі:

```bash
docker compose exec web python manage.py test apps.accounts
docker compose exec web python manage.py test apps.locations.tests.test_filters
docker compose exec web python manage.py test apps.locations.tests.test_cache
docker compose exec web python manage.py test apps.locations.tests.test_export
docker compose exec web python manage.py test apps.reviews
```

| Модуль | Що перевіряє |
|---|---|
| `apps.accounts` | реєстрація, вхід, вихід, CSRF, скидання пароля |
| `apps.locations.tests.test_locations` | права, soft delete, валідація координат, категорії |
| `apps.locations.tests.test_stats` | рейтинг, популярність, ліміт переглядів, 7-денне вікно |
| `apps.locations.tests.test_filters` | пошук, фільтри, сортування, пагінація |
| `apps.locations.tests.test_cache` | кеш і його інвалідація |
| `apps.locations.tests.test_export` | експорт CSV/JSON |
| `apps.reviews` | відгуки, дубль, голоси, паралельні дублі (без `500`) |
| `apps.locations.tests.test_seed` | команда `seed_demo`: 30 локацій, ідемпотентність, `--reset` |

## 3. Ручне тестування: налаштування

Вставте в термінал (діє в поточній сесії терміналу). Кожен користувач має свій файл cookie (`*.jar`), тому можна діяти «від імені» різних людей.

```bash
export B=http://localhost:8000/api

# повертає свіжий CSRF-токен для файлу cookie
csrf(){ curl -s -b "$1" -c "$1" $B/auth/csrf/ | python3 -c 'import sys,json;print(json.load(sys.stdin)["csrfToken"])'; }

# call <jar> <METHOD> <path> [curl-опції], наприклад: call /tmp/alice.jar POST /locations/ -d '{...}'
call(){ local jar=$1 m=$2 p=$3; shift 3
  curl -s -b "$jar" -c "$jar" -X "$m" "$B$p" -H 'Content-Type: application/json' \
    -H "X-CSRFToken: $(csrf "$jar")" "$@" -w '  [HTTP %{http_code}]\n'; }

rm -f /tmp/alice.jar /tmp/bob.jar /tmp/admin.jar /tmp/guest.jar
```

Ролі: **guest** (без входу), **alice** (автор локацій), **bob** (рецензент), **admin**.
Читання (`GET`) працює без токена; токен потрібен для `POST/PATCH/DELETE`.

## 4. Автентифікація

**Реєстрація** (одразу логінить, ставить cookie `sessionid`):

```bash
call /tmp/alice.jar POST /auth/register/ -d '{"username":"alice","email":"alice@example.com","password":"Alice-pass-123"}'
call /tmp/bob.jar   POST /auth/register/ -d '{"username":"bob","email":"bob@example.com","password":"Bob-pass-12345"}'
```
Очікується `201` і `{"id":2,"username":"alice",...}` (без пароля у відповіді).

**Помилки:**

```bash
call /tmp/guest.jar POST /auth/register/ -d '{"username":"alice2","email":"alice@example.com","password":"Alice-pass-123"}'
call /tmp/guest.jar POST /auth/register/ -d '{"username":"x","email":"x@example.com","password":"123"}'
```
Очікується `400`: «email already exists» і помилки слабкого пароля.

**Вхід адміна:**

```bash
call /tmp/admin.jar POST /auth/login/ -d '{"username":"admin","password":"Admin-pass-123"}'
call /tmp/guest.jar POST /auth/login/ -d '{"username":"admin","password":"wrong"}'
```
Очікується `200`, потім `400 Invalid credentials`.

**Вихід:** виконайте в самому кінці (див. [розділ 12](#12-скидання-пароля)), щоб не втратити сесію alice:

```bash
call /tmp/alice.jar POST /auth/logout/   # 204
call /tmp/alice.jar POST /auth/logout/   # 403, сесії вже немає
```

**CSRF.** Запит на запис залогіненого користувача без токена має падати:

```bash
curl -s -b /tmp/bob.jar -X POST $B/auth/logout/ -w '  [HTTP %{http_code}]\n'
```
Очікується `403` (`CSRF Failed`). Це нормально: токен потрібен.

## 5. Категорії

```bash
curl -s $B/categories/                                  # гість читає: 200, порожньо
call /tmp/admin.jar POST /categories/ -d '{"name":"Parks"}'   # 201
call /tmp/admin.jar POST /categories/ -d '{"name":"Cafes"}'   # 201
call /tmp/alice.jar POST /categories/ -d '{"name":"Bars"}'    # 403 не адмін
```

**Збережіть id категорій у змінні.** Далі гайд використовує `$PARKS` і `$CAFES`, тож він працює і на чистій базі
(id 1 і 2), і на базі з демо-даними (id інші):

```bash
cat_id(){ curl -s "$B/categories/" | python3 -c 'import sys,json;n=sys.argv[1];print(next(c["id"] for c in json.load(sys.stdin)["results"] if c["name"]==n))' "$1"; }
export PARKS=$(cat_id Parks) CAFES=$(cat_id Cafes)
echo "PARKS=$PARKS CAFES=$CAFES"
```

Далі:

```bash
call /tmp/admin.jar PATCH /categories/$PARKS/ -d '{"name":"Parks & Gardens"}'   # 200
call /tmp/admin.jar PATCH /categories/$PARKS/ -d '{"name":"Parks"}'             # повертаємо назву
```

Видалення категорії, що має локації, дає `400` (перевіряється у [розділі 6](#6-локації)).

## 6. Локації

**Гість не може створювати:**

```bash
call /tmp/guest.jar POST /locations/ -d '{"title":"x"}'
```
Очікується `403 Authentication credentials were not provided`.

**Alice створює дві локації** (автор береться із сесії, а не з тіла запиту):

```bash
call /tmp/alice.jar POST /locations/ -d '{"title":"Central Park","description":"Green and quiet","category":'$PARKS',"address":"Kyiv","latitude":"50.45","longitude":"30.52"}'
call /tmp/alice.jar POST /locations/ -d '{"title":"Blue Cafe","description":"Great coffee near the park","category":'$CAFES',"address":"Lviv","latitude":"49.84","longitude":"24.03"}'
```
Очікується `201`, `"avg_rating":null`, `"popularity":0.0`.

**Збережіть id локацій у змінні** (далі гайд використовує `$LOC1` і `$LOC2`, тож id не обов'язково 1 і 2):

```bash
loc_id(){ curl -s -G "$B/locations/" --data-urlencode "search=$1" | python3 -c 'import sys,json;print(json.load(sys.stdin)["results"][0]["id"])'; }
export LOC1=$(loc_id "Central Park") LOC2=$(loc_id "Blue Cafe")
echo "LOC1=$LOC1 LOC2=$LOC2"
```

**Валідація координат:**

```bash
call /tmp/alice.jar POST /locations/ -d '{"title":"Bad","description":"d","category":'$PARKS',"address":"a","latitude":"95","longitude":"30"}'
call /tmp/alice.jar POST /locations/ -d '{"title":"Bad","description":"d","category":'$PARKS',"address":"a","latitude":"10","longitude":"181"}'
call /tmp/alice.jar POST /locations/ -d '{"title":"Bad","description":"d","category":999,"address":"a","latitude":"10","longitude":"10"}'
```
Очікується `400`: широта ≤ 90, довгота ≤ 180, неіснуюча категорія.

**Права на редагування:**

```bash
call /tmp/bob.jar   PATCH /locations/$LOC1/ -d '{"title":"Hacked"}'                  # 403 чужа
call /tmp/alice.jar PATCH /locations/$LOC1/ -d '{"title":"Central Park v2"}'         # 200 власник
call /tmp/admin.jar PATCH /locations/$LOC1/ -d '{"title":"Central Park"}'            # 200 адмін
call /tmp/bob.jar   DELETE /locations/$LOC1/                                          # 403
```

**Категорія з локаціями не видаляється:**

```bash
call /tmp/admin.jar DELETE /categories/$PARKS/
```
Очікується `400 Category has locations and cannot be deleted.`

**Soft delete** (Blue Cafe, `$LOC2`):

```bash
call /tmp/alice.jar DELETE /locations/$LOC2/        # 204
curl -s $B/locations/$LOC2/ -w '  [HTTP %{http_code}]\n'      # 404
curl -s $B/locations/ | python3 -c 'import sys,json;print(json.load(sys.stdin)["count"])'   # на 1 менше, ніж до видалення
```

Запис лишається в БД з `is_deleted=true`:

```bash
docker compose exec web python manage.py shell -c "
from apps.locations.models import Location
print([(l.id, l.title, l.is_deleted) for l in Location.all_objects.filter(title__in=['Blue Cafe','Central Park'])])"
```
Очікується, що Blue Cafe має `is_deleted=True`, а Central Park `False` (видно також в `/admin/`).

**Обов'язково відновіть Blue Cafe**, бо далі на неї пишуться відгуки:

```bash
docker compose exec web python manage.py shell -c "
from apps.locations.models import Location; Location.all_objects.filter(pk=$LOC2).update(is_deleted=False)"
curl -s $B/locations/$LOC2/ -o /dev/null -w '%{http_code}\n'     # 200
```

## 7. Відгуки і голоси

```bash
call /tmp/bob.jar POST /locations/$LOC1/reviews/ -d '{"rating":5,"comment":"Great"}'    # 201
call /tmp/bob.jar POST /locations/$LOC1/reviews/ -d '{"rating":4}'                      # 400 дубль
call /tmp/bob.jar POST /locations/$LOC2/reviews/ -d '{"rating":6}'                      # 400 рейтинг > 5
call /tmp/bob.jar POST /locations/$LOC2/reviews/ -d '{"rating":0}'                      # 400 рейтинг < 1
call /tmp/alice.jar POST /locations/$LOC1/reviews/ -d '{"rating":3,"comment":"ok"}'     # 201
call /tmp/guest.jar POST /locations/$LOC1/reviews/ -d '{"rating":5}'                    # 403
call /tmp/bob.jar POST /locations/999/reviews/ -d '{"rating":5}'                    # 404
```
Для дубля очікується `{"detail":"You have already reviewed this location."}`.

Збережіть id відгуку bob (`$REV1`):

```bash
export REV1=$(curl -s "$B/locations/$LOC1/reviews/" | python3 -c 'import sys,json;print(next(r["id"] for r in json.load(sys.stdin)["results"] if r["author_username"]=="bob"))')
echo "REV1=$REV1"
```

**Список відгуків** (з лічильниками голосів):

```bash
curl -s $B/locations/$LOC1/reviews/ | python3 -m json.tool
```

**Редагування відгуку:**

```bash
call /tmp/alice.jar PATCH /reviews/$REV1/ -d '{"rating":1}'    # 403 чужий відгук
call /tmp/bob.jar   PATCH /reviews/$REV1/ -d '{"rating":5}'    # 200
```

**Голоси** (like = 1, dislike = -1, один голос на користувача):

```bash
call /tmp/alice.jar POST /reviews/$REV1/vote/ -d '{"value":1}'    # 200, "likes":1
call /tmp/alice.jar POST /reviews/$REV1/vote/ -d '{"value":-1}'   # 400 вже голосували
call /tmp/alice.jar POST /reviews/$REV1/vote/ -d '{"value":5}'    # 400 некоректне значення
call /tmp/guest.jar POST /reviews/$REV1/vote/ -d '{"value":1}'    # 403
```

## 8. Рейтинг, популярність, перегляди

Після відгуків bob=5 і alice=3 у Central Park:

```bash
curl -s $B/locations/$LOC1/ | python3 -c 'import sys,json;d=json.load(sys.stdin);print({k:d[k] for k in ("avg_rating","reviews_count","views_7d","popularity")})'
```
Очікується: `{'avg_rating': 4.0, 'reviews_count': 2, 'views_7d': 1, 'popularity': 10.1}`

Формула: `avg_rating*2 + reviews_count + views_7d*0.1` = 8 + 2 + 0.1.

**Ліміт: один перегляд на годину.** Виконайте ту саму команду ще 2 рази: `views_7d` лишається `1`.

**Лічильник у Redis** (кеш лежить у базі `-n 1`):

```bash
docker compose exec redis redis-cli -n 1 --scan --pattern '*view:*'
```
Очікується ключ типу `:1:view:1:ip192.168.65.1`. Для залогіненого це `view:1:u<id>`.

```bash
docker compose exec redis redis-cli -n 1 ttl ':1:view:1:ip192.168.65.1'
```
Очікується число близько `3600` (підставте свій ключ з попередньої команди).

**Залогінений рахується окремо від гостя:**

```bash
curl -s -b /tmp/bob.jar $B/locations/$LOC1/ | python3 -c 'import sys,json;print(json.load(sys.stdin)["views_7d"])'
```
Очікується `2`.

**Скидання ліміту** (як ніби минула година):

```bash
docker compose exec redis redis-cli -n 1 flushdb
curl -s $B/locations/$LOC1/ | python3 -c 'import sys,json;print(json.load(sys.stdin)["views_7d"])'   # 3
```

**Список не рахує перегляди:** `GET /locations/` не змінює `views_7d`.

**Вікно 7 днів:** старий перегляд не враховується.

```bash
docker compose exec web python manage.py shell -c "
from datetime import timedelta
from django.utils import timezone
from apps.locations.models import Location, LocationView
l = Location.objects.get(pk=1)
v = LocationView.objects.create(location=l)
LocationView.objects.filter(pk=v.pk).update(created_at=timezone.now() - timedelta(days=8))
print('total', l.views.count(), '| views_7d', Location.objects.with_stats().get(pk=1).views_7d)"
```
Очікується, що `total` на 1 більший за `views_7d` (старий запис не рахується).

**Рейтинг не зберігається:** у моделі `Location` немає полів `rating`/`popularity`:

```bash
docker compose exec web python manage.py shell -c "
print([f.name for f in __import__('apps.locations.models', fromlist=['Location']).Location._meta.fields])"
```

## 9. Пошук, фільтри, сортування, пагінація

Для зручності:

```bash
q(){ curl -s "$B/locations/?$1" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d if "results" not in d else (d["count"],[(r["title"],r["avg_rating"],r["popularity"]) for r in d["results"]]))'; }
```

Значення нижче отримано на чистій базі після розділів 4-8 і `seed_demo` (демо-дані детерміновані). Якщо ви
пропустили розділи 4-8, числа можуть відрізнятися, але правила ті самі.

| Запит | Очікування |
|---|---|
| `q 'search=coffee'` | 1 запис: Blue Cafe (шукає в назві й описі, без урахування регістру) |
| `q 'search=park'` | 2 записи: Central Park (у назві) і Blue Cafe (в описі) |
| `q 'search=парк'` | 5 записів із кирилицею (регістр теж не важливий) |
| `q "category=$CAFES"` | лише Blue Cafe |
| `q "category=$PARKS"` | лише Central Park |
| `q 'author=2'` | 2 локації alice (id автора можна побачити у відповіді) |
| `q 'min_rating=4'` | 11 записів, у всіх `avg_rating >= 4`; локації без відгуків не потрапляють |
| `q 'max_rating=3'` | 6 записів, у всіх `avg_rating <= 3` |
| `q 'ordering=-popularity'` | першим «Кафе «Старе місто»» (15.7), далі за спаданням |
| `q 'ordering=popularity'` | першими найменш популярні (0.0), далі за зростанням |
| `q 'ordering=-created_at'` | найновіші першими («Парк «Нивки»» серед демо-даних) |
| `q 'ordering=-avg_rating'` | спочатку 5.0, локації без відгуків в кінці |
| `q 'ordering=avg_rating'` | спочатку найнижчий рейтинг (2.0), локації без відгуків знову в кінці |
| `q 'ordering=title'` | `400`: `Select a valid choice` (дозволено лише `created_at`, `avg_rating`, `popularity`) |
| `q 'min_rating=abc'` | `400`: `Enter a number.` |
| `q "search=park&category=$PARKS&min_rating=3"` | 1 запис (Central Park): фільтри комбінуються |

**Пагінація** (10 на сторінку). Створіть 12 локацій:

```bash
for i in $(seq 1 12); do call /tmp/alice.jar POST /locations/ -d "{\"title\":\"Extra $i\",\"description\":\"d\",\"category\":$PARKS,\"address\":\"a\",\"latitude\":\"1\",\"longitude\":\"1\"}" >/dev/null; done
curl -s "$B/locations/" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("count",d["count"],"on page",len(d["results"]),"next",d["next"],"prev",d["previous"])'
curl -s "$B/locations/?page=2" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("on page",len(d["results"]),"next",d["next"],"prev",d["previous"])'
curl -s "$B/locations/?page=99" -w '  [HTTP %{http_code}]\n'
```
Очікується: `count` = було + 12 (на демо-даних 32 + 12 = 44), на сторінці 10 записів, `next` вказує на `?page=2`,
`previous` порожній на першій сторінці. На останній сторінці лишок записів і `next: null`.
Неіснуюча сторінка дає `404 Invalid page.`

Сторінки не перетинаються (кожен запис рівно один раз), навіть при сортуванні за популярністю, де багато однакових значень:

```bash
python3 - <<'EOF'
import json, urllib.request
ids, page = [], 1
while True:
    d = json.load(urllib.request.urlopen(f"http://localhost:8000/api/locations/?ordering=-popularity&page={page}"))
    ids += [r["id"] for r in d["results"]]
    if not d["next"]: break
    page += 1
print("total", len(ids), "unique", len(set(ids)))
EOF
```
Очікується однакові числа `total` і `unique`.

## 10. Кеш списку

Кеш зберігається в Redis 5 хвилин. Ключ містить версію; будь-яка зміна даних міняє версію.

```bash
docker compose exec redis redis-cli -n 1 flushdb
curl -s -o /dev/null $B/locations/
docker compose exec redis redis-cli -n 1 --scan --pattern '*locations:*'
```
Очікується два ключі: `:1:locations:version` та `:1:locations:list:v1:<хеш>`.

```bash
docker compose exec redis redis-cli -n 1 ttl ":1:locations:list:v1:<хеш із попередньої команди>"
```
Очікується `300` (секунд).

**Окремі ключі для різних параметрів:**

```bash
curl -s -o /dev/null "$B/locations/?search=park"
docker compose exec redis redis-cli -n 1 --scan --pattern '*locations:list:*'    # тепер їх два (по одному на кожну комбінацію параметрів)
```

**Інвалідація.** Запам'ятайте версію, змініть дані, перевірте:

```bash
docker compose exec redis redis-cli -n 1 get ':1:locations:version'
call /tmp/admin.jar PATCH /locations/$LOC1/ -d '{"title":"Central Park (cache test)"}' >/dev/null
docker compose exec redis redis-cli -n 1 get ':1:locations:version'    # змінилась на велике число
curl -s $B/locations/ | python3 -c 'import sys,json;print([r["title"] for r in json.load(sys.stdin)["results"]])'
```
Очікується, що нова назва видна одразу.

Те саме для інших подій (перевіряйте, що версія змінюється і список свіжий):

| Дія | Команда |
|---|---|
| Створення локації | `call /tmp/alice.jar POST /locations/ -d '{...}'` |
| Видалення локації | `call /tmp/alice.jar DELETE /locations/<id>/` |
| Новий відгук | `call /tmp/bob.jar POST /locations/<id>/reviews/ -d '{"rating":4}'` (рейтинг у списку оновиться) |
| Зміна/видалення відгуку | `call /tmp/bob.jar PATCH /reviews/<id>/ -d '{"rating":2}'` |

**Після зміни коду відповіді API очищайте кеш**, бо старі відповіді живуть до 5 хвилин:

```bash
docker compose exec redis redis-cli -n 1 flushdb
```

**Що кеш НЕ скидає:** перегляди (`GET /locations/<id>/`) і голоси. Тому `views_7d` у списку може відставати до 5 хвилин, а в деталях завжди точний. Це свідоме рішення.

## 11. Експорт

```bash
curl -s "$B/locations/export/?format=csv"
curl -s "$B/locations/export/?format=json" | python3 -m json.tool | head -30
curl -s -D- -o /dev/null "$B/locations/export/?format=csv" | grep -i content-
```

Очікується: заголовок `Content-Disposition: attachment; filename="locations.csv"`, колонки
`id,title,description,category,address,latitude,longitude,author,avg_rating,reviews_count,views_7d,popularity,created_at,updated_at`.

**Збереження у файл:**

```bash
curl -OJ "$B/locations/export/?format=csv"      # locations.csv
curl -OJ "$B/locations/export/?format=json"     # locations.json
```
Відкрийте файли: кирилиця читається, категорія і автор показані назвою. Видалені (soft delete) локації в експорті відсутні.

**Ті самі фільтри, що й у списку, без пагінації:**

```bash
curl -s "$B/locations/export/?format=csv&min_rating=4" | wc -l                # рядків = кількість у списку з min_rating=4, плюс 1 заголовок
curl -s "$B/locations/export/?format=json&ordering=-popularity" | head -c 300
curl -s "$B/locations/export/?format=csv" | wc -l                            # усі записи + 1 заголовок (більше 10, тобто без пагінації)
```

**Помилки:**

```bash
curl -s "$B/locations/export/?format=xml" -w '  [HTTP %{http_code}]\n'        # 400
curl -s "$B/locations/export/?min_rating=abc" -w '  [HTTP %{http_code}]\n'    # 400
```

**Захист від CSV-ін'єкцій:** назва, що починається з `=`, експортується з апострофом.

```bash
call /tmp/alice.jar POST /locations/ -d '{"title":"=HYPERLINK(1)","description":"d","category":'$PARKS',"address":"a","latitude":"1","longitude":"1"}' >/dev/null
curl -s "$B/locations/export/?format=csv" | grep HYPERLINK
```
Очікується `'=HYPERLINK(1)`.

## 12. Скидання пароля

Крок 1: запит на скидання. Відповідь завжди `204`, навіть якщо email не існує (щоб не розкривати акаунти).

```bash
call /tmp/guest.jar POST /auth/password-reset/ -d '{"email":"bob@example.com"}'
call /tmp/guest.jar POST /auth/password-reset/ -d '{"email":"nobody@example.com"}'
```

Крок 2: лист друкується в консоль (EMAIL_BACKEND=console):

```bash
docker compose logs web | grep -E "uid:|token:" | tail -2
```
Очікується `Subject: Password reset`, `To: bob@example.com`, `uid: Mw` (у вас може бути інший), `token: ...`. Для `nobody@example.com` листа немає.

Крок 3: підтвердження. Підставте свої значення:

```bash
call /tmp/guest.jar POST /auth/password-reset/confirm/ -d '{"uid":"Mw","token":"<token>","new_password":"Bob-new-pass-777"}'   # 204
call /tmp/guest.jar POST /auth/password-reset/confirm/ -d '{"uid":"Mw","token":"<token>","new_password":"Other-pass-8888"}'    # 400 токен одноразовий
call /tmp/guest.jar POST /auth/password-reset/confirm/ -d '{"uid":"Mw","token":"bad","new_password":"Bob-new-pass-777"}'       # 400
```

Слабкий новий пароль відхиляється (`400` зі списком вимог).

Крок 4: старий пароль більше не діє, новий працює:

```bash
call /tmp/guest.jar POST /auth/login/ -d '{"username":"bob","password":"Bob-pass-12345"}'      # 400
call /tmp/bobnew.jar POST /auth/login/ -d '{"username":"bob","password":"Bob-new-pass-777"}'   # 200
```

**Вихід:**

```bash
call /tmp/alice.jar POST /auth/logout/    # 204
call /tmp/alice.jar POST /auth/logout/    # 403, сесії вже немає
```

## 13. Swagger

Відкрийте <http://localhost:8000/api/docs/>. Тут можна клацати «Try it out» для всіх ендпоінтів.

Для запитів на запис потрібен вхід:
1. Виконайте `POST /api/auth/login/`.
2. **Обов'язково оновіть сторінку (F5)**: після входу Django міняє CSRF-токен, а Swagger підставляє токен лише при завантаженні сторінки. Без F5 буде `403 CSRF token incorrect`.
3. Далі виконуйте `POST /api/locations/` тощо.

Для категорій потрібна сесія адміна. Увійти можна й через `/admin/`.

## 14. Типові проблеми

| Симптом | Причина і рішення |
|---|---|
| `Cannot connect to the Docker daemon` | запустіть Docker Desktop |
| Контейнери зупинені | `docker compose up -d` |
| `403 CSRF Failed` | потрібен заголовок `X-CSRFToken` (функція `call` додає його); у Swagger оновіть сторінку |
| `403 Authentication credentials were not provided` | ви не залогінені або cookie-файл порожній |
| `404` на локацію, яку створювали | вона видалена (soft delete) або id інший на непорожній базі |
| Порт 8000 зайнятий | змініть мапінг портів у `docker-compose.yml` (`"8001:8000"`) і `B` |
| Не збігаються id у прикладах | база не чиста, див. розділ 1 (`down -v`) |
| Нічого не видно в Redis | кеш лежить у базі 1: `redis-cli -n 1` |
| Тести падають з помилкою БД | переконайтеся, що `db` у статусі healthy |

## 15. Прибирання

Зупинити, зберігши дані:

```bash
docker compose down
```

Зупинити й видалити всі дані (БД і Redis):

```bash
docker compose down -v
```

Видалити тимчасові файли cookie та експорту:

```bash
rm -f /tmp/alice.jar /tmp/bob.jar /tmp/bobnew.jar /tmp/admin.jar /tmp/guest.jar locations.csv locations.json
```
