import os

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers

from portal.models import (
    Admin, BuyPackage, Category, ContactUs, Employer, Interview, JobApply, JobPost,
    Package, Payment, User,
)


def check_upload(upload, allowed_ext, max_size):
    ext = os.path.splitext(upload.name)[1].lower()
    if ext not in allowed_ext:
        raise serializers.ValidationError(f"Allowed file types: {', '.join(sorted(allowed_ext))}")
    if upload.size > max_size:
        raise serializers.ValidationError(
            f"File is too large (max {max_size // (1024 * 1024)} MB).")
    return upload


def must_be_future(value):
    if value <= timezone.now():
        raise serializers.ValidationError("Please choose a date and time in the future.")
    return value


# --- Accounts ---------------------------------------------------------------

class SignupSerializer(serializers.ModelSerializer):
    """Base for the three sign-up serializers: unique e-mail, hashed password."""

    password = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        email = value.strip().lower()
        if self.Meta.model.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                f"{email} is already registered. Please try with another email.")
        return email

    def create(self, validated_data):
        account = self.Meta.model(**validated_data)
        account.set_password(validated_data["password"])
        account.save()
        return account


class AdminSignupSerializer(SignupSerializer):
    class Meta:
        model = Admin
        fields = ["id", "name", "email", "password"]


class EmployerSignupSerializer(SignupSerializer):
    class Meta:
        model = Employer
        fields = ["id", "name", "companyname", "location", "email", "mobile", "password"]


class UserSignupSerializer(SignupSerializer):
    class Meta:
        model = User
        fields = ["id", "name", "email", "mobile", "gender", "location", "password"]


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class OTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.RegexField(r"^\d{6}$")


class AdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Admin
        fields = ["id", "name", "email"]


class EmployerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employer
        fields = ["id", "name", "companyname", "location", "email", "mobile",
                  "authentication", "status", "bantime"]
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    """Job seeker.  Also the profile serializer: e-mail and status are fixed."""

    class Meta:
        model = User
        fields = ["id", "name", "email", "mobile", "gender", "location", "education",
                  "skill", "experience", "additional", "image",
                  "authentication", "status", "bantime"]
        read_only_fields = ["id", "email", "authentication", "status", "bantime"]

    def validate_image(self, value):
        return check_upload(value, {".jpg", ".jpeg", ".png"}, settings.MAX_IMAGE_SIZE)


# --- Catalogue --------------------------------------------------------------

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class PackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Package
        fields = ["id", "name", "numberofpost", "price"]


# --- Jobs -------------------------------------------------------------------

class JobPostSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = JobPost
        fields = ["id", "title", "companyname", "category", "category_name", "location",
                  "type", "requirement", "education", "experience", "salary", "deadline",
                  "status", "editlimit"]
        read_only_fields = ["id", "companyname", "status", "editlimit"]

    def validate_deadline(self, value):
        return must_be_future(value)


class JobPostEditSerializer(JobPostSerializer):
    """Title and category are fixed once posted, as in the original."""

    class Meta(JobPostSerializer.Meta):
        read_only_fields = JobPostSerializer.Meta.read_only_fields + ["title", "category"]


class JobSearchSerializer(JobPostSerializer):
    """What a job seeker sees; adds whether they already applied."""

    applied = serializers.SerializerMethodField()

    class Meta(JobPostSerializer.Meta):
        fields = [f for f in JobPostSerializer.Meta.fields if f not in ("status", "editlimit")
                  ] + ["applied"]

    def get_applied(self, job):
        return job.id in self.context.get("applied", ())


class ApplySerializer(serializers.ModelSerializer):
    class Meta:
        model = JobApply
        fields = ["cv"]

    def validate_cv(self, value):
        check_upload(value, {".pdf"}, settings.MAX_CV_SIZE)
        if value.read(5) != b"%PDF-":
            raise serializers.ValidationError("That file is not a valid PDF.")
        value.seek(0)
        return value


class InterviewSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source="jobpost.title", read_only=True)
    companyname = serializers.CharField(source="employer.companyname", read_only=True)
    candidate_name = serializers.CharField(source="user.name", read_only=True)
    candidate_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = Interview
        fields = ["id", "job_title", "companyname", "candidate_name", "candidate_email",
                  "meetingid", "time", "url", "password"]

    def validate_time(self, value):
        return must_be_future(value)


class MyApplicationSerializer(serializers.ModelSerializer):
    """An application as its job seeker sees it."""

    job = JobSearchSerializer(read_only=True)

    class Meta:
        model = JobApply
        fields = ["id", "job", "applytime", "status"]


class ReceivedApplicationSerializer(serializers.ModelSerializer):
    """An application as the employer sees it."""

    user = UserSerializer(read_only=True)
    job_title = serializers.CharField(source="job.title", read_only=True)
    cv_url = serializers.SerializerMethodField()

    class Meta:
        model = JobApply
        fields = ["id", "job", "job_title", "user", "applytime", "status", "cv_url"]

    def get_cv_url(self, application):
        # Needs the employer's token; add ?download=1 to force a download.
        path = reverse("api:employer_cv", args=[application.pk])
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path


# --- Payments ---------------------------------------------------------------

class PaymentSerializer(serializers.ModelSerializer):
    companyname = serializers.CharField(source="employer.companyname", read_only=True)
    email = serializers.CharField(source="employer.email", read_only=True)
    location = serializers.CharField(source="employer.location", read_only=True)

    class Meta:
        model = Payment
        fields = ["id", "status", "transid", "cardtype", "package", "package_name",
                  "numberofpost", "amount", "transtime", "companyname", "email", "location"]


class BalanceSerializer(serializers.ModelSerializer):
    employer = serializers.CharField(source="employer_id", read_only=True)
    companyname = serializers.CharField(source="employer.companyname", read_only=True)

    class Meta:
        model = BuyPackage
        fields = ["employer", "companyname", "numberofpost", "amount"]


# --- Contact ----------------------------------------------------------------

class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactUs
        fields = ["id", "name", "email", "mobile", "comment", "created"]
        read_only_fields = ["id", "created"]
