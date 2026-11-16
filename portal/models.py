import hashlib
import secrets
import uuid
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone


def uniqid():
    return uuid.uuid4().hex[:13]


def new_otp():
    return secrets.randbelow(900000) + 100000


def private_storage():
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


class PasswordMixin(models.Model):
    password = models.CharField(max_length=255)

    class Meta:
        abstract = True

    def set_password(self, raw):
        self.password = make_password(raw)

    def check_password(self, raw):
        def upgrade(raw_password):
            # Called when the stored hash is the old unsalted SHA-256 one.
            self.set_password(raw_password)
            self.save(update_fields=["password"])

        return check_password(raw, self.password, setter=upgrade)


class Admin(PasswordMixin):
    id = models.CharField(primary_key=True, max_length=255, default=uniqid, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, unique=True)

    class Meta:
        db_table = "admin"

    def __str__(self):
        return self.name


class Account(PasswordMixin):
    UNVERIFIED = "unverified"
    VERIFIED = "Verified"
    ACTIVE = "active"
    DEACTIVATED = "deactivate"
    MAX_OTP_ATTEMPTS = 5

    id = models.CharField(primary_key=True, max_length=255, default=uniqid, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, unique=True)
    mobile = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    otp = models.IntegerField(null=True, blank=True)
    otp_attempts = models.PositiveSmallIntegerField(default=0)
    authentication = models.CharField(max_length=255, default=UNVERIFIED)
    status = models.CharField(max_length=255, default=ACTIVE)
    bantime = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name

    @property
    def is_verified(self):
        return self.authentication != self.UNVERIFIED

    def is_banned(self):
        """True while a ban is running; lifts the ban once it has expired."""
        if self.status != self.DEACTIVATED:
            return False
        if self.bantime and self.bantime <= timezone.now():
            self.unban()
            return False
        return True

    def ban(self):
        self.status = self.DEACTIVATED
        self.bantime = timezone.now() + timedelta(days=settings.BAN_DAYS)
        self.save(update_fields=["status", "bantime"])

    def unban(self):
        self.status = self.ACTIVE
        self.bantime = timezone.now()
        self.save(update_fields=["status", "bantime"])

    def issue_otp(self):
        self.otp = new_otp()
        self.otp_attempts = 0
        self.save(update_fields=["otp", "otp_attempts"])
        return self.otp

    def verify_otp(self, value):
        """Check a submitted code.  After too many misses the code is voided."""
        if self.otp is None:
            return False
        if str(value).strip() == str(self.otp):
            self.authentication = self.VERIFIED
            self.otp = None
            self.otp_attempts = 0
            self.save(update_fields=["authentication", "otp", "otp_attempts"])
            return True
        self.otp_attempts += 1
        if self.otp_attempts >= self.MAX_OTP_ATTEMPTS:
            self.otp = None
        self.save(update_fields=["otp", "otp_attempts"])
        return False


class Employer(Account):
    companyname = models.CharField("company name", max_length=255)
    position = models.CharField(max_length=255, default="employer", editable=False)

    class Meta:
        db_table = "employer"


class User(Account):
    GENDER_CHOICES = [
        ("Male", "Male"),
        ("Female", "Female"),
        ("prefer not to say", "Prefer not to Say"),
    ]

    gender = models.CharField(max_length=255, choices=GENDER_CHOICES, blank=True)
    position = models.CharField(max_length=255, default="user", editable=False)
    education = models.CharField(max_length=255, blank=True)
    skill = models.CharField(max_length=255, blank=True)
    experience = models.CharField(max_length=255, blank=True)
    additional = models.CharField(max_length=255, blank=True)
    image = models.FileField(upload_to="profile/", max_length=255, blank=True)

    class Meta:
        db_table = "user"


