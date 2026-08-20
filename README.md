# Clinic Booking System API

A FastAPI REST API for booking, cancelling, rescheduling, and discovering 30-minute doctor appointments.

# Section 1: System Design

## 1. System Overview & Architecture

The clinic booking system is designed as a modular, stateless REST API built to handle appointment scheduling for 5 doctors. The core architecture follows a layered pattern (Router $\rightarrow$ Service/Business Logic $\rightarrow$ Repository/Database Layer) to ensure clean separation of concerns, testability, and maintainability.

## 2. Data Models

- **Doctor**: Represents the clinic's medical professionals.
- `id` (UUID / Integer, Primary Key)
- `name` (String)
- `specialization` (String)

- **WorkingHours**: Defines the weekly working schedule for each doctor.
- `id` (Primary Key)
- `doctor_id` (Foreign Key $\rightarrow$ `Doctor`)
- `day_of_week` (Integer: 0 = Monday to 6 = Sunday)
- `start_time` (Time, e.g., `09:00:00`)
- `end_time` (Time, e.g., `17:00:00`)

- **Patient**: Stores basic user details for booking appointments.
- `id` (Primary Key)
- `name` (String)
- `email` (String, Unique)

- **Appointment**: Tracks active, cancelled, or rescheduled bookings.
- `id` (Primary Key)
- `doctor_id` (Foreign Key $\rightarrow$ `Doctor`)
- `patient_id` (Foreign Key $\rightarrow$ `Patient`)
- `start_time` (DateTime, exact start of the 30-minute slot)
- `end_time` (DateTime, exactly 30 minutes after `start_time`)
- `status` (Enum: `BOOKED`, `CANCELLED`, `RESCHEDULED`)
- `cancellation_reason` (String, Nullable)

---

## 3. Key Design Decisions & Trade-offs

### A. Dynamic Slot Generation vs. Pre-generated Slot Tables

- **Decision**: Instead of pre-generating and storing thousands of slot rows in the database for future dates, available 30-minute slots are **computed dynamically** on request.
- **How it works**: When a client calls `GET /doctors/{id}/availability`, the system fetches the doctor's working hours for that specific weekday, slices the time range into 30-minute increments, and queries existing active appointments for that day to filter out already booked slots.
- **Trade-off**:
- _Pros_: Keeps the database lightweight, easily handles ad-hoc schedule changes or vacation days without messy slot cleanups.
- _Cons_: Slightly higher computational overhead per availability request, which is easily mitigated with database indexing on `doctor_id` and `start_time`.

### B. Concurrency Control & Double-Booking Prevention

- **Decision**: To ensure two patients cannot book the exact same 30-minute slot simultaneously, the system relies on database transactions combined with **row-level locking** (`SELECT ... FOR UPDATE`) or a unique database constraint on `(doctor_id, start_time)` for active bookings.
- **Trade-off**: Prevents race conditions at the database level rather than application level, guaranteeing data integrity under high traffic.

### C. Validation Rules

- Bookings must not be in the past.
- Bookings must fall strictly within the doctor's defined `WorkingHours` for that day.
- (Bonus implementation) Enforces a minimum 1-hour buffer between current time and the requested slot time to prevent last-minute chaos.

## Features

- `POST /appointments`: validates patient, doctor, 30-minute boundary, one-hour notice, working hours, and conflict.
- `GET /doctors/{id}/availability?date=YYYY-MM-DD`: available 30-minute slots.
- `PATCH /appointments/{id}/cancel`: records a reason and releases the slot.
- `PATCH /appointments/{id}/reschedule`: validates the destination slot and releases the original one.
- `GET /patients/{id}/appointments`: bonus endpoint for upcoming appointments, sorted by date.
- Interactive API documentation: `/docs`; health check: `/health`.

## Run locally

Requires Python 3.10+ and a running local PostgreSQL server (pgAdmin is suitable for creating and managing the database).

### 1. Create the database in pgAdmin

Open pgAdmin, connect to your local PostgreSQL server, then right-click **Databases** → **Create** → **Database**. Set the database name to `clinic_booking` and save it.

This guide uses the default PostgreSQL user, `postgres`. If you created a separate user such as `clinic_user`, substitute that username in the connection string below.

### 2. Open a terminal in the project folder

In VS Code, choose **Terminal** → **New Terminal**, then run:

```powershell
cd C:\Users\USER\Desktop\clinic-booking-system
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configure the database connection

The API reads its database connection from the `DATABASE_URL` environment variable. Set it in the same terminal that will run the application.

**PowerShell** (the prompt begins with `PS`):

```powershell
$pgUser = 'postgres'
$pgPassword = 'YOUR_POSTGRES_PASSWORD'
$encodedPassword = [System.Uri]::EscapeDataString($pgPassword)
$env:DATABASE_URL = "postgresql+psycopg2://${pgUser}:$encodedPassword@localhost:5432/clinic_booking"
```

Using single quotes around the password prevents PowerShell from expanding special characters such as `$`. `EscapeDataString` makes characters such as `@`, `:`, and `/` safe in the connection URL.

**Command Prompt / CMD** (the prompt does not begin with `PS`):

```cmd
set "DATABASE_URL=postgresql+psycopg2://postgres:YOUR_POSTGRES_PASSWORD@localhost:5432/clinic_booking"
```

If the CMD password contains URL-special characters, use PowerShell instead. The environment variable lasts only for the current terminal session, so set it again after opening a new terminal.

### 4. Seed data and start the API

```powershell
python -m app.seed
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`. The seed command creates five doctors (IDs 1–5), weekday 09:00–17:00 working hours, and one patient (ID 1). It is safe to run again; existing sample data is not duplicated. Use a future weekday time at least one hour away, for example:

```json
POST /appointments
{"doctor_id": 1, "patient_id": 1, "start_time": "2026-08-21T10:00:00"}
```

### 5. Run tests

Stop the API with `Ctrl+C`, then run:

```powershell
pytest
```

To confirm PostgreSQL is selected before starting the application:

```powershell
python -c "from app.database import engine; from sqlalchemy import text; c=engine.connect(); print(c.execute(text('select current_database()')).scalar()); c.close()"
```

Expected output: `clinic_booking`.

> The included dependency ranges support modern Python versions; GitHub Actions uses Python 3.10 for a stable CI baseline.

## AI reflection

1. I used AI to help structure the FastAPI modules, identify validation cases, draft tests, and improve this documentation and deployment checklist.
2. A useful prompt was: “Review this appointment workflow for race conditions and cancellation behaviour.” It led to the partial unique index design, which keeps an active slot unique without blocking a new booking after cancellation.
3. An initial suggestion treated an ordinary unique `(doctor_id, start_time)` index as sufficient. That was incomplete because it would prevent a cancelled slot from becoming bookable again. I caught it by writing the cancellation/rebooking test and changed it to a partial index.
4. I independently chose dynamic slot generation because a five-doctor clinic does not need persistent future slot rows, and chose a one-hour booking buffer because it is explicitly offered as a bonus and is practical for clinic operations.
