# Campus Equipment Rental System

**Campus Equipment Rental System | Python, Django REST Framework, React, SQLite**: students reserve lab and
sports equipment, track their rental history, and staff flag overdue returns.

A React frontend talks to a documented Django REST API with filtering, availability checks and relational
data models. Students browse oscilloscopes, Raspberry Pi kits, microscopes, cameras, footballs, hurleys and
more, see which days each item is free, and reserve it for a date range. Desk staff hand items out, take
them back (recording their condition) and chase anything overdue.

**Stack:** React 18 · React Router 6 · Django 5.2 LTS · Django REST Framework · django-filter ·
drf-spectacular (OpenAPI) · python-decouple · SQLite

## Features

- **Browse equipment:** Lab and Sports tabs, search by name or asset tag, a category filter and a date-range
  picker that lists only the items free for the whole range.
- **Availability calendar:** each item's page shows three weeks of busy and free days. Click a free day to
  start and another to choose the due date, then reserve. The form checks the dates, the item's loan limit
  and busy days before sending, and the API re-checks every rule.
- **Booking rules**, enforced in one services module inside a transaction that locks the item:
  - no overlap with another reserved or checked-out reservation for the same item;
  - no bookings in the past, longer than the item's `max_loan_days`, or for retired items or items waiting
    for repair;
  - at most `MAX_ACTIVE_RESERVATIONS` (default 3) reserved or checked-out items per student;
  - no new bookings while the student has an overdue item.
- **My rentals:** current, upcoming and history tabs. Overdue items are highlighted, with a banner
  explaining that the student can't reserve more until they are returned. Reservations can be cancelled
  until they are collected.
- **Equipment desk (staff):** the day's pickups and returns with check-out and return buttons. Returning an
  item records its condition, which also updates the item.
- **Overdue returns:** a staff list of everything still out after its due time, the `is_overdue` flag on
  every reservation, and a `flag_overdue` management command for cron.
- **Students and history:** a staff student directory with each student's active and overdue counts, and
  every student's full rental history, including returns that came back late.
- **Manage equipment (staff):** add and edit items, retire them, and see why an item with rental history
  can't be deleted.
- **Accounts:** token authentication, student self-service sign-up (student number, course and year) with
  Django's password validators, and two roles with their own navigation and API permissions.
- **Back office:** Django admin for every model, plus interactive OpenAPI docs in Swagger UI and ReDoc.
- **Look and feel:** a campus theme in Outfit with a navy sidebar, indigo actions and an amber accent. On
  phones the sidebar becomes a scrollable top bar and the forms and calendar stack to fit.

### Backend design

| Concern | Implementation |
| --- | --- |
| Business rules | `rentals/services.py`: create, check out, return and cancel run in `transaction.atomic` with the item's row locked (`SELECT ... FOR UPDATE`; on SQLite a no-op `UPDATE` takes the write lock, so concurrent bookings queue) |
| Overdue | Never stored: `Reservation.objects.with_flags()` annotates `is_overdue` (checked out, `due_at` in the past) and `returned_late` (`returned_at` after `due_at`) |
| Availability | `Reservation.objects.blocking(start, end)` finds the reservations that hold an item; an overdue item stays busy until it is returned |
| Integrity | Check constraint `due_at > start_at`; equipment and reservations use `on_delete=PROTECT`, and the API answers blocked deletes with `409 Conflict` |
| Indexes | `Reservation(equipment, start_at)`, `(student, start_at)`, `(status, due_at)`, `Equipment(category, name)`, unique `asset_tag`, `student_number` and email |
| Bounded responses | `PageNumberPagination` with 25 rows per page on every list; `?page_size=` up to 100 |
| Filtering and search | `django-filter` FilterSets, `SearchFilter` and `OrderingFilter` on every list |
| Query efficiency | `select_related` on every foreign key, `Exists`/`Count` annotations, and tests asserting a constant query count |
| Abuse protection | `DEFAULT_THROTTLE_RATES` for `anon`, `user`, `login` and `register` |
| Configuration | python-decouple reads every secret and setting from the environment or `Backend/.env` |