class Category(models.Model):
    name = models.CharField(max_length=255)
    admin = models.ForeignKey(Admin, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        db_table = "category"
        ordering = ["id"]

    def __str__(self):
        return self.name


class Package(models.Model):
    name = models.CharField(max_length=255)
    numberofpost = models.PositiveIntegerField("number of posts")
    price = models.PositiveIntegerField()
    admin = models.ForeignKey(Admin, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        db_table = "package"
        ordering = ["id"]

    def __str__(self):
        return self.name


class BuyPackage(models.Model):
    """Running balance per employer: posts left and total money paid."""

    employer = models.OneToOneField(Employer, on_delete=models.CASCADE, related_name="balance")
    numberofpost = models.IntegerField(default=0)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        db_table = "buypackage"


class Payment(models.Model):
    PENDING = "PENDING"
    VALID = "VALID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    status = models.CharField(max_length=255, default=PENDING)
    transid = models.CharField(max_length=255, unique=True)
    cardtype = models.CharField(max_length=255, blank=True)
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="payments")
    package = models.ForeignKey(Package, null=True, on_delete=models.SET_NULL)
    # Copied from the package at checkout so later price edits or a deleted
    # package cannot change what was bought.
    package_name = models.CharField(max_length=255, blank=True)
    numberofpost = models.PositiveIntegerField(default=0)
    transtime = models.DateTimeField(default=timezone.now)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "payment"
        ordering = ["-transtime"]


class JobPost(models.Model):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

    TYPE_CHOICES = [
        ("Part Time", "Part Time"),
        ("Full Time", "Full Time"),
        ("Work From Home", "Work From Home"),
        ("Remote", "Remote"),
        ("Others", "Others"),
    ]

    id = models.CharField(primary_key=True, max_length=255, default=uniqid, editable=False)
    title = models.CharField(max_length=255)
    companyname = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    location = models.CharField(max_length=255)
    type = models.CharField(max_length=255, choices=TYPE_CHOICES)
    requirement = models.CharField(max_length=255)
    education = models.CharField(max_length=255)
    experience = models.CharField(max_length=255)
    salary = models.PositiveIntegerField(help_text="In thousands (k)")
    deadline = models.DateTimeField()
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="jobposts")
    editlimit = models.IntegerField(default=1)   # edits the employer still has
    status = models.CharField(max_length=255, default=PENDING)

    class Meta:
        db_table = "jobpost"
        ordering = ["deadline"]

    def __str__(self):
        return self.title

    @classmethod
    def open_jobs(cls):
        """Approved posts whose deadline has not passed -- what seekers see."""
        return cls.objects.filter(status=cls.APPROVED, deadline__gt=timezone.now())


class JobApply(models.Model):
    APPLIED = "applied"
    INTERVIEW = "interview"
    REJECTED = "rejected"

    id = models.CharField(primary_key=True, max_length=255, default=uniqid, editable=False)
    cv = models.FileField(upload_to="cv/", storage=private_storage, max_length=300)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    job = models.ForeignKey(JobPost, on_delete=models.CASCADE, related_name="applications")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="applications")
    applytime = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=255, default=APPLIED)

    class Meta:
        db_table = "jobapply"
        ordering = ["-applytime"]
        constraints = [
            models.UniqueConstraint(fields=["job", "user"], name="one_application_per_job"),
        ]


class Interview(models.Model):
    id = models.CharField(primary_key=True, max_length=255, default=uniqid, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="interviews")
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="interviews")
    jobpost = models.ForeignKey(JobPost, on_delete=models.CASCADE, related_name="interviews")
    jobapply = models.OneToOneField(JobApply, on_delete=models.CASCADE, related_name="interview")
    meetingid = models.CharField("meeting ID", max_length=255)
    time = models.DateTimeField()
    url = models.URLField("meeting link", max_length=255)
    password = models.CharField("meeting password", max_length=255, blank=True)

    class Meta:
        db_table = "interview"
        ordering = ["time"]


class ContactUs(models.Model):
    id = models.CharField(primary_key=True, max_length=255, default=uniqid, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    mobile = models.CharField(max_length=15)
    comment = models.TextField(max_length=500)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "contactus"
        ordering = ["-created"]


class AuthToken(models.Model):
    ADMIN, EMPLOYER, USER = "admin", "employer", "user"
    key_hash = models.CharField(max_length=64, unique=True)
    role = models.CharField(max_length=10)
    account_id = models.CharField(max_length=255)
    created = models.DateTimeField(auto_now_add=True)
    expires = models.DateTimeField()

    class Meta:
        db_table = "authtoken"
        indexes = [models.Index(fields=["role", "account_id"])]

    @staticmethod
    def hash(key):
        return hashlib.sha256(key.encode()).hexdigest()

    @classmethod
    def issue(cls, role, account):
        cls.objects.filter(expires__lt=timezone.now()).delete()
        key = secrets.token_urlsafe(32)
        cls.objects.create(
            key_hash=cls.hash(key), role=role, account_id=account.pk,
            expires=timezone.now() + timedelta(days=settings.TOKEN_LIFETIME_DAYS),
        )
        return key
