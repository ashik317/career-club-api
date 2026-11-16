# Career Club API

Base URL: `http://127.0.0.1:8000/api/`  All bodies and answers are JSON,
except file uploads (multipart/form-data) and the CV download (PDF).

## Authentication

1. `POST .../login/` with `{"email", "password"}` returns `{"token", "account"}`.
2. Send the token on every other request: `Authorization: Token <token>`
3. `POST /api/logout/` deletes the token. Tokens expire after 7 days.

There are three kinds of account, each with its own login. A token only opens
the endpoints of its own kind (others answer 403; no/invalid token answers 401).

Errors look like `{"detail": "...", "code": "..."}`, or for invalid fields
`{"field": ["message"]}` with status 400.

## Public

| Method | Path | |
|---|---|---|
| GET | `/api/` | Entry point |
| GET | `/api/categories/` | Job categories |
| GET | `/api/packages/` | Post packages and prices |
| POST | `/api/contact/` | `name, email, mobile, comment` |
| POST | `/api/logout/` | Delete the token sent with the request |

## Job seeker - `/api/user/`

| Method | Path | |
|---|---|---|
| POST | `signup/` | `name, email, mobile, gender, location, password` (8+ chars). E-mails an OTP |
| POST | `verify-otp/` | `email, otp` |
| POST | `resend-otp/` | `email, password` |
| POST | `login/` | `email, password`. 403 `unverified` (new OTP sent) or `banned` |
| GET | `me/` | Logged-in account |
| GET, PATCH | `profile/` | `name, mobile, gender, location, education, skill, experience, additional, image` (jpg/png, multipart) |
| GET | `jobs/` | Open jobs. Filters: `?keyword= &location= &category=<id> &quick=deadline24\|parttime\|wfh` |
| GET | `jobs/<id>/` | One job, with `applied: true/false` |
| POST | `jobs/<id>/apply/` | multipart with a PDF in `cv`. 409 if already applied |
| GET | `applications/` | My applications and their status (`applied`, `interview`, `rejected`) |
| GET | `interviews/` | My interview schedule |
| GET | `interview-tips/` | Tips list |

## Employer - `/api/employer/`

| Method | Path | |
|---|---|---|
| POST | `signup/` | `name, companyname, location, email, mobile, password` |
| POST | `verify-otp/`, `resend-otp/`, `login/` | Same as job seeker |
| GET | `me/` | Logged-in account |
| GET | `dashboard/` | Totals: job posts, applications, interviews, paid, posts remaining |
| GET | `my-package/` | Purchase history and balance |
| POST | `packages/<id>/checkout/` | Start a purchase. Returns `gateway_url` (send the browser there) or, in simulation mode, `simulate_url` |
| GET | `payments/<transid>/` | Status of one payment: `PENDING`, `VALID`, `FAILED`, `CANCELLED` |
| POST | `payments/<transid>/simulate/` | Debug only: `{"outcome": "pay"\|"fail"\|"cancel"}` |
| GET, POST | `jobs/` | List my posts / create one: `title, category, location, type, requirement, education, experience, salary, deadline`. Uses one post from the balance (402 if none). Status starts as `pending` |
| GET, PATCH | `jobs/<id>/` | Edit once (not title/category); goes back to `pending`. 409 after that |
| GET | `jobs/<id>/applications/` | Applicants, each with a `cv_url` |
| GET | `applications/<id>/cv/` | The CV as PDF (`?download=1` for attachment). Needs the token |
| POST | `applications/<id>/interview/` | `meetingid, time, url, password` |
| POST | `applications/<id>/reject/` | |
| GET | `interviews/` | Interview list |

`type` is one of: `Part Time`, `Full Time`, `Work From Home`, `Remote`, `Others`.
Dates use ISO format, e.g. `2026-12-31T17:00:00+06:00`.

`payments/success/`, `payments/fail/` and `payments/cancel/` are called by
SSLCommerz, not by your front-end. They redirect the browser to
`PAYMENT_RETURN_URL?result=success|fail|cancel&tran_id=...`; your front-end can
then confirm with `GET payments/<transid>/`.

## Admin - `/api/admin/`

| Method | Path | |
|---|---|---|
| POST | `signup/` | `name, email, password` (only while `ADMIN_SIGNUP_ENABLED`) |
| POST | `login/` | |
| GET | `me/`, `dashboard/` | |
| GET | `users/`, `employers/` | All accounts |
| POST | `users/<id>/toggle/`, `employers/<id>/toggle/` | Deactivate for 7 days / activate again |
| GET, POST | `packages/` | `name, numberofpost, price` |
| GET, PUT, PATCH, DELETE | `packages/<id>/` | |
| GET, POST | `categories/` | `name` |
| GET, PUT, PATCH, DELETE | `categories/<id>/` | DELETE also removes that category's job posts |
| GET | `payments/` | All completed transactions |
| GET | `employer-payments/` | Total paid and posts left per employer |
| GET | `jobs/` | All job posts (`?status=pending`) |
| POST | `jobs/<id>/decide/` | `{"decision": "approve"\|"reject"}` |
| GET | `messages/` | Contact-us messages |

## Try it

(On Windows PowerShell use `curl.exe`, not `curl`.)

```bash
# log in as the sample employer
curl -X POST http://127.0.0.1:8000/api/employer/login/ \
     -H "Content-Type: application/json" \
     -d '{"email": "minhajulsiam786@gmail.com", "password": "1234"}'

# use the token from the answer
curl http://127.0.0.1:8000/api/employer/dashboard/ -H "Authorization: Token PASTE_TOKEN_HERE"

# apply for a job with a CV (job seeker token)
curl -X POST http://127.0.0.1:8000/api/user/jobs/JOB_ID/apply/ \
     -H "Authorization: Token PASTE_TOKEN_HERE" -F "cv=@my_cv.pdf"
```