## Architecture

```
.
├── Backend/                          Django REST API
│   ├── equipmentrental/              Project package: settings (python-decouple), root URLconf,
│   │                                 pagination, 409 exception handler
│   ├── accounts/                     Custom User (students and staff), token login/logout, sign-up, "me"
│   ├── rentals/
│   │   ├── models.py                 Category, Location, Equipment, Reservation (+ overdue annotations)
│   │   ├── services.py               Availability checks and every booking, check-out and return rule
│   │   ├── permissions.py            IsStudent, IsDeskStaff, IsStaffOrReadOnly, ReservationPermission
│   │   ├── serializers.py            API representations
│   │   ├── views.py                  ViewSets: catalogue, availability, reservations, students, history
│   │   ├── filters.py                FilterSets (available_from/to, when, overdue, kind, date bounds)
│   │   ├── admin.py                  Django admin configuration
│   │   ├── management/commands/      seed_demo_data, flag_overdue
│   │   └── tests.py                  Rules, API, permissions, query-count and command tests
│   ├── schema.yml                    Generated OpenAPI 3 schema
│   ├── requirements.txt
│   └── .env.example
└── Frontend/                         React single-page app (Create React App)
    ├── src/api.js                    API client: token auth, pagination, error handling
    ├── src/hooks.js · dates.js       Data-loading hooks; local-date and desk-hours helpers
    ├── src/rentals.js                Reserve-form validation and calendar selection
    ├── src/session.js                Current user and role helpers
    ├── src/components/               AvailabilityCalendar, WeekNavigator, ReservePanel, ReturnForm,
    │                                 ReservationRow, StatusBadge, DateTile, Icon, ...
    ├── src/styles.css                Theme: colours, sidebar layout, calendar and responsive rules
    ├── src/views/                    BrowseEquipment, EquipmentDetail, MyRentals, ReservationDetail,
    │                                 EquipmentDesk, OverdueList, StudentList, StudentHistory,
    │                                 ManageEquipment, Login
    ├── src/__tests__/                Jest / Testing Library tests
    └── .env.example
```

### Data model

```
Category  (name, slug, kind: lab | sports)            1 ── * Equipment
Location  (name, building)                             1 ── * Equipment
Equipment (name, asset_tag, description, condition, is_active, max_loan_days)
                                                       1 ── * Reservation
User      (student_number, course, year | is_staff)    1 ── * Reservation   (as the student)
Reservation (start_at, due_at, status, checked_out_at/_by, returned_at/_by, return_condition, notes)
```

- A reservation moves `reserved` → `checked_out` → `returned`, or `reserved` → `cancelled`. Reservations
  are never edited or deleted through the API, so the rental history stays intact.
- **Overdue** means checked out with `due_at` in the past. It is computed by a query annotation, never stored.
- Condition is one of `excellent`, `good`, `fair` or `needs_repair`. Items needing repair can't be reserved
  or lent out until staff change their condition.
- Times are stored in UTC. The React app books whole days: collection from 09:00 on the start date (or
  straight away, if that has passed today) and return by 17:00 on the due date, in the browser's time zone.

### Who can do what

| | Student | Staff (`is_staff`) |
| --- | --- | --- |
| Browse categories, locations, equipment and availability | ✓ (active items) | ✓ (including retired items) |
| Add, edit, retire or delete equipment, categories and locations | – | ✓ |
| Reserve equipment | for themselves | for any student |
| See reservations | their own | all |
| Cancel a reservation (until it is collected) | their own | any |
| Check out and return items | – | ✓ |
| Overdue list (`/api/reservations/overdue/`) | – | ✓ |
| Rental history | `/api/me/history/` | `/api/students/{id}/history/` for any student |
| Student directory (`/api/students/`) | – | ✓ |

## Getting started

### Prerequisites

