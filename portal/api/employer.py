"""Employer endpoints (the old /employer/*.php pages)."""
import os
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.http import FileResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .. import payments as gateway
from ..models import BuyPackage, Interview, JobApply, JobPost, Package, Payment
from .accounts import error
from .auth import IsEmployer
from .serializers import (
    BalanceSerializer, InterviewSerializer, JobPostEditSerializer, JobPostSerializer,
    PaymentSerializer, ReceivedApplicationSerializer,
)


def employer_view(methods):
    def decorator(view):
        return api_view(methods)(permission_classes([IsEmployer])(view))
    return decorator


@employer_view(["GET"])
def dashboard(request):
    employer = request.user
    balance = BuyPackage.objects.filter(employer=employer).first()
    return Response({
        "total_jobpost": employer.jobposts.count(),
        "total_application": JobApply.objects.filter(job__employer=employer).count(),
        "total_interview": employer.interviews.count(),
        "total_payment": f"{balance.amount if balance else 0:.2f}",
        "posts_remaining": balance.numberofpost if balance else 0,
    })


# --- Packages & payment -----------------------------------------------------

@employer_view(["GET"])
def my_package(request):
    """Purchase history plus the current balance ("My Package")."""
    employer = request.user
    balance = BuyPackage.objects.filter(employer=employer).first()
    return Response({
        "posts_remaining": balance.numberofpost if balance else 0,
        "total_paid": f"{balance.amount if balance else 0:.2f}",
        "payments": PaymentSerializer(
            employer.payments.filter(status=Payment.VALID), many=True).data,
    })


@employer_view(["POST"])
def checkout(request, package_id):
    """
    Start buying a package.  The answer contains "gateway_url": send the
    browser there to pay.  In simulation mode it contains "simulate_url"
    instead (POST {"outcome": "pay" | "fail" | "cancel"} to it).
    """
    package = get_object_or_404(Package, pk=package_id)
    payment = gateway.create_payment(request.user, package)
    data = {"payment": PaymentSerializer(payment).data}

    def absolute(name, *args):
        return request.build_absolute_uri(reverse(name, args=args))

    if settings.PAYMENT_SIMULATION:
        data["simulate_url"] = absolute("api:payment_simulate", payment.transid)
        return Response(data, status=status.HTTP_201_CREATED)
    try:
        data["gateway_url"] = gateway.start_session(
            payment, absolute("api:payment_success"), absolute("api:payment_fail"),
            absolute("api:payment_cancel"))
    except gateway.GatewayError as exc:
        gateway.close(payment, Payment.FAILED)
        return error(str(exc), "gateway_error", status.HTTP_502_BAD_GATEWAY)
    return Response(data, status=status.HTTP_201_CREATED)


@employer_view(["GET"])
def payment_detail(request, transid):
    """Lets the front-end check how a payment ended after the gateway returns."""
    payment = get_object_or_404(Payment, transid=transid, employer=request.user)
    return Response(PaymentSerializer(payment).data)


@employer_view(["POST"])
def payment_simulate(request, transid):
    """Stand-in for the gateway.  Only exists in DEBUG with no store configured."""
    if not settings.PAYMENT_SIMULATION:
        return error("Not found.", "not_found", status.HTTP_404_NOT_FOUND)
    payment = get_object_or_404(Payment, transid=transid, employer=request.user,
                                status=Payment.PENDING)
    outcome = request.data.get("outcome")
    if outcome == "pay":
        gateway.complete(payment.pk, "SIMULATED")
    elif outcome == "cancel":
        gateway.close(payment, Payment.CANCELLED)
    elif outcome == "fail":
        gateway.close(payment, Payment.FAILED)
    else:
        return error('Send {"outcome": "pay"}, "fail" or "cancel".', "invalid_outcome")
    payment.refresh_from_db()
    return Response(PaymentSerializer(payment).data)


def _gateway_return(result, transid):
    """
    SSLCommerz sends the customer's *browser* to these callbacks, so the
    answer is a redirect to the front-end when PAYMENT_RETURN_URL is set.
    """
    if settings.PAYMENT_RETURN_URL:
        joiner = "&" if "?" in settings.PAYMENT_RETURN_URL else "?"
        query = urlencode({"result": result, "tran_id": transid})
        return HttpResponseRedirect(f"{settings.PAYMENT_RETURN_URL}{joiner}{query}")
    return Response({"result": result, "tran_id": transid})


