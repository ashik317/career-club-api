"""
End-to-end tests of the API.  Run with:  python manage.py test
"""
import re
import shutil
import tempfile
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from . import payments
from .models import (
    Admin, AuthToken, BuyPackage, Category, ContactUs, Employer, Interview, JobApply,
    JobPost, Package, Payment, User,
)

PDF = b"%PDF-1.4\n%fake cv\n"
TMP = tempfile.mkdtemp()
SEED_EMPLOYER = "632ccd2d496d0"


def url(name, *args):
    return reverse(f"api:{name}", args=args)


def future(days=5):
    return (timezone.now() + timedelta(days=days)).isoformat()


@override_settings(PAYMENT_SIMULATION=True, ADMIN_SIGNUP_ENABLED=True, PAYMENT_RETURN_URL="",
                   PRIVATE_MEDIA_ROOT=TMP + "/private", MEDIA_ROOT=TMP + "/media")
class APITests(APITestCase):
    fixtures = ["career_club"]

    def setUp(self):
        cache.clear()       # reset the login throttle between tests

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    # --- helpers ------------------------------------------------------------

    def otp_from_mail(self):
        return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

    def use(self, token):
        if token:
            self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        else:
            self.client.credentials()

    def as_admin(self):
        admin = Admin(name="Boss", email="boss@example.com")
        admin.set_password("adminpass1")
        admin.save()
        r = self.client.post(url("admin_login"), {"email": admin.email, "password": "adminpass1"})
        self.assertEqual(r.status_code, 200, r.data)
        self.use(r.data["token"])
        return admin

    def as_seed_employer(self):
        r = self.client.post(url("employer_login"),
                             {"email": "minhajulsiam786@gmail.com", "password": "1234"})
        self.assertEqual(r.status_code, 200, r.data)
        self.use(r.data["token"])
        return Employer.objects.get(pk=SEED_EMPLOYER)

    def make_user(self, email="seeker@example.com"):
        user = User(name="Seeker", email=email, mobile="017", location="Dhaka",
                    authentication=User.VERIFIED)
        user.set_password("seekerpass1")
        user.save()
        return user

    def as_user(self, user):
        r = self.client.post(url("user_login"), {"email": user.email, "password": "seekerpass1"})
        self.assertEqual(r.status_code, 200, r.data)
        self.use(r.data["token"])
        return r.data["token"]

    def open_job(self, employer, **extra):
        data = dict(title="Django Dev", companyname=employer.companyname,
                    category=Category.objects.get(pk=4), location="Dhaka", type="Part Time",
                    requirement="Python", education="BSc", experience="1 year", salary=40,
                    deadline=timezone.now() + timedelta(days=3), employer=employer,
                    status=JobPost.APPROVED)
        data.update(extra)
        return JobPost.objects.create(**data)

    def titles(self, **params):
        r = self.client.get(url("user_jobs"), params)
        self.assertEqual(r.status_code, 200)
        return [job["title"] for job in r.data]

    # --- public & access control --------------------------------------------

    def test_public_endpoints(self):
        self.assertEqual(self.client.get(url("root")).status_code, 200)
        self.assertEqual(len(self.client.get(url("categories")).data), 7)
        self.assertEqual(len(self.client.get(url("packages")).data), 3)
        r = self.client.post(url("contact"), {"name": "A", "email": "a@example.com",
                                              "mobile": "0170", "comment": "Hello"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(ContactUs.objects.count(), 1)

    def test_every_private_endpoint_needs_the_right_role(self):
        private = ["user_me", "user_profile", "user_jobs", "user_applications",
                   "user_interviews", "employer_me", "employer_dashboard", "employer_jobs",
                   "employer_my_package", "employer_interviews", "admin_me",
                   "admin_dashboard", "admin_users", "admin_employers", "admin_packages",
                   "admin_categories", "admin_payments", "admin_jobs", "admin_messages"]
        for name in private:
            self.assertEqual(self.client.get(url(name)).status_code, 401, name)
        self.use("not-a-real-token")
        self.assertEqual(self.client.get(url("admin_users")).status_code, 401)

        self.as_user(self.make_user())       # a job seeker's token opens only user_*
        for name in private:
            expected = 200 if name.startswith("user_") else 403
            self.assertEqual(self.client.get(url(name)).status_code, expected, name)
        self.assertEqual(self.client.post(url("admin_user_toggle", "x")).status_code, 403)
        self.assertEqual(self.client.post(url("employer_checkout", 1)).status_code, 403)

    def test_responses_never_contain_password_or_otp(self):
        self.as_admin()
        self.make_user()
        for name in ["admin_users", "admin_employers"]:
            for row in self.client.get(url(name)).data:
                self.assertNotIn("password", row)
                self.assertNotIn("otp", row)

    # --- sign-up, OTP, login, logout ----------------------------------------

    def test_user_signup_otp_login_logout(self):
        r = self.client.post(url("user_signup"), {
            "name": "New", "email": "New@Example.com", "mobile": "0171", "gender": "Male",
            "location": "Dhaka", "password": "longpassword"})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertNotIn("password", r.data["account"])
        user = User.objects.get(email="new@example.com")
        self.assertTrue(user.password.startswith("pbkdf2_"))
        otp = self.otp_from_mail()

        creds = {"email": "new@example.com", "password": "longpassword"}
        r = self.client.post(url("user_login"), creds)          # not verified yet
        self.assertEqual((r.status_code, r.data["code"]), (403, "unverified"))
        self.assertNotEqual(self.otp_from_mail(), None)
        otp = self.otp_from_mail()                              # login re-sent a code

        r = self.client.post(url("user_verify_otp"), {"email": creds["email"], "otp": "000000"})
        self.assertEqual((r.status_code, r.data["code"]), (400, "invalid_otp"))
        r = self.client.post(url("user_verify_otp"), {"email": creds["email"], "otp": otp})
        self.assertEqual(r.status_code, 200, r.data)

        r = self.client.post(url("user_login"), dict(creds, password="wrong"))
        self.assertEqual(r.status_code, 401)
        r = self.client.post(url("user_login"), creds)
        self.assertEqual(r.status_code, 200)
        token = r.data["token"]
        self.assertFalse(AuthToken.objects.filter(key_hash=token).exists())   # stored hashed
        self.use(token)
        self.assertEqual(self.client.get(url("user_me")).data["email"], "new@example.com")

        self.assertEqual(self.client.post(url("logout")).status_code, 204)
        self.assertEqual(self.client.get(url("user_me")).status_code, 401)

    def test_signup_validation(self):
        self.make_user()
        r = self.client.post(url("user_signup"), {
            "name": "X", "email": "SEEKER@example.com", "mobile": "1", "location": "D",
            "password": "short"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("already registered", r.data["email"][0])
        self.assertIn("password", r.data)

    def test_otp_voided_after_too_many_wrong_attempts_then_resend(self):
        data = {"name": "E", "companyname": "Co", "location": "D", "email": "e@example.com",
                "mobile": "1", "password": "longpassword"}
        self.assertEqual(self.client.post(url("employer_signup"), data).status_code, 201)
        real = self.otp_from_mail()
        wrong = "111111" if real != "111111" else "222222"
        for _ in range(Employer.MAX_OTP_ATTEMPTS):
            r = self.client.post(url("employer_verify_otp"), {"email": data["email"], "otp": wrong})
        self.assertEqual(r.data["code"], "otp_voided")
        r = self.client.post(url("employer_verify_otp"), {"email": data["email"], "otp": real})
        self.assertEqual(r.status_code, 400)

        r = self.client.post(url("employer_resend_otp"), {"email": data["email"], "password": "bad"})
        self.assertEqual(r.status_code, 401)
        r = self.client.post(url("employer_resend_otp"),
                             {"email": data["email"], "password": "longpassword"})
        self.assertEqual(r.status_code, 200)
        r = self.client.post(url("employer_verify_otp"),
                             {"email": data["email"], "otp": self.otp_from_mail()})
        self.assertEqual(r.status_code, 200)

    def test_legacy_sha256_password_is_upgraded_on_login(self):
        employer = self.as_seed_employer()
        self.assertTrue(employer.password.startswith("pbkdf2_"))
        self.use(None)
        self.as_seed_employer()

    def test_ban_blocks_login_and_kills_existing_token(self):
        user = self.make_user()
        self.as_user(user)
        user.ban()
        self.assertEqual(self.client.get(url("user_me")).status_code, 401)
        self.use(None)
        r = self.client.post(url("user_login"), {"email": user.email, "password": "seekerpass1"})
        self.assertEqual((r.status_code, r.data["code"]), (403, "banned"))
        User.objects.filter(pk=user.pk).update(bantime=timezone.now() - timedelta(minutes=1))
        self.as_user(user)       # ban expired

    def test_expired_token_is_rejected(self):
        self.as_user(self.make_user())
        AuthToken.objects.update(expires=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get(url("user_me")).status_code, 401)

    def test_login_is_throttled(self):
        codes = {self.client.post(url("user_login"), {"email": "x@example.com", "password": "p"})
                 .status_code for _ in range(25)}
        self.assertIn(429, codes)

    # --- admin --------------------------------------------------------------

    def test_admin_dashboard_and_crud(self):
        admin = self.as_admin()
        self.assertEqual(self.client.get(url("admin_dashboard")).data["total_payment"], "250.00")
        for name in ["admin_users", "admin_employers", "admin_payments",
                     "admin_employer_payments", "admin_jobs", "admin_messages"]:
            self.assertEqual(self.client.get(url(name)).status_code, 200, name)

        r = self.client.post(url("admin_categories"), {"name": "DevOps"})
        self.assertEqual(r.status_code, 201)
        pk = r.data["id"]
        self.assertEqual(Category.objects.get(pk=pk).admin, admin)
        self.assertEqual(self.client.patch(url("admin_category_detail", pk),
                                           {"name": "SRE"}).data["name"], "SRE")
        self.assertEqual(self.client.delete(url("admin_category_detail", pk)).status_code, 204)
        self.assertFalse(Category.objects.filter(pk=pk).exists())

        r = self.client.post(url("admin_packages"), {"name": "Mega", "numberofpost": 20, "price": 300})
        pk = r.data["id"]
        r = self.client.put(url("admin_package_detail", pk),
                            {"name": "Mega", "numberofpost": 25, "price": 300})
        self.assertEqual(r.data["numberofpost"], 25)
        self.assertEqual(self.client.post(url("admin_packages"), {"name": "Bad"}).status_code, 400)
        self.client.delete(url("admin_package_detail", pk))
        self.assertFalse(Package.objects.filter(pk=pk).exists())

    def test_admin_toggle_and_job_decision(self):
        self.as_admin()
        r = self.client.post(url("admin_employer_toggle", SEED_EMPLOYER))
        self.assertEqual(r.data["status"], "deactivate")
        employer = Employer.objects.get(pk=SEED_EMPLOYER)
        self.assertGreater(employer.bantime, timezone.now() + timedelta(days=6))
        r = self.client.post(url("admin_employer_toggle", SEED_EMPLOYER))
        self.assertEqual(r.data["status"], "active")

        job = self.open_job(employer, status=JobPost.PENDING)
        self.assertEqual(len(self.client.get(url("admin_jobs"), {"status": "pending"}).data), 1)
        self.assertEqual(self.client.post(url("admin_job_decide", job.pk), {}).status_code, 400)
        r = self.client.post(url("admin_job_decide", job.pk), {"decision": "approve"})
        self.assertEqual(r.data["status"], "approved")

    @override_settings(ADMIN_SIGNUP_ENABLED=False)
    def test_admin_signup_can_be_switched_off(self):
        r = self.client.post(url("admin_signup"), {"name": "a", "email": "a@example.com",
                                                   "password": "longpassword"})
        self.assertEqual(r.status_code, 403)

    def test_admin_signup(self):
        r = self.client.post(url("admin_signup"), {"name": "a", "email": "a@example.com",
                                                   "password": "longpassword"})
        self.assertEqual(r.status_code, 201)
        r = self.client.post(url("admin_login"), {"email": "a@example.com", "password": "longpassword"})
        self.assertEqual(r.status_code, 200)

    # --- employer -----------------------------------------------------------

    def test_simulated_purchase_credits_posts_once(self):
        employer = self.as_seed_employer()
        r = self.client.post(url("employer_checkout", 2))
        self.assertEqual(r.status_code, 201)
        transid = r.data["payment"]["transid"]
        self.assertIn(transid, r.data["simulate_url"])
        r = self.client.post(url("payment_simulate", transid), {"outcome": "pay"})
        self.assertEqual(r.data["status"], "VALID")
        balance = BuyPackage.objects.get(employer=employer)
        self.assertEqual((balance.numberofpost, str(balance.amount)), (14, "350.00"))
        # replaying does nothing
        self.assertEqual(self.client.post(url("payment_simulate", transid),
                                          {"outcome": "pay"}).status_code, 404)
        balance.refresh_from_db()
        self.assertEqual(balance.numberofpost, 14)
        r = self.client.get(url("employer_my_package"))
        self.assertEqual((r.data["posts_remaining"], len(r.data["payments"])), (14, 4))
        self.assertEqual(self.client.get(url("payment_detail", transid)).data["status"], "VALID")
        self.assertEqual(self.client.get(url("employer_dashboard")).data["total_payment"], "350.00")

    @override_settings(PAYMENT_SIMULATION=False, SSLCOMMERZ_STORE_ID="s",
                       SSLCOMMERZ_STORE_PASSWORD="p",
                       PAYMENT_RETURN_URL="https://app.example/paid")
    def test_gateway_callback_trusts_only_the_validation_api(self):
        employer = self.as_seed_employer()
        with mock.patch.object(payments, "_request",
                               return_value={"GatewayPageURL": "https://sandbox.example/pay"}):
            r = self.client.post(url("employer_checkout", 1))
        self.assertEqual(r.data["gateway_url"], "https://sandbox.example/pay")
        payment = Payment.objects.get(status=Payment.PENDING)
        self.use(None)              # the gateway callback carries no token

        def reply(**changes):
            base = {"status": "VALID", "tran_id": payment.transid, "amount": "50.00",
                    "currency_type": "BDT", "currency_amount": "50.00", "card_type": "VISA"}
            base.update(changes)
            return mock.patch.object(payments, "_request", return_value=base)

        def callback():
            return self.client.post(url("payment_success"),
                                    {"tran_id": payment.transid, "val_id": "v"},
                                    format="multipart")

        before = BuyPackage.objects.get(employer=employer).numberofpost
        for bad in [{"status": "FAILED"}, {"tran_id": "other"}, {"currency_amount": "1.00"}]:
            Payment.objects.filter(pk=payment.pk).update(status=Payment.PENDING)
            with reply(**bad):
                r = callback()
            self.assertEqual(r.status_code, 302)
            self.assertIn("https://app.example/paid?result=fail", r["Location"])
            self.assertEqual(BuyPackage.objects.get(employer=employer).numberofpost, before)

        Payment.objects.filter(pk=payment.pk).update(status=Payment.PENDING)
        with reply():
            r = callback()
        self.assertIn("result=success", r["Location"])
        self.assertEqual(BuyPackage.objects.get(employer=employer).numberofpost, before + 2)
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.cardtype), (Payment.VALID, "VISA"))

    def test_job_post_uses_balance_and_edit_is_allowed_once(self):
        employer = self.as_seed_employer()
        data = {"title": "QA", "category": 4, "location": "Dhaka", "type": "Full Time",
                "requirement": "Testing", "education": "BSc", "experience": "2y",
                "salary": 30, "deadline": future()}
        r = self.client.post(url("employer_jobs"), data)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["status"], r.data["companyname"]), ("pending", "SwipeWire"))
        pk = r.data["id"]
        self.assertEqual(BuyPackage.objects.get(employer=employer).numberofpost, 8)
        self.assertEqual(len(self.client.get(url("employer_jobs")).data), 4)

        r = self.client.patch(url("employer_job_detail", pk), {"location": "Khulna", "title": "Hacked"})
        self.assertEqual((r.data["location"], r.data["title"], r.data["editlimit"]),
                         ("Khulna", "QA", 0))
        r = self.client.patch(url("employer_job_detail", pk), {"location": "Again"})
        self.assertEqual(r.status_code, 409)

        r = self.client.post(url("employer_jobs"), dict(data, deadline="2020-01-01T10:00:00+06:00"))
        self.assertIn("deadline", r.data)
        self.assertEqual(BuyPackage.objects.get(employer=employer).numberofpost, 8)

        BuyPackage.objects.filter(employer=employer).update(numberofpost=0)
        r = self.client.post(url("employer_jobs"), dict(data, title="Blocked"))
        self.assertEqual((r.status_code, r.data["code"]), (402, "no_posts_remaining"))
        self.assertFalse(JobPost.objects.filter(title="Blocked").exists())

    # --- job seeker + applications + interviews -----------------------------

    def test_search_apply_interview_flow(self):
        employer = Employer.objects.get(pk=SEED_EMPLOYER)
        job = self.open_job(employer)
        self.open_job(employer, title="Hidden pending", status=JobPost.PENDING)
        user = self.make_user()
        user_token = self.as_user(user)

        self.assertEqual(self.titles(), ["Django Dev"])       # seed jobs are past deadline
        self.assertEqual(self.titles(keyword="django"), ["Django Dev"])
        self.assertEqual(self.titles(location="Sylhet"), [])
        self.assertEqual(self.titles(quick="parttime"), ["Django Dev"])
        self.assertEqual(self.titles(quick="wfh"), [])
        self.assertEqual(self.titles(quick="deadline24"), [])
        self.assertEqual(self.titles(category=4), ["Django Dev"])
        self.assertEqual(self.titles(category=1), [])
        self.assertFalse(self.client.get(url("user_job_detail", job.pk)).data["applied"])
        self.assertEqual(len(self.client.get(url("user_interview_tips")).data["tips"]), 7)

        def apply(name, content):
            return self.client.post(url("user_job_apply", job.pk),
                                    {"cv": SimpleUploadedFile(name, content)}, format="multipart")

        self.assertIn("not a valid PDF", str(apply("cv.pdf", b"<html>").data))
        self.assertIn("Allowed file types", str(apply("cv.exe", PDF).data))
        r = apply("my cv.pdf", PDF)
        self.assertEqual((r.status_code, r.data["status"]), (201, "applied"))
        self.assertEqual(apply("again.pdf", PDF).status_code, 409)
        application = JobApply.objects.get(user=user, job=job)
        self.assertTrue(self.client.get(url("user_job_detail", job.pk)).data["applied"])
        self.assertEqual(len(self.client.get(url("user_applications")).data), 1)

        # a job seeker cannot fetch CVs
        self.assertEqual(self.client.get(url("employer_cv", application.pk)).status_code, 403)

        # another employer cannot see this application
        other = Employer(name="O", companyname="Other", location="D", email="o@example.com",
                         mobile="1", authentication=Employer.VERIFIED)
        other.set_password("otherpass1")
        other.save()
        self.use(None)
        r = self.client.post(url("employer_login"), {"email": other.email, "password": "otherpass1"})
        self.use(r.data["token"])
        for name, method in [("employer_cv", "get"), ("employer_application_reject", "post"),
                             ("employer_interview", "post")]:
            self.assertEqual(getattr(self.client, method)(url(name, application.pk)).status_code,
                             404, name)
        self.assertEqual(self.client.get(url("employer_job_applications", job.pk)).status_code, 404)
        self.assertEqual(self.client.get(url("employer_job_detail", job.pk)).status_code, 404)

        # the owning employer reviews it
        self.use(None)
        self.as_seed_employer()
        r = self.client.get(url("employer_job_applications", job.pk))
        self.assertEqual(r.data[0]["user"]["name"], "Seeker")
        r = self.client.get(r.data[0]["cv_url"], {"download": 1})
        self.assertEqual(b"".join(r.streaming_content), PDF)
        self.assertIn("attachment", r["Content-Disposition"])
        r = self.client.get(url("employer_cv", application.pk))
        self.assertIn("inline", r["Content-Disposition"])
        r.close()

        meeting = {"meetingid": "874", "time": future(2), "url": "https://zoom.example/j/874",
                   "password": "12345"}
        r = self.client.post(url("employer_interview", application.pk),
                             dict(meeting, url="javascript:alert(1)"))
        self.assertIn("url", r.data)
        r = self.client.post(url("employer_interview", application.pk), meeting)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.client.post(url("employer_interview", application.pk),
                                          meeting).status_code, 409)
        application.refresh_from_db()
        self.assertEqual(application.status, JobApply.INTERVIEW)
        self.assertEqual(Interview.objects.get().user, user)
        self.assertEqual(self.client.get(url("employer_interviews")).data[0]["candidate_name"], "Seeker")
        self.assertEqual(self.client.get(url("employer_dashboard")).data["total_interview"], 1)

        self.use(user_token)
        r = self.client.get(url("user_interviews"))
        self.assertEqual(r.data[0]["url"], "https://zoom.example/j/874")
        self.assertEqual(self.client.get(url("user_applications")).data[0]["status"], "interview")

    def test_reject_application_and_profile_update(self):
        employer = Employer.objects.get(pk=SEED_EMPLOYER)
        job = self.open_job(employer)
        user = self.make_user()
        application = JobApply.objects.create(
            job=job, category=job.category, user=user, cv=SimpleUploadedFile("c.pdf", PDF))
        self.as_seed_employer()
        r = self.client.post(url("employer_application_reject", application.pk))
        self.assertEqual(r.data["status"], "rejected")
        self.assertEqual(self.client.post(url("employer_application_reject", application.pk))
                         .status_code, 409)

        self.use(None)
        self.as_user(user)
        r = self.client.patch(url("user_profile"), {
            "name": "Seeker Two", "skill": "Python", "email": "evil@example.com",
            "status": "x", "image": SimpleUploadedFile("me.png", b"\x89PNG fake")},
            format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        user.refresh_from_db()
        self.assertEqual((user.name, user.skill, user.email, user.status),
                         ("Seeker Two", "Python", "seeker@example.com", "active"))
        self.assertTrue(r.data["image"].endswith(".png"))
        r = self.client.patch(url("user_profile"),
                              {"image": SimpleUploadedFile("me.svg", b"<svg/>")}, format="multipart")
        self.assertIn("Allowed file types", str(r.data))