- Python 3.10–3.14 (tested with 3.14)
- Node.js 18+ with npm (tested with Node 22). On WSL, use a Linux install of Node (for example via
  [nvm](https://github.com/nvm-sh/nvm)); a Windows `npm` can't work with WSL paths.

SQLite comes with Python, so there is no database server to install. You'll need two terminals: one for the
API and one for the React app.

### 1. Start the backend (terminal 1)

```bash
cd Backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env
```

Set `SECRET_KEY` in `Backend/.env`. You can generate one with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Then create the SQLite database (`Backend/db.sqlite3`), load the demo data and start the server:

```bash
python manage.py migrate
python manage.py seed_demo_data      # prints the demo passwords, so note them
python manage.py test                # optional: should end with OK
python manage.py runserver 8000
```

Keep the API on port 8000, because that's where the React app looks for it (see `REACT_APP_API_URL` below).

| URL | What |
| --- | --- |
| http://127.0.0.1:8000/ | Swagger UI |
| http://127.0.0.1:8000/api/schema/redoc/ | ReDoc |
| http://127.0.0.1:8000/api/ | Browsable API root |
| http://127.0.0.1:8000/admin/ | Django admin (log in as `admin`) |

### 2. Start the frontend (terminal 2)

```bash
cd Frontend
npm install
npm start                            # or: npm run build   (production bundle in Frontend/build/)
```

Open http://localhost:3000 and sign in with one of the demo accounts, or create a new student account from
the sign-in page. The app calls `http://127.0.0.1:8000/api` by default; to change that, copy `.env.example`
to `.env` and edit `REACT_APP_API_URL`.

### Demo data and accounts

`seed_demo_data` loads five locations (engineering, science, media, sports centre and pavilion desks), six
categories and 24 items of equipment:

- **Lab:** oscilloscopes, multimeters, Raspberry Pi kits, microscopes (one waiting for repair) and DSLR cameras.
- **Sports:** footballs, tennis rackets, hurleys (one retired), training bibs and cones.

It also adds six students and twelve reservations: returned ones (one returned late), current loans, a
pickup due today, upcoming reservations, a cancellation and two overdue loans. These accounts can sign in:

| Account | Role | Use it to |
| --- | --- | --- |
| `aoife` | student | Browse, reserve, cancel and track rentals (has a current loan and an upcoming reservation) |
| `liam` | student | See an overdue item highlighted and the block on new reservations |
| `desk` | staff | Run the equipment desk: pickups, returns, overdue list, students, equipment |
| `admin` | superuser | The Django admin (and everything staff can do) |

Passwords are generated on each run and **printed only to your console**, so no credentials live in the
repository. You can adjust the command with these options:

- `DEMO_PASSWORD` in `Backend/.env` (or the environment) sets one fixed password for all four accounts.
- `--reset` deletes the equipment, reservations and student accounts and rebuilds the sample data. Run it
  when the sample dates have drifted too far into the past.
- Running the command again without `--reset` keeps the data and just rotates the passwords.

### 3. Try it out

1. **As `aoife`:**
   - On **Browse equipment**, choose the **Lab** tab, then pick dates under **Show what's free** (for
     example **Next 3 days**) to list only the items free for that range.
   - Open **Digital multimeter**. Red days are busy and green days are free. Click a free day, then a later
     one, and press **Reserve**.
   - Try a range longer than the item's loan limit, or one that covers a busy day: the form explains why it
     can't be booked.
   - **My rentals** now shows the reservation under **Upcoming**, where you can cancel it. Your Raspberry Pi
     kit is under **Current**, and **History** shows past loans, including a camera that came back late.
2. **As `liam`:** **My rentals** highlights an overdue multimeter. Try to reserve anything and the API
   refuses until it is returned.
3. **As `desk`:**
   - **Equipment desk** lists today's pickups (an oscilloscope for Emma). Press **Check out**.
   - Under **Returns due**, press **Return** on Liam's multimeter, choose its condition and confirm. Liam
     can now reserve again.
   - **Overdue** lists what is still late. **Students** shows each student's active and overdue counts and
     opens their full rental history.
   - **Manage equipment** adds or edits items. Set an item to **Needs repair** and students can no longer
     reserve it.

### Checking overdue items from cron

```bash
python manage.py flag_overdue                 # human-readable list, or "No overdue equipment."
python manage.py flag_overdue --format csv    # for spreadsheets or mail merges
python manage.py flag_overdue --exit-code     # exits with status 1 when anything is overdue
```

For example, a crontab line that mails the desk every weekday morning, but only when something is overdue:

```
0 8 * * 1-5  cd /srv/equipment/Backend && .venv/bin/python manage.py flag_overdue --exit-code > overdue.txt || mail -s "Overdue equipment" desk@example.com < overdue.txt
```

### Stopping and restarting

- Stop a server with `Ctrl+C`; leave the virtualenv with `deactivate`.
- Next time:
  - Start the API with `source .venv/bin/activate` and `python manage.py runserver 8000` in `Backend/`.
  - Start the React app with `npm start` in `Frontend/`.
  - Run `python manage.py seed_demo_data` again for fresh passwords, or with `--reset` for fresh dates.
- To start over with a clean database, delete `Backend/db.sqlite3`, then run `python manage.py migrate` and
  `python manage.py seed_demo_data`.

### Troubleshooting

| Problem | Fix |
| --- | --- |
| `SECRET_KEY not found` | `Backend/.env` is missing. Copy `.env.example` to `.env` and set `SECRET_KEY`. |
| `UNC paths are not supported` or other npm errors on WSL | You're using the Windows npm. Install Node with nvm and open a new terminal. |
| The React app shows CORS or network errors | Make sure the API is running on port 8000, and open the app at `localhost:3000`. |
| "Invalid username or password" | Use the passwords from your most recent `seed_demo_data` run. |
| The sample loans are weeks old | Run `python manage.py seed_demo_data --reset` to rebuild them around today. |
| `Error: That port is already in use` | Stop the other server, or run the API on another port and point `REACT_APP_API_URL` at it. |

## Configuration

Backend settings are read from environment variables or `Backend/.env` via python-decouple, and nothing
secret is hard-coded.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | *(required)* | Django secret key |
| `DEBUG` | `False` | Development mode |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated host names |
| `CSRF_TRUSTED_ORIGINS` | *(empty)* | HTTPS origins allowed to POST to the admin |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Browser origins allowed to call the API |
| `DATABASE_URL` | SQLite file `Backend/db.sqlite3` | Optional database URL (dj-database-url syntax) |
| `TIME_ZONE` | `UTC` | Zone for bare dates in query strings and command output |
| `MAX_ACTIVE_RESERVATIONS` | `3` | Reserved or checked-out items a student may hold at once |
| `THROTTLE_RATE_ANON` / `_USER` / `_LOGIN` / `_REGISTER` | `60/minute` / `300/minute` / `5/minute` / `10/hour` | API rate limits |
| `DEMO_PASSWORD` | *(random)* | Fixed password for the `seed_demo_data` accounts |
| `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS` | `False`, `0` | HTTPS hardening (applies when `DEBUG=False`) |

The frontend reads `REACT_APP_API_URL` from `Frontend/.env` at build time.

## API overview

Every endpoint except login, sign-up and the docs needs an `Authorization: Token <token>` header. List
endpoints return `{count, next, previous, results}` (25 per page) and accept `?page=`, `?page_size=`
(up to 100), `?search=` and `?ordering=`. Rule violations come back as `400` with `{field: [messages]}`;
deleting a record that history depends on returns `409`.

| Method | Endpoint | Notes |
| --- | --- | --- |
| `POST` | `/api/auth/token/` | Exchange `username` / `password` for a token (throttled) |
| `POST` | `/api/auth/register/` | Create a student account (`student_number`, `course`, `year` required); returns a token and the user (throttled) |
| `POST` | `/api/auth/logout/` | Revoke the current token |
| `GET`, `PATCH` | `/api/auth/me/` | Current user, including `is_staff` and `role` |
| CRUD | `/api/categories/`, `/api/locations/` | Reference data (staff write). Category filters: `kind`, `slug` |
| CRUD | `/api/equipment/` | Staff write. Filters: `category`, `kind`, `location`, `condition`, `is_active`, `available_from` + `available_to`; search on `name` and `asset_tag` |
| `GET` | `/api/equipment/{id}/availability/?from=&to=` | Busy ranges in the window (default 28 days from today, at most 120), plus `is_available` |
| `GET`, `POST` | `/api/reservations/` | Students see their own, staff see all. `POST {equipment, start_at, due_at, notes[, student]}`. Filters: `status`, `equipment`, `student`, `kind`, `when=current\|upcoming\|past`, `overdue=true`, `start_after`, `start_before`, `due_after`, `due_before` |
| `GET` | `/api/reservations/{id}/` | Includes `is_overdue` and `returned_late` |
| `POST` | `/api/reservations/{id}/checkout/` | Staff: hand the item over (from the start day until it is due) |
| `POST` | `/api/reservations/{id}/return/` | Staff: `{return_condition, notes}`; also updates the item's condition |
| `POST` | `/api/reservations/{id}/cancel/` | Owner or staff, until checkout |
| `GET` | `/api/reservations/overdue/` | Staff: overdue loans, longest overdue first |
| `GET` | `/api/me/history/` | Students: their own rental history (same filters as reservations) |
| `GET` | `/api/students/`, `/api/students/{id}/` | Staff: student directory with `active_reservations` and `overdue_reservations`. Filters: `course`, `year`, `student_number` |
| `GET` | `/api/students/{id}/history/` | Staff: a student's rental history |

`from`, `to`, `available_from` and `available_to` accept an ISO date (a whole day in `TIME_ZONE`, with `to`
inclusive) or an ISO datetime.

Example, using the demo data:

```bash
API=http://127.0.0.1:8000/api
TOKEN=$(curl -s -X POST $API/auth/token/ -H 'Content-Type: application/json' \
  -d '{"username": "aoife", "password": "<printed password>"}' \
  | python -c "import json, sys; print(json.load(sys.stdin)['token'])")

# Lab equipment free for the whole of 2–4 November
curl -H "Authorization: Token $TOKEN" "$API/equipment/?kind=lab&available_from=2026-11-02&available_to=2026-11-04"

# When is item 4 busy this month?
curl -H "Authorization: Token $TOKEN" "$API/equipment/4/availability/?from=2026-11-01&to=2026-11-30"

# Reserve it; a second, overlapping request is rejected with 400
curl -X POST -H "Authorization: Token $TOKEN" -H 'Content-Type: application/json' \
  -d '{"equipment": 4, "start_at": "2026-11-02T09:00:00Z", "due_at": "2026-11-04T17:00:00Z"}' $API/reservations/
```

## Tests

```bash
cd Backend && python manage.py test                     # about 100 tests
cd Frontend && CI=true npm test -- --watchAll=false     # 44 tests
```

- **Backend:** overlap and double-booking rules, loan limits, past and unavailable items, overdue blocking,
  the availability endpoint and filters, check-out and return permissions and rules, the overdue annotation
  and endpoint, the `flag_overdue` command, history scoping, pagination, throttling, constant query counts,
  sign-up and the seed command.
- **Frontend:** sign-in and sign-up, role-based navigation and redirects, token handling, the availability
  calendar, reserve form validation, overdue highlighting, date helpers and error formatting.

## Deploying

- Set `DEBUG=False`, a strong `SECRET_KEY`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `TIME_ZONE` and the
  HTTPS settings.
- Run `python manage.py migrate` and `python manage.py collectstatic`, then serve the project with a WSGI
  server such as gunicorn behind an HTTPS reverse proxy. Keep `db.sqlite3` on persistent storage and back
  it up.
- If you run several worker processes, configure a shared cache (for example Redis) so throttling limits
  apply across all of them.
- Build the frontend with `npm run build` (with `REACT_APP_API_URL` pointing at the API) and serve
  `Frontend/build/` as static files.