@api_view(["POST"])
@permission_classes([AllowAny])        # called by the gateway, which has no token
def payment_success(request):
    transid = request.data.get("tran_id", "")
    val_id = request.data.get("val_id", "")
    payment = Payment.objects.filter(transid=transid).first()
    if payment is None or not val_id:
        return _gateway_return("fail", transid)
    if payment.status == Payment.VALID:
        return _gateway_return("success", transid)
    try:
        ok, card_type = gateway.validate(payment, val_id)
    except gateway.GatewayError:
        return _gateway_return("fail", transid)
    if not ok:
        gateway.close(payment, Payment.FAILED)
        return _gateway_return("fail", transid)
    gateway.complete(payment.pk, card_type)
    return _gateway_return("success", transid)


def _closed(request, new_status, result):
    transid = request.data.get("tran_id", "")
    payment = Payment.objects.filter(transid=transid).first()
    if payment:
        gateway.close(payment, new_status)
    return _gateway_return(result, transid)


@api_view(["POST"])
@permission_classes([AllowAny])
def payment_fail(request):
    return _closed(request, Payment.FAILED, "fail")


@api_view(["POST"])
@permission_classes([AllowAny])
def payment_cancel(request):
    return _closed(request, Payment.CANCELLED, "cancel")


# --- Job posts --------------------------------------------------------------

@employer_view(["GET", "POST"])
def jobs(request):
    employer = request.user
    if request.method == "GET":
        rows = employer.jobposts.select_related("category")
        return Response(JobPostSerializer(rows, many=True).data)

    serializer = JobPostSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        # Take one post from the balance; fails if there is none left.
        used = BuyPackage.objects.filter(employer=employer, numberofpost__gt=0).update(
            numberofpost=F("numberofpost") - 1)
        if not used:
            return error("Please buy a package. You have zero post remaining.",
                         "no_posts_remaining", status.HTTP_402_PAYMENT_REQUIRED)
        serializer.save(employer=employer, companyname=employer.companyname)
    # New posts are "pending" until an admin approves them.
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@employer_view(["GET", "PUT", "PATCH"])
def job_detail(request, pk):
    job = get_object_or_404(JobPost, pk=pk, employer=request.user)
    if request.method == "GET":
        return Response(JobPostSerializer(job).data)
    if job.editlimit <= 0:
        return error("This job post has already been edited.", "edit_limit_reached",
                     status.HTTP_409_CONFLICT)
    serializer = JobPostEditSerializer(job, data=request.data,
                                       partial=request.method == "PATCH")
    serializer.is_valid(raise_exception=True)
    # One edit only, and the post goes back to the admin for approval.
    serializer.save(editlimit=0, status=JobPost.PENDING)
    return Response(serializer.data)


# --- Applications, CVs and interviews ---------------------------------------

@employer_view(["GET"])
def job_applications(request, pk):
    job = get_object_or_404(JobPost, pk=pk, employer=request.user)
    rows = job.applications.select_related("user", "job")
    return Response(ReceivedApplicationSerializer(
        rows, many=True, context={"request": request}).data)


def _own_application(request, pk):
    return get_object_or_404(JobApply.objects.select_related("job", "user"),
                             pk=pk, job__employer=request.user)


@employer_view(["GET"])
def cv(request, pk):
    """The applicant's CV as a PDF.  ?download=1 sends it as an attachment."""
    application = _own_application(request, pk)
    try:
        handle = application.cv.open("rb")
    except (FileNotFoundError, ValueError):
        return error("CV not found", "cv_not_found", status.HTTP_404_NOT_FOUND)
    return FileResponse(handle, as_attachment=bool(request.query_params.get("download")),
                        filename=os.path.basename(application.cv.name),
                        content_type="application/pdf")


@employer_view(["POST"])
def interview(request, pk):
    """Invite an applicant: {meetingid, time, url, password}."""
    application = _own_application(request, pk)
    if application.status != JobApply.APPLIED:
        return error("This application has already been handled.", "already_handled",
                     status.HTTP_409_CONFLICT)
    serializer = InterviewSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        serializer.save(user=application.user, employer=request.user,
                        jobpost=application.job, jobapply=application)
        application.status = JobApply.INTERVIEW
        application.save(update_fields=["status"])
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@employer_view(["POST"])
def application_reject(request, pk):
    application = _own_application(request, pk)
    if application.status != JobApply.APPLIED:
        return error("This application has already been handled.", "already_handled",
                     status.HTTP_409_CONFLICT)
    application.status = JobApply.REJECTED
    application.save(update_fields=["status"])
    return Response(ReceivedApplicationSerializer(
        application, context={"request": request}).data)


@employer_view(["GET"])
def interviews(request):
    rows = (Interview.objects.filter(employer=request.user)
            .select_related("user", "jobpost", "employer"))
    return Response(InterviewSerializer(rows, many=True).data)
