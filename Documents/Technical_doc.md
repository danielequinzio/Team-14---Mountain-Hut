# Mountain Hut

> A software system supporting the activities of a mountain hut.

## Contents

- [Overview](#overview)
- [The problem](#the-problem)
- [Purpose](#purpose)
- [Roles](#roles)
- [Development](#development)
  - [Architecture](#architecture)
  - [Tech stack](#tech-stack)
  - [Backend structure](#backend-structure)
  - [Database](#database): [`user`](#user), [`table`](#table), [`slot`](#slot), [`slot_table`](#slot_table), [`booking`](#booking), [`booking_table`](#booking_table)
- [Backend EndPoint](#backend-endpoint)
  - [Authentication](#authentication)
  - [Routes](#routes): [`GET /slot`](#get-slot), [`GET /slot/{id}`](#get-slotid), [`GET /availability`](#get-availability), [`POST /booking`](#post-booking), [`POST /register`](#post-register), [`POST /login`](#post-login), [`POST /token`](#post-token), [`POST /logout`](#post-logout), [`GET /users/me`](#get-usersme), [`GET /tables`](#get-tables), [`POST /tables`](#post-tables), [`GET /slots`](#get-slots), [`GET /slots/{id}`](#get-slotsid), [`POST /slots`](#post-slots), [`POST /slots/{id}/tables`](#post-slotsidtables), [`POST /slots/{id}/copy`](#post-slotsidcopy)
  - [Objects](#objects): [`Table`](#table-object), [`TableCreate`](#tablecreate-object), [`Slot`](#slot-object), [`SlotCreate`](#slotcreate-object), [`SlotTablesAdd`](#slottablesadd-object), [`CopySlotRequest`](#copyslotrequest-object), [`SlotAvailability`](#slotavailability-object), [`SlotDetail`](#slotdetail-object), [`SlotTableInfo`](#slottableinfo-object), [`BookingCreate`](#bookingcreate-object), [`BookingResponse`](#bookingresponse-object), [`AvailabilityResponse`](#availabilityresponse-object), [`RegisterRequest`](#registerrequest-object), [`LoginRequest`](#loginrequest-object), [`UserPublic`](#userpublic-object), [`TokenResponse`](#tokenresponse-object)
  - [Errors](#errors)

## Overview

**Mountain Hut** is a web-based system that supports the day-to-day operations of an alpine mountain hut. These huts are simple hospitality facilities that offer shared sleeping spaces, communal dining, basic food and shelter. Hikers use them as day-trip destinations, overnight stops on longer routes, or bases for further hikes. They are often owned by alpine clubs or public bodies and run by a warden with a small staff.

## The problem

Huts work under tight constraints:

- **Limited resources**: space, supplies and energy restrict what the hut can offer, and staff must split their time between serving guests and preparing for later arrivals.
- **Changing demand**: weather and mountain conditions change visitors' plans, and meal times can bring many arrivals at once.
- **Scattered information**: requests come in through web, phone, messages and in person. When those records are scattered, staff can miss changes, misread a party's needs, or commit to more than the hut can handle.

## Purpose

The system gives hikers and the hut team one shared, up-to-date source of information:

- **For visitors**: more confidence when planning their stop and adapting their journey.
- **For hut staff**: better use of limited resources and fewer misunderstandings when plans change.

## Roles

| Role         | Description                                                           |
|--------------|-----------------------------------------------------------------------|
| **User**     | Anyone accessing the public web pages.                                |
| **Hiker**    | A registered visitor, acting alone or as the contact person for a party. |
| **Warden**   | Manages the hut and makes operational decisions. Can also act as an employee. |
| **Employee** | Handles the hut's daily operations.                                   |

Inside the project there are some seed data including some users:

|role|email|pwd|
|----|----|----|
|warden|luca.bonetti@rifugio.example|warden|
|Employee|giulia.ferrero@rifugio.example|employee|
|Hiker|anna.rossi@mail.example|hiker|
|Hiker|paolo.bianchi@mail.example|hiker|

## Development

The project is developed with **Scrum** in two-week sprints.


### Architecture

```mermaid
flowchart LR
    C[Web Client <br/> React] -- HTTP + JSON --> A[FastAPI app<br/>backend/app/]
    A -- SQLModel / SQLAlchemy --> D[(SQLite<br/>backend/OQM.db)]
```

- **FastAPI** exposes the REST endpoints and validates requests and responses.
- **SQLModel** defines each table once. The same class is used as the database table and as the Pydantic model for request and response bodies.
- **SQLite** stores the data in a single file, `backend/OQM.db`, so no database server is needed.

### Tech stack

| Component         | Library                      | Version             |
| ----------------- | ---------------------------- | ------------------- |
| Fronted Framework | React                        |                 |
| API framework     | FastAPI                      | 0.142.2             |
| ORM / models      | SQLModel (on SQLAlchemy 2.1) | 0.0.48              |
| Database          | SQLite                       | bundled with Python |
| Tests             | pytest + `unittest.mock`     | pytest 9.1.1        |

The requirements of the backend can be found in the [requirements.txt](../backend/requirements.txt) in the backend folder. To install and it is suggested to check the appropriate document in that folder with all the instructions.

### Backend structure

The backend code is in the [`backend/app/`](../backend/app/) package:

```
app/
├── main.py              # creates the app, startup logic (lifespan), mounts the routers
├── config.py            # settings read from environment variables (DATABASE_URL)
├── database.py          # engine, get_session / SessionDep dependency
├── models/              # SQLModel tables and request bodies
│   #all the models here
├── routers/             # HTTP endpoints, one APIRouter per resource
│   # all the routers
└── services/            # logic shared by the routes
  
```

### Database

This schema defines the overall structure of the project until user-story: #4; Other user-story may change database representation.

```mermaid
erDiagram
    USER ||--o{ SLOT : "creates"
    USER ||--o{ BOOKING : "makes"
    SLOT ||--o{ BOOKING : "receives"
    SLOT ||--o{ SLOT_TABLE : "offers"
    TABLE ||--o{ SLOT_TABLE : "is offered in"
    BOOKING ||--o{ BOOKING_TABLE : "uses"
    SLOT_TABLE ||--o{ BOOKING_TABLE : "is used by"

    USER {
        int id PK
        string username
        string name
        string surname
        string email UK
        string mobile_number
        string notes
        string emergency_contact
        string password_hash
        string role
    }
    TABLE {
        int id PK
        int number UK
        int capacity
        string location
    }
    SLOT {
        int id PK
        datetime start_time
        datetime end_time
        int created_by FK
    }
    SLOT_TABLE {
        int id PK
        int slot_id FK
        int table_id FK
        int occupied_seats
    }
    BOOKING {
        int id PK
        int user_id FK
        int slot_id FK
        int party_size
        datetime created_at
    }
    BOOKING_TABLE {
        int id PK
        int booking_id FK
        int slot_table_id FK
        int seats_booked
    }
```

Columns are `NOT NULL` unless marked as nullable.

#### `user`

A person with an account in the system.

| Column              | Type    | Constraints | Description                               |
|---------------------|---------|-------------|-------------------------------------------|
| `id`                | INTEGER | PK          | User identifier                           |
| `username`          | VARCHAR |             | Username                                  |
| `name`              | VARCHAR |             | First name                                |
| `surname`           | VARCHAR |             | Last name                                 |
| `email`             | VARCHAR | UNIQUE      | Email address                             |
| `mobile_number`     | VARCHAR |             | Mobile number                             |
| `notes`             | VARCHAR | nullable    | Free notes                                |
| `emergency_contact` | VARCHAR | nullable    | Emergency contact                         |
| `password_hash`     | VARCHAR |             | Password hash                             |
| `role`              | VARCHAR |             | `Hiker`, `Warden` or `Employee`           |

#### `table`

A physical table of the hut.

| Column     | Type    | Constraints | Description          |
|------------|---------|-------------|----------------------|
| `id`       | INTEGER | PK          | Table identifier     |
| `number`   | INTEGER | UNIQUE      | Number of the table  |
| `capacity` | INTEGER | CHECK `> 0` | Total seats          |
| `location` | VARCHAR |             | Where the table is   |

#### `slot`

A time window that can be booked.

| Column       | Type     | Constraints    | Description               |
|--------------|----------|----------------|---------------------------|
| `id`         | INTEGER  | PK             | Slot identifier           |
| `start_time` | DATETIME |                | Start of the slot         |
| `end_time`   | DATETIME |                | End of the slot           |
| `created_by` | INTEGER  | FK → [`user.id`](#user) | User who defined the slot |

#### `slot_table`

A table available in a slot. A slot offers one or more tables.

| Column           | Type    | Constraints     | Description                    |
|------------------|---------|-----------------|--------------------------------|
| `id`             | INTEGER | PK              | Identifier a booking refers to |
| `slot_id`        | INTEGER | FK → [`slot.id`](#slot)  | The slot                       |
| `table_id`       | INTEGER | FK → [`table.id`](#table) | The table offered              |
| `occupied_seats` | INTEGER | CHECK `>= 0`    | Seats already taken            |

Each table appears at most once per slot: `UNIQUE (slot_id, table_id)`.
The `occupied_seats` is redundant on porpuse to not recaulcate it every time from the bookings table.
#### `booking`

A reservation made by a user for a slot.

| Column       | Type     | Constraints    | Description               |
|--------------|----------|----------------|---------------------------|
| `id`         | INTEGER  | PK             | Booking identifier        |
| `user_id`    | INTEGER  | FK → [`user.id`](#user) | User who made the booking |
| `slot_id`    | INTEGER  | FK → [`slot.id`](#slot) | The booked slot           |
| `party_size` | INTEGER  | CHECK `> 0`    | Number of people          |
| `created_at` | DATETIME |                | Creation time             |

#### `booking_table`

The seats a booking uses on one of the tables of its slot. A booking uses one or more of them.

| Column          | Type    | Constraints          | Description              |
|-----------------|---------|----------------------|--------------------------|
| `id`            | INTEGER | PK                   | Identifier               |
| `booking_id`    | INTEGER | FK → [`booking.id`](#booking)    | The booking              |
| `slot_table_id` | INTEGER | FK → [`slot_table.id`](#slot_table) | The table in the slot    |
| `seats_booked`  | INTEGER | CHECK `> 0`          | Seats used on that table |

Each slot table appears at most once per booking: `UNIQUE (booking_id, slot_table_id)`.



## Backend EndPoint
The full OpenAPI documentation can be found on the backend URL at [`/docs`](http://127.0.0.1:8000/docs), which is autogenerated by the FastAPI framework. The links to `127.0.0.1:8000` work while the backend is running locally.

### Authentication

A login gives the client a signed token (JWT). The code is in [`services/auth.py`](../backend/app/services/auth.py). Each request that needs a login must carry the token in one of two ways:

| Way            | Sent as                         | Obtained from                                                                 |
|----------------|---------------------------------|-------------------------------------------------------------------------------|
| Session cookie | `session` cookie                | [`POST /login`](#post-login) or [`POST /token`](#post-token), which both set it |
| Bearer token   | `Authorization: Bearer <token>` | The `access_token` returned by [`POST /token`](#post-token)                   |

If a request carries both, only the cookie is checked. A request with an invalid cookie is refused even if its Bearer token is valid.

The cookie is HTTP-only with `SameSite=Lax`, so page scripts can't read it. It is sent only over HTTPS when `SESSION_COOKIE_SECURE=true`.

The token is signed with `SECRET_KEY` (HS256) and contains:

| Claim      | Content                                        |
|------------|------------------------------------------------|
| `sub`      | The [`user`](#user) `id`, as a string          |
| `username` | The username                                   |
| `role`     | `Hiker`, `Warden` or `Employee`                |
| `exp`      | Expiry, 30 minutes after the login by default (`ACCESS_TOKEN_EXPIRE_MINUTES`) |

The server keeps no list of sessions and trusts the content of a signed token until it expires. This means that:

- a token stays valid after [`POST /logout`](#post-logout), which only removes the cookie
- a token keeps the role it was created with, even if the user's role changes
- a token stays valid if its user is deleted, unless the route checks the database as [`POST /booking`](#post-booking) does

Routes limited to some roles use the `require_role` dependency, which answers `403` to any other role.

Passwords are stored as Argon2 hashes in `password_hash`, never in clear text.

### Routes

All the routes of the backend, defined in [`routers/slot.py`](../backend/app/routers/slot.py), [`routers/booking.py`](../backend/app/routers/booking.py), [`routers/availability.py`](../backend/app/routers/availability.py), [`routers/auth.py`](../backend/app/routers/auth.py) and [`routers/tables.py`](../backend/app/routers/tables.py). Click a route for its details, or its errors for the list of errors it can return.

| Method | Route                                        | Login required           | Input                                                               | Success                                                       | Errors                                                                  |
|--------|----------------------------------------------|--------------------------|---------------------------------------------------------------------|---------------------------------------------------------------|-------------------------------------------------------------------------|
| GET    | [`/slot`](#get-slot)                         | No                       | -                                                                   | `200` list of [`SlotAvailability`](#slotavailability-object)  | None                                                                    |
| GET    | [`/slot/{id}`](#get-slotid)                  | No                       | `id` in the path (int)                                              | `200` [`SlotDetail`](#slotdetail-object)                      | [`404`, `422`](#get-slotid-errors)                                      |
| GET    | [`/availability`](#get-availability)         | No                       | Query: `date`, `time`, `party_size`                                 | `200` [`AvailabilityResponse`](#availabilityresponse-object)  | [`400`, `422`](#get-availability-errors)                                |
| POST   | [`/booking`](#post-booking)                  | Yes, `Hiker` only        | [`BookingCreate`](#bookingcreate-object) body                       | `201` [`BookingResponse`](#bookingresponse-object)            | [`400`, `401`, `403`, `409`, `422`](#post-booking-errors)               |
| POST   | [`/register`](#post-register)                | No                       | [`RegisterRequest`](#registerrequest-object) body                   | `201` [`UserPublic`](#userpublic-object)                      | [`409`, `422`](#post-register-errors)                                   |
| POST   | [`/login`](#post-login)                      | No                       | [`LoginRequest`](#loginrequest-object) body                         | `200` [`UserPublic`](#userpublic-object) and the `session` cookie | [`401`, `422`](#post-login-errors)                                  |
| POST   | [`/token`](#post-token)                      | No                       | Form data: `username` (the email), `password`                       | `200` [`TokenResponse`](#tokenresponse-object) and the `session` cookie | [`401`, `422`](#post-token-errors)                            |
| POST   | [`/logout`](#post-logout)                    | No                       | -                                                                   | `204` with no body                                            | None                                                                    |
| GET    | [`/users/me`](#get-usersme)                  | Yes, any role            | -                                                                   | `200` [`UserPublic`](#userpublic-object)                      | [`401`](#get-usersme-errors)                                            |
| GET    | [`/tables`](#get-tables)                     | Yes, `Employee` or `Warden` | -                                                                | `200` list of [`Table`](#table-object)                        | [`401`, `403`](#get-tables-errors)                                      |
| POST   | [`/tables`](#post-tables)                    | Yes, `Employee` or `Warden` | [`TableCreate`](#tablecreate-object) body                        | `201` [`Table`](#table-object)                                | [`401`, `403`, `409`, `422`](#post-tables-errors)                       |
| GET    | [`/slots`](#get-slots)                       | Yes, `Employee` or `Warden` | Optional query: `date`, `from_date`, `to_date`                   | `200` list of [`Slot`](#slot-object)                          | [`400`, `401`, `403`, `422`](#get-slots-errors)                         |
| GET    | [`/slots/{id}`](#get-slotsid)                | Yes, `Employee` or `Warden` | `id` in the path (int)                                           | `200` [`SlotDetail`](#slotdetail-object)                      | [`401`, `403`, `404`, `422`](#get-slotsid-errors)                       |
| POST   | [`/slots`](#post-slots)                      | Yes, `Employee` or `Warden` | [`SlotCreate`](#slotcreate-object) body                          | `201` [`Slot`](#slot-object)                                  | [`401`, `403`, `422`](#post-slots-errors)                               |
| POST   | [`/slots/{id}/tables`](#post-slotsidtables)  | Yes, `Employee` or `Warden` | `id` in the path, [`SlotTablesAdd`](#slottablesadd-object) body  | `200` [`SlotDetail`](#slotdetail-object)                      | [`400`, `401`, `403`, `404`, `409`, `422`](#post-slotsidtables-errors)  |
| POST   | [`/slots/{id}/copy`](#post-slotsidcopy)      | Yes, `Employee` or `Warden` | `id` in the path, [`CopySlotRequest`](#copyslotrequest-object) body | `200` [`SlotDetail`](#slotdetail-object)                   | [`400`, `401`, `403`, `404`, `409`, `422`](#post-slotsidcopy-errors)    |

The `/slot` routes are public and are used by the hikers to choose a slot. The `/slots` routes are for the hut staff and show every slot, also the full, closed or past ones.

**How a hiker books a table**

1. Call [`GET /slot`](#get-slot) to see the slots open for booking.
2. Optionally, call [`GET /availability`](#get-availability) to check that the party fits in the chosen slot and see which tables it would get. This doesn't need a login.
3. Log in with [`POST /login`](#post-login) or [`POST /token`](#post-token). See [Authentication](#authentication).
4. Call [`POST /booking`](#post-booking) with the `date` and `time` of the chosen slot.

**How the staff define a slot**

1. Log in as `Employee` or `Warden`.
2. Call [`GET /tables`](#get-tables) to get the `id` of the tables. Create any missing table with [`POST /tables`](#post-tables).
3. Create the slot with [`POST /slots`](#post-slots). The new slot has no tables yet.
4. Give the slot its tables, either by listing them with [`POST /slots/{id}/tables`](#post-slotsidtables) or by copying them from another slot with [`POST /slots/{id}/copy`](#post-slotsidcopy).

A slot with no tables has no free seats, so it doesn't appear in [`GET /slot`](#get-slot) and hikers can't book it.

The Postman collection [`MH_E2E_slots.postman_collection.json`](../backend/backend_test/e2e/MH_E2E_slots.postman_collection.json) runs the whole procedure as the warden: it creates a slot with tables 1 to 6, then creates four outdoor tables, copies the slot into a second one and adds the outdoor tables to it.

#### `GET /slot`

Returns the slots open for booking as a list of [`SlotAvailability`](#slotavailability-object). A slot is left out of the list when:

- it has no free seats, or
- it starts less than two hours from now.

The sample data creates its slots for the day after the database is created. Once that day has passed, this route returns an empty list. To get new sample slots, delete `backend/OQM.db` and restart the backend with `SEED_DATA=true`.

Try it: <http://127.0.0.1:8000/slot>

#### `GET /slot/{id}`

Returns one slot as a [`SlotDetail`](#slotdetail-object), with all the tables it offers. Unlike [`GET /slot`](#get-slot), it also returns slots that are full or closed. It can fail with a [`404` or a `422`](#get-slotid-errors).

Try it: <http://127.0.0.1:8000/slot/1>

#### `GET /availability`

Tells whether a party fits in a slot, without booking it, and answers `200` with an [`AvailabilityResponse`](#availabilityresponse-object). It doesn't need a login, so a visitor can check before registering.

It takes three query parameters, all required:

| Parameter    | Format       | Description                                                                  |
|--------------|--------------|------------------------------------------------------------------------------|
| `date`       | `YYYY-MM-DD` | Day of the slot, in the hut's local time (`Europe/Rome`)                     |
| `time`       | `HH:MM:SS`   | Start of the slot, in the hut's local time (`12:00` and `12:00:00` both work) |
| `party_size` | int          | Number of people, greater than `0`                                           |

The slot is found like in [`POST /booking`](#post-booking): `date` and `time` must match the start of a slot exactly, and the slot must start at least two hours from now. Otherwise the answer is a [`400`](#get-availability-errors).

The tables are chosen with the same rules as [`POST /booking`](#post-booking) (see **How tables are assigned** there), so `tables` holds the tables the party would get if it booked now:

- If the party fits, `available` is `true` and `tables` lists the seats on each table.
- If it doesn't fit, `available` is `false` and `tables` is empty. This is still a `200`, not a `409`. A slot with no tables never fits.

The check only reads the database and changes nothing:

- no seats are held, so another booking made in between can take them, and the following [`POST /booking`](#post-booking) can still get a `409` or other tables
- it doesn't know who is asking, so it doesn't check whether the hiker already has a booking for that slot

The logic is in `check_availability` in [`services/booking.py`](../backend/app/services/booking.py).

Try it: <http://127.0.0.1:8000/availability?date=2026-10-31&time=13:30:00&party_size=11> (use the `date` and `time` of a slot from [`GET /slot`](#get-slot))

The Postman collection [`MH_E2E_availability.postman_collection.json`](../backend/backend_test/e2e/MH_E2E_availability.postman_collection.json) checks parties of different sizes, the refused requests, and that a booking gets the tables the check promised.

#### `POST /booking`

Books a slot for the logged-in hiker and assigns the party to one or more tables. The body is a [`BookingCreate`](#bookingcreate-object), and the answer is a `201` with a [`BookingResponse`](#bookingresponse-object).

The slot is found from `date` and `time`, which must match the start of a slot exactly, in the hut's local time (`Europe/Rome`).

The request is refused when:

- the user is not a logged-in `Hiker`
- the body is not valid
- no slot starts at that `date` and `time`
- the slot starts less than two hours from now
- the hiker already has a booking for that slot
- the slot does not have enough free seats for the party

The errors are listed in [`POST /booking` errors](#post-booking-errors), in the order they are checked.

The booking, its [`booking_table`](#booking_table) rows and the `occupied_seats` counters are saved in one transaction, so a refused booking changes nothing. On SQLite the transaction takes the write lock before reading the free seats, so two parties can't get the same seats.

**How tables are assigned**

Parties book seats, not whole tables, so two parties can share a table that has enough free seats. The tables are chosen in this order:

1. If one table can seat the whole party, use the one with the fewest free seats. On a tie, use the lowest table number.
2. Otherwise split the party over the fewest tables possible, then leave the fewest free seats unused on them. On a tie, use the lowest table numbers. The table with the most free seats is filled first.

For example, a party of 11 with tables 3 and 4 fully free (6 seats each) gets 6 seats on table 3 and 5 on table 4, as shown in [`BookingResponse`](#bookingresponse-object).

**How to try it**

Use a newly registered hiker: the sample hikers already have a booking in every sample slot, so they always get a `409`. The Postman collection [`MH_E2E_booking.postman_collection.json`](../backend/backend_test/e2e/MH_E2E_booking.postman_collection.json) runs the whole procedure.

#### `POST /register`

Creates a new account from a [`RegisterRequest`](#registerrequest-object) and answers `201` with a [`UserPublic`](#userpublic-object). It doesn't log the user in, so a [`POST /login`](#post-login) is needed afterwards.

The server sets these values itself:

- `role` is always `Hiker`. A `Warden` or `Employee` account can't be created with this route.
- `username` is `<name>.<surname>` in lowercase, so `Mario Verdi` becomes `mario.verdi`. Two people with the same name get the same username: only `email` and `id` are unique.
- `email` is saved in lowercase, so an address can't be registered twice with different capitals.
- Spaces around `name`, `surname`, `mobile_number`, `notes` and `emergency_contact` are removed.

If the email is already registered the answer is a [`409`](#post-register-errors).

#### `POST /login`

Logs a user in from a [`LoginRequest`](#loginrequest-object). The answer is a `200` with a [`UserPublic`](#userpublic-object), and the token is set as the `session` cookie. This is the route for the web client. The email is not case-sensitive.

An unknown email and a wrong password get the same [`401`](#post-login-errors), so the answer doesn't reveal which emails are registered.

The sample users in [Roles](#roles) can log in here.

#### `POST /token`

Does the same as [`POST /login`](#post-login), following the OAuth2 standard. It is the login behind the **Authorize** button of [`/docs`](http://127.0.0.1:8000/docs), and it is useful for clients that send the token as a Bearer header.

It differs from [`POST /login`](#post-login) in three ways:

- The body is form data (`application/x-www-form-urlencoded`), not JSON.
- The email goes in the field called `username`, because the OAuth2 form has no email field. The real `username` of the user doesn't work here.
- The answer is a [`TokenResponse`](#tokenresponse-object) instead of a [`UserPublic`](#userpublic-object).

It also sets the `session` cookie, like [`POST /login`](#post-login).

#### `POST /logout`

Removes the `session` cookie and answers `204` with no body. It doesn't need a login, so it can't fail.

It doesn't cancel the token: a client that kept a copy can use it as a Bearer token until it expires. See [Authentication](#authentication).

#### `GET /users/me`

Returns the logged-in user as a [`UserPublic`](#userpublic-object). Any role can call it, so the client can use it to check who is logged in. It answers a [`401`](#get-usersme-errors) if there is no valid token.

The answer is read from the token, not from the database, so it may be out of date. See [Authentication](#authentication).

Try it: <http://127.0.0.1:8000/users/me> (log in first)

The Postman collection [`MH_E2E_auth.postman_collection.json`](../backend/backend_test/e2e/MH_E2E_auth.postman_collection.json) runs register, login, logout and `GET /users/me` in order.

#### `GET /tables`

Returns all the tables of the hut as a list of [`Table`](#table-object), ordered by `number`.

Try it: <http://127.0.0.1:8000/tables> (log in as staff first)

#### `POST /tables`

Creates a table of the hut from a [`TableCreate`](#tablecreate-object) and answers `201` with the new [`Table`](#table-object). The `id` is chosen by the database.

The `number` must not be used by another table, or the answer is a [`409`](#post-tables-errors). The new table is not added to any slot: use [`POST /slots/{id}/tables`](#post-slotsidtables) for that.

#### `GET /slots`

Returns the slots as a list of [`Slot`](#slot-object), ordered by `start_time`. Unlike [`GET /slot`](#get-slot), it also returns slots that are full, closed, in the past or without tables.

The list can be filtered with these query parameters, all optional and in the `YYYY-MM-DD` format:

| Parameter   | Keeps the slots that start          |
|-------------|-------------------------------------|
| `date`      | on that day                         |
| `from_date` | on that day or later                |
| `to_date`   | on that day or earlier              |

The day of a slot is the day it starts in the hut's local time (`Europe/Rome`). The parameters can be combined, for example `?from_date=2026-11-01&to_date=2026-11-08` for one week. If `from_date` is after `to_date` the answer is a [`400`](#get-slots-errors), and a date that is not valid gets a [`422`](#get-slots-errors).

Try it: <http://127.0.0.1:8000/slots> (log in as staff first)

#### `GET /slots/{id}`

Returns one slot as a [`SlotDetail`](#slotdetail-object), with all its tables. It gives the same answer as [`GET /slot/{id}`](#get-slotid) but needs a staff login. It can fail with a [`404`](#get-slotsid-errors) if there is no slot with that id.

#### `POST /slots`

Creates a slot from a [`SlotCreate`](#slotcreate-object) and answers `201` with the new [`Slot`](#slot-object). The server sets `created_by` to the logged-in user.

Send `start_time` and `end_time` with their UTC offset, as in the example of [`SlotCreate`](#slotcreate-object), so they are read in the hut's local time. `end_time` must be after `start_time`, or the answer is a [`422`](#post-slots-errors).

The server does not check:

- that the slot is in the future
- that the slot doesn't overlap another slot, or that no other slot starts at the same time. [`POST /booking`](#post-booking) finds the slot from its start, so two slots with the same start should be avoided.

The new slot has no tables. Add them with [`POST /slots/{id}/tables`](#post-slotsidtables) or [`POST /slots/{id}/copy`](#post-slotsidcopy).

#### `POST /slots/{id}/tables`

Adds tables to the slot `id` from a [`SlotTablesAdd`](#slottablesadd-object) and answers `200` with the updated [`SlotDetail`](#slotdetail-object). Each table becomes a [`slot_table`](#slot_table) row with all its seats free (`occupied_seats = 0`).

`table_ids` holds the `id` of the tables, not their `number`. [`GET /tables`](#get-tables) shows both.

The request is refused when:

- there is no slot with that `id`
- `table_ids` is empty, or the body is not valid
- the same table is listed twice
- one of the tables doesn't exist
- one of the tables is already in the slot

The errors are listed in [`POST /slots/{id}/tables` errors](#post-slotsidtables-errors), in the order they are checked. All the checks are made before any write, so a refused request adds no table: the request has to be sent again without the wrong ids.

#### `POST /slots/{id}/copy`

Copies the tables of the slot `id` (the source) into the slot `target_slot_id` of a [`CopySlotRequest`](#copyslotrequest-object) (the target), and answers `200` with the [`SlotDetail`](#slotdetail-object) of the target. It is useful to define a new slot like an existing one, for example the same lunch on another day.

Only the list of tables is copied:

- the tables start with all their seats free in the target, even if they have bookings in the source
- the bookings of the source are not copied
- the source and its times don't change
- the tables the target already has are kept, so more tables can be added before or after the copy

The request is refused when:

- the source or the target doesn't exist
- the source and the target are the same slot
- a table of the source is already in the target. Nothing is copied in this case, also not the other tables.

If the source has no tables, nothing is copied and the answer is still a `200`.

### Objects

The objects used by the routes, defined in [`models/table.py`](../backend/app/models/table.py), [`models/slot.py`](../backend/app/models/slot.py), [`models/booking.py`](../backend/app/models/booking.py), [`models/auth.py`](../backend/app/models/auth.py) and [`models/user.py`](../backend/app/models/user.py):

| Object                                         | Used by                                      | Built from                                     |
|------------------------------------------------|----------------------------------------------|------------------------------------------------|
| [`Table`](#table-object)                       | Returned by [`GET /tables`](#get-tables), [`POST /tables`](#post-tables) | [`table`](#table)  |
| [`TableCreate`](#tablecreate-object)           | Body of [`POST /tables`](#post-tables)       | -                                              |
| [`Slot`](#slot-object)                         | Returned by [`GET /slots`](#get-slots), [`POST /slots`](#post-slots) | [`slot`](#slot)        |
| [`SlotCreate`](#slotcreate-object)             | Body of [`POST /slots`](#post-slots)         | -                                              |
| [`SlotTablesAdd`](#slottablesadd-object)       | Body of [`POST /slots/{id}/tables`](#post-slotsidtables) | -                                  |
| [`CopySlotRequest`](#copyslotrequest-object)   | Body of [`POST /slots/{id}/copy`](#post-slotsidcopy) | -                                      |
| [`SlotAvailability`](#slotavailability-object) | Returned by [`GET /slot`](#get-slot)         | [`slot`](#slot), [`slot_table`](#slot_table), [`table`](#table) |
| [`SlotDetail`](#slotdetail-object)             | Returned by [`GET /slot/{id}`](#get-slotid), [`GET /slots/{id}`](#get-slotsid), [`POST /slots/{id}/tables`](#post-slotsidtables), [`POST /slots/{id}/copy`](#post-slotsidcopy) | [`slot`](#slot) |
| [`SlotTableInfo`](#slottableinfo-object)       | Inside [`SlotDetail`](#slotdetail-object)    | [`slot_table`](#slot_table), [`table`](#table) |
| [`BookingCreate`](#bookingcreate-object)       | Body of [`POST /booking`](#post-booking)     | -                                              |
| [`BookingResponse`](#bookingresponse-object)   | Returned by [`POST /booking`](#post-booking) | [`booking`](#booking), [`booking_table`](#booking_table), [`slot`](#slot), [`table`](#table) |
| [`AvailabilityResponse`](#availabilityresponse-object) | Returned by [`GET /availability`](#get-availability) | [`slot_table`](#slot_table), [`table`](#table) |
| [`RegisterRequest`](#registerrequest-object)   | Body of [`POST /register`](#post-register)   | -                                              |
| [`LoginRequest`](#loginrequest-object)         | Body of [`POST /login`](#post-login)         | -                                              |
| [`UserPublic`](#userpublic-object)             | Returned by [`POST /register`](#post-register), [`POST /login`](#post-login), [`GET /users/me`](#get-usersme) | [`user`](#user), or the token for [`GET /users/me`](#get-usersme) |
| [`TokenResponse`](#tokenresponse-object)       | Returned by [`POST /token`](#post-token)     | The token                                      |

The routes don't use the same time zone. [`SlotAvailability`](#slotavailability-object), [`BookingCreate`](#bookingcreate-object), [`BookingResponse`](#bookingresponse-object) and the query of [`GET /availability`](#get-availability) use the hut's local time (`Europe/Rome`). [`SlotDetail`](#slotdetail-object) and [`Slot`](#slot-object) use UTC, so the slot at `12:00:00` in `GET /slot` starts at `11:00:00Z` in `GET /slot/{id}` during winter time.

#### `Table` object

A table of the hut, as stored in [`table`](#table).

| Field      | Type   | Description                                                   |
|------------|--------|---------------------------------------------------------------|
| `id`       | int    | Table identifier, used by [`SlotTablesAdd`](#slottablesadd-object) |
| `number`   | int    | Number of the table, shown to hikers in [`BookingResponse`](#bookingresponse-object) |
| `capacity` | int    | Total seats                                                   |
| `location` | string | Where the table is                                            |

```json
{
  "id": 11,
  "number": 11,
  "capacity": 4,
  "location": "Outside"
}
```

#### `TableCreate` object

The body of [`POST /tables`](#post-tables).

| Field      | Type   | Description                                  |
|------------|--------|----------------------------------------------|
| `number`   | int    | Number of the table, greater than `0` and not used by another table |
| `capacity` | int    | Total seats, greater than `0`                |
| `location` | string | Where the table is, at least 1 character     |

```json
{
  "number": 11,
  "capacity": 4,
  "location": "Outside"
}
```

#### `Slot` object

A slot without its tables, as stored in [`slot`](#slot). Use [`GET /slots/{id}`](#get-slotsid) to see its tables.

| Field        | Type     | Description                                    |
|--------------|----------|------------------------------------------------|
| `id`         | int      | Slot identifier                                |
| `start_time` | datetime | Start of the slot                              |
| `end_time`   | datetime | End of the slot                                |
| `created_by` | int      | Id of the [`user`](#user) who defined the slot |

```json
{
  "id": 4,
  "start_time": "2026-11-08T11:00:00Z",
  "end_time": "2026-11-08T12:30:00Z",
  "created_by": 1
}
```

#### `SlotCreate` object

The body of [`POST /slots`](#post-slots).

| Field        | Type     | Description                                         |
|--------------|----------|-----------------------------------------------------|
| `start_time` | datetime | Start of the slot, with its UTC offset              |
| `end_time`   | datetime | End of the slot, with its UTC offset. Must be after `start_time` |

```json
{
  "start_time": "2026-11-08T12:00:00+01:00",
  "end_time": "2026-11-08T13:30:00+01:00"
}
```

The hut's offset is `+01:00` in winter time and `+02:00` in summer time.

#### `SlotTablesAdd` object

The body of [`POST /slots/{id}/tables`](#post-slotsidtables).

| Field       | Type        | Description                                                       |
|-------------|-------------|-------------------------------------------------------------------|
| `table_ids` | list of int | The `id` of the [`Table`](#table-object)s to add, at least one, each only once |

```json
{
  "table_ids": [1, 2, 3, 4, 5, 6]
}
```

#### `CopySlotRequest` object

The body of [`POST /slots/{id}/copy`](#post-slotsidcopy).

| Field            | Type | Description                                                  |
|------------------|------|--------------------------------------------------------------|
| `target_slot_id` | int  | Id of the slot that receives the tables, greater than `0`    |

```json
{
  "target_slot_id": 5
}
```

#### `SlotAvailability` object

One slot open for booking, with its free seats across all its tables.

| Field             | Type | Description                                           |
|-------------------|------|-------------------------------------------------------|
| `id`              | int  | Slot identifier                                       |
| `date`            | date | Day of the slot, in the hut's local time              |
| `time`            | time | Start of the slot, in the hut's local time            |
| `available_seats` | int  | Free seats, summed over all the tables of the slot    |

```json
{
  "id": 1,
  "date": "2026-10-31",
  "time": "12:00:00",
  "available_seats": 35
}
```

#### `SlotDetail` object

| Field        | Type                                              | Description                                 |
|--------------|---------------------------------------------------|---------------------------------------------|
| `id`         | int                                               | Slot identifier                             |
| `start_time` | datetime                                          | Start of the slot, in UTC                   |
| `end_time`   | datetime                                          | End of the slot, in UTC                     |
| `created_by` | int                                               | Id of the [`user`](#user) who defined the slot |
| `tables`     | list of [`SlotTableInfo`](#slottableinfo-object)  | The tables offered in the slot              |

```json
{
  "id": 1,
  "start_time": "2026-10-31T11:00:00Z",
  "end_time": "2026-10-31T12:30:00Z",
  "created_by": 1,
  "tables": [
    { "id": 1, "table_id": 1, "seats_booked": 4, "seats_free": 0 },
    { "id": 2, "table_id": 2, "seats_booked": 0, "seats_free": 4 }
  ]
}
```

#### `SlotTableInfo` object

One table offered in the slot, with how many of its seats are still free.

| Field          | Type | Description                                                  |
|----------------|------|--------------------------------------------------------------|
| `id`           | int  | Id of the [`slot_table`](#slot_table) row                    |
| `table_id`     | int  | Id of the [`table`](#table) offered                          |
| `seats_booked` | int  | Seats already taken (`occupied_seats`)                       |
| `seats_free`   | int  | Seats still available (`capacity - occupied_seats`)          |

#### `BookingCreate` object

The body of [`POST /booking`](#post-booking).

| Field        | Type | Description                                                                |
|--------------|------|----------------------------------------------------------------------------|
| `date`       | date | Day of the slot, in the hut's local time                                   |
| `time`       | time | Start of the slot, in the hut's local time (`12:00` and `12:00:00` both work) |
| `party_size` | int  | Number of people, greater than `0`                                         |

```json
{
  "date": "2026-10-31",
  "time": "13:30:00",
  "party_size": 11
}
```

#### `BookingResponse` object

The booking just created, with the tables assigned to the party. It is built by `booking_response` in [`services/booking.py`](../backend/app/services/booking.py), not by a model, so `/docs` doesn't show its fields.

| Field             | Type          | Description                                      |
|-------------------|---------------|--------------------------------------------------|
| `id`              | int           | Booking identifier                               |
| `date`            | date          | Day of the slot, in the hut's local time         |
| `time`            | time          | Start of the slot, in the hut's local time       |
| `party_size`      | int           | Number of people                                 |
| `tables`          | list          | The tables assigned, one item per table          |
| `tables[].number` | int           | `number` of the [`table`](#table), not its `id`  |
| `tables[].seats`  | int           | Seats assigned to the party on that table        |

```json
{
  "id": 11,
  "date": "2026-10-31",
  "time": "13:30:00",
  "party_size": 11,
  "tables": [
    { "number": 3, "seats": 6 },
    { "number": 4, "seats": 5 }
  ]
}
```

#### `AvailabilityResponse` object

The answer of [`GET /availability`](#get-availability): whether the party fits, and the tables it would get.

| Field             | Type | Description                                                        |
|-------------------|------|--------------------------------------------------------------------|
| `available`       | bool | `true` if the slot has enough free seats for the party             |
| `tables`          | list | The tables the party would get, one item per table. Empty when `available` is `false` |
| `tables[].number` | int  | `number` of the [`table`](#table), not its `id`                    |
| `tables[].seats`  | int  | Seats the party would get on that table                            |

```json
{
  "available": true,
  "tables": [
    { "number": 3, "seats": 6 },
    { "number": 4, "seats": 5 }
  ]
}
```

When the party doesn't fit:

```json
{
  "available": false,
  "tables": []
}
```

#### `RegisterRequest` object

The body of [`POST /register`](#post-register).

| Field               | Type           | Required | Description                         |
|---------------------|----------------|----------|-------------------------------------|
| `name`              | string         | Yes      | First name, at least 1 character    |
| `surname`           | string         | Yes      | Last name, at least 1 character     |
| `email`             | string         | Yes      | A valid email address               |
| `mobile_number`     | string         | Yes      | Mobile number, at least 1 character |
| `password`          | string         | Yes      | Password, at least 8 characters     |
| `notes`             | string or null | No       | Free notes                          |
| `emergency_contact` | string or null | No       | Emergency contact                   |

```json
{
  "name": "Mario",
  "surname": "Verdi",
  "email": "mario.verdi@mail.example",
  "mobile_number": "+39 333 111 2222",
  "password": "a-long-password",
  "notes": "Vegetarian meals preferred.",
  "emergency_contact": "+39 333 333 4444 - Lucia Verdi"
}
```

#### `LoginRequest` object

The body of [`POST /login`](#post-login).

| Field      | Type   | Description           |
|------------|--------|-----------------------|
| `email`    | string | A valid email address |
| `password` | string | The password          |

```json
{
  "email": "anna.rossi@mail.example",
  "password": "hiker"
}
```

#### `UserPublic` object

What the API shows about a user. It never contains the email, the id or the password hash.

| Field      | Type   | Description                     |
|------------|--------|---------------------------------|
| `username` | string | Username                        |
| `role`     | string | `Hiker`, `Warden` or `Employee` |

```json
{
  "username": "anna.rossi",
  "role": "Hiker"
}
```

#### `TokenResponse` object

The answer of [`POST /token`](#post-token). It is built directly in [`routers/auth.py`](../backend/app/routers/auth.py), not by a model, so `/docs` doesn't show its fields.

| Field          | Type   | Description                                     |
|----------------|--------|-------------------------------------------------|
| `access_token` | string | The signed token, to send as a Bearer token     |
| `token_type`   | string | Always `bearer`                                 |

```json
{
  "access_token": "<token>",
  "token_type": "bearer"
}
```

### Errors

The errors each route can return, in the order they are checked: a request with several problems gets only the first error of its list.

The `400`, `401`, `403`, `404` and `409` are returned as `{ "detail": "<message>" }`. For the `422`, `detail` is the list of the invalid fields and the message is written by FastAPI. Each `401` also has the header `WWW-Authenticate: Bearer`, except `User not found` on [`POST /booking`](#post-booking-errors).

[`GET /slot`](#get-slot) and [`POST /logout`](#post-logout) never return an error.

#### `GET /slot/{id}` errors

| Code  | Message          | When                   |
|-------|------------------|------------------------|
| `422` | Automatic        | `id` is not an integer |
| `404` | `Slot not found` | No slot with that id   |

#### `GET /availability` errors

A party that doesn't fit is not an error: the answer is a `200` with `available: false`.

| Code  | Message                                                   | When                                                                         |
|-------|-----------------------------------------------------------|------------------------------------------------------------------------------|
| `422` | Automatic                                                 | A parameter is missing or not valid, or `party_size` is `0` or less          |
| `400` | `Slot not available`                                      | No slot starts at that `date` and `time`                                     |
| `400` | `Bookings are closed less than two hours before the slot` | The slot starts less than two hours from now                                 |

#### `POST /booking` errors

| Code  | Message                                                   | When                                                          |
|-------|-----------------------------------------------------------|---------------------------------------------------------------|
| `401` | `Not authenticated`                                       | No cookie or token in the request                             |
| `401` | `Invalid or expired token`                                | The cookie or token is not valid                              |
| `403` | `Not enough permissions`                                  | The user is not a `Hiker`                                     |
| `422` | Automatic                                                 | A field is missing or invalid, or `party_size` is `0` or less |
| `401` | `User not found`                                          | The token is valid but its user no longer exists              |
| `400` | `Slot not available`                                      | No slot starts at that `date` and `time`                      |
| `400` | `Bookings are closed less than two hours before the slot` | The slot starts less than two hours from now                  |
| `409` | `A booking already exists for this slot`                  | The hiker already has a booking for that slot                 |
| `409` | `There are not enough seats for this party`               | The slot doesn't have enough free seats                       |

#### `POST /register` errors

| Code  | Message                    | When                                                                                     |
|-------|----------------------------|------------------------------------------------------------------------------------------|
| `422` | Automatic                  | A required field is missing, the email is not valid, or the password is shorter than 8 characters |
| `409` | `Email already registered` | An account already uses that email                                                       |

#### `POST /login` errors

| Code  | Message                   | When                                          |
|-------|---------------------------|-----------------------------------------------|
| `422` | Automatic                 | A field is missing or the email is not valid  |
| `401` | `Wrong email or password` | The email is unknown or the password is wrong |

#### `POST /token` errors

| Code  | Message                      | When                                             |
|-------|------------------------------|--------------------------------------------------|
| `422` | Automatic                    | A field is missing or the body is not form data  |
| `401` | `Wrong username or password` | The email is unknown or the password is wrong    |

#### `GET /users/me` errors

| Code  | Message                    | When                              |
|-------|----------------------------|-----------------------------------|
| `401` | `Not authenticated`        | No cookie or token in the request |
| `401` | `Invalid or expired token` | The cookie or token is not valid  |

#### `GET /tables` errors

| Code  | Message                    | When                                        |
|-------|----------------------------|---------------------------------------------|
| `401` | `Not authenticated`        | No cookie or token in the request           |
| `401` | `Invalid or expired token` | The cookie or token is not valid            |
| `403` | `Not enough permissions`   | The user is not an `Employee` or a `Warden` |

#### `POST /tables` errors

| Code  | Message                       | When                                                                         |
|-------|-------------------------------|------------------------------------------------------------------------------|
| `401` | `Not authenticated`           | No cookie or token in the request                                            |
| `401` | `Invalid or expired token`    | The cookie or token is not valid                                             |
| `403` | `Not enough permissions`      | The user is not an `Employee` or a `Warden`                                  |
| `422` | Automatic                     | A field is missing, `number` or `capacity` is `0` or less, or `location` is empty |
| `409` | `Table number already exists` | Another table already has that `number`                                      |

#### `GET /slots` errors

| Code  | Message                               | When                                        |
|-------|---------------------------------------|---------------------------------------------|
| `401` | `Not authenticated`                   | No cookie or token in the request           |
| `401` | `Invalid or expired token`            | The cookie or token is not valid            |
| `403` | `Not enough permissions`              | The user is not an `Employee` or a `Warden` |
| `422` | Automatic                             | A date is not in the `YYYY-MM-DD` format    |
| `400` | `from_date must not be after to_date` | `from_date` is after `to_date`              |

#### `GET /slots/{id}` errors

| Code  | Message                    | When                                        |
|-------|----------------------------|---------------------------------------------|
| `401` | `Not authenticated`        | No cookie or token in the request           |
| `401` | `Invalid or expired token` | The cookie or token is not valid            |
| `403` | `Not enough permissions`   | The user is not an `Employee` or a `Warden` |
| `422` | Automatic                  | `id` is not an integer                      |
| `404` | `Slot not found`           | No slot with that id                        |

#### `POST /slots` errors

| Code  | Message                    | When                                                                     |
|-------|----------------------------|--------------------------------------------------------------------------|
| `401` | `Not authenticated`        | No cookie or token in the request                                        |
| `401` | `Invalid or expired token` | The cookie or token is not valid                                         |
| `403` | `Not enough permissions`   | The user is not an `Employee` or a `Warden`                              |
| `422` | Automatic                  | A field is missing or not a datetime, or `end_time` is not after `start_time` |

#### `POST /slots/{id}/tables` errors

| Code  | Message                                    | When                                          |
|-------|--------------------------------------------|-----------------------------------------------|
| `401` | `Not authenticated`                        | No cookie or token in the request             |
| `401` | `Invalid or expired token`                 | The cookie or token is not valid              |
| `403` | `Not enough permissions`                   | The user is not an `Employee` or a `Warden`   |
| `422` | Automatic                                  | `id` is not an integer, or `table_ids` is missing or empty |
| `404` | `Slot not found`                           | No slot with that id                          |
| `400` | `A table cannot be added twice`            | The same id is in `table_ids` more than once  |
| `404` | `One or more tables not found`             | An id in `table_ids` is not a table           |
| `409` | `A table is already assigned to this slot` | A table is already in the slot                |

#### `POST /slots/{id}/copy` errors

| Code  | Message                                          | When                                                       |
|-------|--------------------------------------------------|------------------------------------------------------------|
| `401` | `Not authenticated`                              | No cookie or token in the request                          |
| `401` | `Invalid or expired token`                       | The cookie or token is not valid                           |
| `403` | `Not enough permissions`                         | The user is not an `Employee` or a `Warden`                |
| `422` | Automatic                                        | `id` is not an integer, or `target_slot_id` is missing or `0` or less |
| `404` | `Source or target slot not found`                | No slot with the `id` of the path or with `target_slot_id` |
| `400` | `Source and target slots must differ`            | `target_slot_id` is the `id` of the path                   |
| `409` | `A table is already assigned to the target slot` | A table of the source is already in the target             |

[Back to top](#mountain-hut)



## Notification Service
The notification is provided by an external library (already prensent in the requirements.txt), the usage can be split according to the enviroments varibale passed:
- Development usage: Uses a fake mail client that runs through docker. It allows the testing to be automated! Not really usefull for demo or prod-
- Real Usage: Used in prod and demo, this system rely on a real stmp service, for this project it was decided to use Gmail, here are the list of thing to set up!

|Env_variable| default value|description|
|--|--|--|
|SMTP_HOST| smtp.gmail.com | This is the endpoint of the smtp server that is used to send notification email|
|SMTP_PORT| 587 | this is the port that also enable the TLS|
|SMTP_USERNAME| mountainhut14@gmail.com | Username to login in the stmp service|
|SMTP_PASSWORD| (not given here)| `not given`|
|EMAIL_FROM| Mountain Hut <mountainhut14@gmail.com> | the sender name|