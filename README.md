# Location Map API

REST API (Django REST Framework) where users add interesting locations, review and rate them,
and see the most popular places. Stack: Django, DRF, PostgreSQL, Redis, django-filter, pandas, Docker Compose.

## Run

```bash
docker compose up --build
```

- API root: <http://localhost:8000/api/>
- Swagger UI: <http://localhost:8000/api/docs/>
- Admin: <http://localhost:8000/admin/> (create an admin first, see below)

Migrations are applied automatically on start. Settings come from environment variables
(see `.env.example`; Compose reads it by default).

```bash
docker compose exec web python manage.py createsuperuser   # admin: manages categories
docker compose exec web python manage.py test              # run the API tests
```

## Endpoints

| Method | URL | Notes |
|---|---|---|
| GET | `/api/auth/csrf/` | returns CSRF token + sets cookie |
| POST | `/api/auth/register/` `login/` `logout/` | session + cookie auth (no JWT) |
| POST | `/api/auth/password-reset/` | `{email}`; sends an email with `uid` and `token` |
| POST | `/api/auth/password-reset/confirm/` | `{uid, token, new_password}` |
| GET/POST/PUT/PATCH/DELETE | `/api/categories/` | read: everyone, write: admin only |
| GET/POST/PUT/PATCH/DELETE | `/api/locations/` | write: authenticated; edit/delete: author or admin; delete is soft |
| GET | `/api/locations/export/?format=json\|csv` | same filters as the list, no pagination (pandas) |
| GET/POST | `/api/locations/{id}/reviews/` | rating 1-5 + comment; one review per user per location |
| GET/PATCH/DELETE | `/api/reviews/{id}/` | author or admin can modify |
| POST | `/api/reviews/{id}/vote/` | `{"value": 1}` like / `{"value": -1}` dislike; once per user |

List query params: `search` (title/description), `category`, `author`, `min_rating`, `max_rating`,
`ordering` (`created_at`, `avg_rating`, `popularity`, prefix `-` for descending), `page` (10 per page).

Authenticated unsafe requests need the `X-CSRFToken` header (get the token from `/api/auth/csrf/`).
In Swagger, reload the page after logging in so it picks up the new token.

## Design notes

- **Rating and popularity are never stored.** `Location.objects.with_stats()` annotates
  `avg_rating`, `reviews_count`, `views_7d` and
  `popularity = avg_rating * 2 + reviews_count + views_7d * 0.1`
  (weights are constants in `apps/locations/models.py`). Locations without reviews have `avg_rating = null`
  and sort last when ordering by rating.
- **Views.** `GET /api/locations/{id}/` records a `LocationView` row. A Redis key
  `view:{location}:{user id | IP}` with a 1 hour TTL makes sure one viewer counts once per hour.
  The IP is taken from `REMOTE_ADDR`; behind a reverse proxy configure the proxy to set it correctly.
- **List cache.** List responses are cached in Redis for 5 minutes under a key that contains a version number.
  Creating/updating/deleting a location or a review bumps the version (Django signals), which invalidates
  every cached page at once. View counts do not invalidate the cache, so `views_7d`/`popularity` in the list
  can lag by up to the TTL; the detail endpoint is always exact.
- **Soft delete.** `Location.delete()` sets `is_deleted`; the default manager hides such rows,
  `Location.all_objects` sees them (used by the admin).
- **Email.** The console backend is the default (the reset email appears in `docker compose logs web`).
  Set `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` for real SMTP.
- **Tests** use an in-memory cache, so they do not touch Redis.

## Layout

```
config/            settings, root urls
apps/accounts/     auth + password reset
apps/locations/    Category, Location, LocationView, filters, cache, export
apps/reviews/      Review, ReviewVote
```
