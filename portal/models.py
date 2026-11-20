from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models

from common.models import CreatedAtUpdatedAtBaseModel, NameSlugDescriptionBaseModel


def private_storage():
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


class EmployerProfile(CreatedAtUpdatedAtBaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employer_profile"
    )
    companyname = models.CharField("company name", max_length=255)

    def __str__(self):
        return self.companyname


class SeekerProfile(CreatedAtUpdatedAtBaseModel):
    GENDER_CHOICES = [
        ("Male", "Male"),
        ("Female", "Female"),
        ("prefer not to say", "Prefer not to Say"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="seeker_profile"
    )
    gender = models.CharField(max_length=32, choices=GENDER_CHOICES, blank=True)
    education = models.CharField(max_length=255, blank=True)
    skill = models.CharField(max_length=255, blank=True)
    experience = models.CharField(max_length=255, blank=True)
    additional = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return str(self.user)



class Category(NameSlugDescriptionBaseModel):
    # created_by (from the base model) records which admin added it.

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Package(CreatedAtUpdatedAtBaseModel):
    name = models.CharField(max_length=255)
    numberofpost = models.PositiveIntegerField("number of posts")
    price = models.PositiveIntegerField()

    class Meta:
        ordering = ["price"]

    def __str__(self):
        return self.name



class BuyPackage(CreatedAtUpdatedAtBaseModel):
    """Running balance per employer: posts left and total money paid."""

    employer = models.OneToOneField(
        EmployerProfile, on_delete=models.CASCADE, related_name="balance"
    )
    numberofpost = models.IntegerField(default=0)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(numberofpost__gte=0), name="post_balance_not_negative"
            ),
        ]


class Payment(CreatedAtUpdatedAtBaseModel):
    PENDING = "PENDING"
    VALID = "VALID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    STATUS_CHOICES = [(s, s) for s in (PENDING, VALID, FAILED, CANCELLED)]

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PENDING)
    transid = models.CharField(max_length=255, unique=True)
    cardtype = models.CharField(max_length=255, blank=True)
    employer = models.ForeignKey(
        EmployerProfile, on_delete=models.CASCADE, related_name="payments"
    )
    package = models.ForeignKey(Package, null=True, blank=True, on_delete=models.SET_NULL)
    package_name = models.CharField(max_length=255, blank=True)
    numberofpost = models.PositiveIntegerField(default=0)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["-created_at"]



class JobPost(CreatedAtUpdatedAtBaseModel):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    STATUS_CHOICES = [(s, s.title()) for s in (PENDING, APPROVED, REJECTED)]

    TYPE_CHOICES = [
        ("Part Time", "Part Time"),
        ("Full Time", "Full Time"),
        ("Work From Home", "Work From Home"),
        ("Remote", "Remote"),
        ("Others", "Others"),
    ]

    title = models.CharField(max_length=255)
    companyname = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="jobposts")
    location = models.CharField(max_length=255)
    type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    requirement = models.CharField(max_length=255)
    education = models.CharField(max_length=255)
    experience = models.CharField(max_length=255)
    salary = models.PositiveIntegerField(help_text="In thousands (k)")
    deadline = models.DateTimeField()
    employer = models.ForeignKey(
        EmployerProfile, on_delete=models.CASCADE, related_name="jobposts"
    )
    editlimit = models.IntegerField(default=1)  # edits the employer still has
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PENDING)

    class Meta:
        ordering = ["deadline"]

    def __str__(self):
        return self.title

    @classmethod
    def open_jobs(cls):
        from django.utils import timezone

        return cls.objects.filter(status=cls.APPROVED, deadline__gt=timezone.now())


class JobApply(CreatedAtUpdatedAtBaseModel):
    APPLIED = "applied"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    STATUS_CHOICES = [(s, s.title()) for s in (APPLIED, INTERVIEW, REJECTED)]

    cv = models.FileField(upload_to="cv/", storage=private_storage, max_length=300)
    job = models.ForeignKey(JobPost, on_delete=models.CASCADE, related_name="applications")
    seeker = models.ForeignKey(
        SeekerProfile, on_delete=models.CASCADE, related_name="applications"
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=APPLIED)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["job", "seeker"], name="one_application_per_job"),
        ]


class Interview(CreatedAtUpdatedAtBaseModel):
    jobapply = models.OneToOneField(
        JobApply, on_delete=models.CASCADE, related_name="interview"
    )
    meetingid = models.CharField("meeting ID", max_length=255)
    time = models.DateTimeField()
    url = models.URLField("meeting link", max_length=255)
    password = models.CharField("meeting password", max_length=255, blank=True)

    class Meta:
        ordering = ["time"]


class ContactUs(CreatedAtUpdatedAtBaseModel):
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    mobile = models.CharField(max_length=24)
    comment = models.TextField(max_length=500)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "contact us messages"