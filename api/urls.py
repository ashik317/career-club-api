# from django.urls import path
#
# from portal.models import AuthToken, Employer, User
# from . import accounts, admin, employer, public, user
# from .auth import IsEmployer, IsJobSeeker
#
# app_name = "api"
#
# user_account = accounts.make_account_views(
#     AuthToken.USER, User, UserSignupSerializer, UserSerializer, IsJobSeeker)
# employer_account = accounts.make_account_views(
#     AuthToken.EMPLOYER, Employer, EmployerSignupSerializer, EmployerSerializer, IsEmployer)
#
# urlpatterns = [
#     path("", public.root, name="root"),
#     path("categories/", public.categories, name="categories"),
#     path("packages/", public.packages, name="packages"),
#     path("contact/", public.contact, name="contact"),
#     path("logout/", accounts.logout, name="logout"),
#
#     # --- Job seeker ---------------------------------------------------------
#     path("user/signup/", user_account["signup"], name="user_signup"),
#     path("user/verify-otp/", user_account["verify_otp"], name="user_verify_otp"),
#     path("user/resend-otp/", user_account["resend_otp"], name="user_resend_otp"),
#     path("user/login/", user_account["login"], name="user_login"),
#     path("user/me/", user_account["me"], name="user_me"),
#     path("user/profile/", user.profile, name="user_profile"),
#     path("user/jobs/", user.jobs, name="user_jobs"),
#     path("user/jobs/<str:pk>/", user.job_detail, name="user_job_detail"),
#     path("user/jobs/<str:pk>/apply/", user.job_apply, name="user_job_apply"),
#     path("user/applications/", user.applications, name="user_applications"),
#     path("user/interviews/", user.interviews, name="user_interviews"),
#     path("user/interview-tips/", user.interview_tips, name="user_interview_tips"),
#
#     # --- Employer -----------------------------------------------------------
#     path("employer/signup/", employer_account["signup"], name="employer_signup"),
#     path("employer/verify-otp/", employer_account["verify_otp"], name="employer_verify_otp"),
#     path("employer/resend-otp/", employer_account["resend_otp"], name="employer_resend_otp"),
#     path("employer/login/", employer_account["login"], name="employer_login"),
#     path("employer/me/", employer_account["me"], name="employer_me"),
#     path("employer/dashboard/", employer.dashboard, name="employer_dashboard"),
#     path("employer/my-package/", employer.my_package, name="employer_my_package"),
#     path("employer/packages/<int:package_id>/checkout/", employer.checkout,
#          name="employer_checkout"),
#     path("employer/payments/success/", employer.payment_success, name="payment_success"),
#     path("employer/payments/fail/", employer.payment_fail, name="payment_fail"),
#     path("employer/payments/cancel/", employer.payment_cancel, name="payment_cancel"),
#     path("employer/payments/<str:transid>/", employer.payment_detail, name="payment_detail"),
#     path("employer/payments/<str:transid>/simulate/", employer.payment_simulate,
#          name="payment_simulate"),
#     path("employer/jobs/", employer.jobs, name="employer_jobs"),
#     path("employer/jobs/<str:pk>/", employer.job_detail, name="employer_job_detail"),
#     path("employer/jobs/<str:pk>/applications/", employer.job_applications,
#          name="employer_job_applications"),
#     path("employer/applications/<str:pk>/cv/", employer.cv, name="employer_cv"),
#     path("employer/applications/<str:pk>/interview/", employer.interview,
#          name="employer_interview"),
#     path("employer/applications/<str:pk>/reject/", employer.application_reject,
#          name="employer_application_reject"),
#     path("employer/interviews/", employer.interviews, name="employer_interviews"),
#
#     # --- Admin --------------------------------------------------------------
#     path("admin/signup/", admin.signup, name="admin_signup"),
#     path("admin/login/", admin.login, name="admin_login"),
#     path("admin/me/", admin.me, name="admin_me"),
#     path("admin/dashboard/", admin.dashboard, name="admin_dashboard"),
#     path("admin/users/", admin.user_list, name="admin_users"),
#     path("admin/users/<str:pk>/toggle/", admin.user_toggle, name="admin_user_toggle"),
#     path("admin/employers/", admin.employer_list, name="admin_employers"),
#     path("admin/employers/<str:pk>/toggle/", admin.employer_toggle,
#          name="admin_employer_toggle"),
#     path("admin/packages/", admin.packages, name="admin_packages"),
#     path("admin/packages/<int:pk>/", admin.package_detail, name="admin_package_detail"),
#     path("admin/categories/", admin.categories, name="admin_categories"),
#     path("admin/categories/<int:pk>/", admin.category_detail, name="admin_category_detail"),
#     path("admin/payments/", admin.payments, name="admin_payments"),
#     path("admin/employer-payments/", admin.employer_payments, name="admin_employer_payments"),
#     path("admin/jobs/", admin.jobs, name="admin_jobs"),
#     path("admin/jobs/<str:pk>/decide/", admin.job_decide, name="admin_job_decide"),
#     path("admin/messages/", admin.contact_messages, name="admin_messages"),
# ]
