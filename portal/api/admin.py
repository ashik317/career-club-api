"""Admin endpoints (the old /admin/*.php pages)."""
from django.conf import settings
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from ..models import (
    Admin, AuthToken, BuyPackage, Category, ContactUs, Employer, JobApply, JobPost,
    Package, Payment, User,
)
from .accounts import check_credentials, error, public
from .auth import IsAdmin
from .serializers import (
    AdminSerializer, AdminSignupSerializer, BalanceSerializer, CategorySerializer,
    ContactSerializer, EmployerSerializer, JobPostSerializer, PackageSerializer,
    PaymentSerializer, UserSerializer,
)


def admin_view(methods):
    def decorator(view):
        return api_view(methods)(permission_classes([IsAdmin])(view))
    return decorator


@public(["POST"])
def signup(request):
    if not settings.ADMIN_SIGNUP_ENABLED:
        return error("Admin sign-up is disabled.", "signup_disabled", status.HTTP_403_FORBIDDEN)
    serializer = AdminSignupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    admin = serializer.save()
    return Response({"detail": "Registration Successfully.",
                     "account": AdminSerializer(admin).data}, status=status.HTTP_201_CREATED)


@public(["POST"])
def login(request):
    admin, failure = check_credentials(Admin, request.data)
    if failure:
        return failure
    return Response({"token": AuthToken.issue(AuthToken.ADMIN, admin),
                     "account": AdminSerializer(admin).data})


@admin_view(["GET"])
def me(request):
    return Response(AdminSerializer(request.user).data)


@admin_view(["GET"])
def dashboard(request):
    total = Payment.objects.filter(status=Payment.VALID).aggregate(t=Sum("amount"))["t"]
    return Response({
        "total_employers": Employer.objects.count(),
        "total_users": User.objects.count(),
        "total_jobposts": JobPost.objects.count(),
        "total_jobapplies": JobApply.objects.count(),
        "total_payment": f"{total or 0:.2f}",
    })


# --- Users & employers (activate / deactivate) ------------------------------

def _toggle(model, serializer, pk):
    account = get_object_or_404(model, pk=pk)
    if account.status == model.ACTIVE:
        account.ban()           # deactivated for settings.BAN_DAYS days
    else:
        account.unban()
    return Response(serializer(account).data)


@admin_view(["GET"])
def user_list(request):
    return Response(UserSerializer(User.objects.order_by("name"), many=True,
                                   context={"request": request}).data)


@admin_view(["POST"])
def user_toggle(request, pk):
    return _toggle(User, UserSerializer, pk)


@admin_view(["GET"])
def employer_list(request):
    return Response(EmployerSerializer(Employer.objects.order_by("name"), many=True).data)


@admin_view(["POST"])
def employer_toggle(request, pk):
    return _toggle(Employer, EmployerSerializer, pk)


# --- Packages & categories --------------------------------------------------

def _collection(request, model, serializer_class):
    if request.method == "GET":
        return Response(serializer_class(model.objects.all(), many=True).data)
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(admin=request.user)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


def _item(request, model, serializer_class, pk):
    obj = get_object_or_404(model, pk=pk)
    if request.method == "GET":
        return Response(serializer_class(obj).data)
    if request.method == "DELETE":
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = serializer_class(obj, data=request.data, partial=request.method == "PATCH")
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@admin_view(["GET", "POST"])
def packages(request):
    return _collection(request, Package, PackageSerializer)


@admin_view(["GET", "PUT", "PATCH", "DELETE"])
def package_detail(request, pk):
    return _item(request, Package, PackageSerializer, pk)


@admin_view(["GET", "POST"])
def categories(request):
    return _collection(request, Category, CategorySerializer)


@admin_view(["GET", "PUT", "PATCH", "DELETE"])
def category_detail(request, pk):
    # DELETE also removes the category's job posts and their applications
    # (ON DELETE CASCADE in the original schema).
    return _item(request, Category, CategorySerializer, pk)


# --- Payments ---------------------------------------------------------------

@admin_view(["GET"])
def payments(request):
    rows = Payment.objects.filter(status=Payment.VALID).select_related("employer")
    return Response(PaymentSerializer(rows, many=True).data)


@admin_view(["GET"])
def employer_payments(request):
    rows = BuyPackage.objects.select_related("employer")
    return Response(BalanceSerializer(rows, many=True).data)


# --- Job posts (approve / reject) -------------------------------------------

@admin_view(["GET"])
def jobs(request):
    rows = JobPost.objects.select_related("category").order_by("-deadline")
    if request.query_params.get("status"):
        rows = rows.filter(status=request.query_params["status"])
    return Response(JobPostSerializer(rows, many=True).data)


@admin_view(["POST"])
def job_decide(request, pk):
    job = get_object_or_404(JobPost, pk=pk)
    decision = request.data.get("decision")
    if decision not in ("approve", "reject"):
        return error('Send {"decision": "approve"} or {"decision": "reject"}.',
                     "invalid_decision")
    job.status = JobPost.APPROVED if decision == "approve" else JobPost.REJECTED
    job.save(update_fields=["status"])
    return Response(JobPostSerializer(job).data)


# --- Contact messages -------------------------------------------------------

@admin_view(["GET"])
def contact_messages(request):
    return Response(ContactSerializer(ContactUs.objects.all(), many=True).data)
