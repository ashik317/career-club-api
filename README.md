# Career Club API (Django REST Framework)

REST API version of the Career Club PHP job portal: job seekers search and
apply for jobs, employers buy post packages and post jobs, admins approve
posts and manage the site. There are no HTML pages; every endpoint answers
JSON. **All endpoints are listed in [API.md](API.md).**

## Run it

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py loaddata career_club      # sample data from the old career_club.sql
python manage.py createadmin you@example.com
python manage.py runserver
```

The API is at http://127.0.0.1:8000/api/

* Sample employer: `minhajulsiam786@gmail.com` / `1234` (`POST /api/employer/login/`)
* Admin: the account made with `createadmin` (`POST /api/admin/login/`)
* Job seeker: sign up with `POST /api/user/signup/`; the OTP e-mail is printed
  in the runserver terminal

The sample job posts have 2022 deadlines, so job seekers will not see them.
Post a new job as the employer and approve it as the admin.

Run the tests with `python manage.py test`.

## Configuration

Copy `.env.example` to `.env`. Nothing is required for local development.

* **Database** - SQLite by default. For MySQL set `DB_ENGINE=mysql` and the
  `DB_*` values, then `pip install mysqlclient`.
* **E-mail** - set `EMAIL_HOST` etc. to send real OTP mails (for Gmail use an
  app password). Otherwise mails are printed in the console.
* **Front-end** - list its origin in `CORS_ALLOWED_ORIGINS` so a browser app
  may call the API. Set `PAYMENT_RETURN_URL` to the front-end page the browser
  should land on after paying.
* **SSLCommerz** - set `SSLCOMMERZ_STORE_ID` and `SSLCOMMERZ_STORE_PASSWORD`.
  With no store id and `DJANGO_DEBUG=true`, checkout returns a `simulate_url`
  instead of a gateway link. On a local machine the real gateway can only call
  back to a URL it can reach, as with the PHP version.
* **Production** - set `DJANGO_DEBUG=false`, `DJANGO_SECRET_KEY`,
  `DJANGO_ALLOWED_HOSTS`, `ADMIN_SIGNUP_ENABLED=false`, serve over HTTPS, and
  serve `media/` (profile pictures) from your web server. Do not serve
  `private_media/` (CVs).

## Where the PHP files went

| PHP | Django |
|-----|--------|
| `database.php`, `database/career_club.sql` | `careerclub/settings.py`, `portal/models.py`, `portal/fixtures/career_club.json` |
| `user/*.php` | `portal/api/user.py` |
| `employer/*.php` | `portal/api/employer.py` |
| `employer/payment_*.php` | `portal/payments.py` + payment endpoints in `api/employer.py` |
| `admin/*.php` | `portal/api/admin.py` |
| `*_login.php`, `*_signup.php`, `*_otpsend.php`, `*_otpverify.php` | `portal/api/accounts.py` (shared by user and employer) |
| PHP sessions | Login tokens: `portal/api/auth.py` |
| HTML in the PHP files, `css/`, navbars | Removed - build the front-end separately |
| `phpmailer/` | Django's built-in `send_mail` |

Routes are in `portal/api/urls.py`; request/response shapes in `portal/api/serializers.py`.

## Endpoints rebuilt from the database schema

These pages were linked from the PHP navbars but their files were not in the
project, so the endpoints were written from the `jobapply`, `interview`,
`contactus` and `user` tables. Adjust them to match your originals.

* Job seeker: search, apply (CV upload), applied jobs, interview schedule,
  interview tips (placeholder text), profile
* Employer: schedule interview / reject application, interview list
* Public: contact us (read them at `GET /api/admin/messages/`)

## What behaves differently from the PHP version

* Queries go through the Django ORM (the PHP built SQL from raw input).
* Passwords are hashed with PBKDF2. Old SHA-256 passwords from the dump still
  work and are upgraded at first login.
* Login returns a token instead of starting a PHP session.
* Approve, reject, activate, deactivate, delete and buy are POST/DELETE
  requests instead of plain links.
* Every admin endpoint requires an admin token (the pages had no check before).
* Login, sign-up and OTP endpoints are rate limited (20 requests a minute per IP).
* Employers can only see their own job posts, applications and CVs.
* Payment: the purchase is recorded before going to the gateway and credited
  only after SSLCommerz's validation API confirms the transaction. Package,
  employer and post count are no longer read from the return URL.
* `employer_buypackage.php?employerid=...` logged in whoever was named in the
  URL; that is gone.
* A new job post can be edited once (the PHP set the limit to 2 but only
  allowed editing at exactly 1, so new posts could never be edited).
* A ban ends by itself after 7 days.
* The OTP is voided after 5 wrong attempts; "Resend" issues a new one.
* Gmail and SSLCommerz credentials are read from `.env`, not the source code.
