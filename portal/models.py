from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from common.models import CreatedAtUpdatedAtBaseModel, NameSlugDescriptionBaseModel
from organisations.enums import GenderChoices
from portal.enums import PaymentStatusChoices, JobTypeChoices, JobPostStatusChoices, JobApplyStatusChoices

User = get_user_model()


def private_storage():
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


class EmployerProfile(CreatedAtUpdatedAtBaseModel):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="employer_profile",
        verbose_name=_("User"),
    )
    companyname = models.CharField(max_length=255, verbose_name=_("Company Name"))

    class Meta:
        verbose_name = _("Employer Profile")
        verbose_name_plural = _("Employer Profiles")
        ordering = ["-created_at", "-updated_at"]

    def __str__(self):
        return f"{self.companyname}"


class SeekerProfile(CreatedAtUpdatedAtBaseModel):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="seeker_profile",
        verbose_name=_("User"),
    )
    gender = models.CharField(
        max_length=32,
        choices=GenderChoices.choices,
        blank=True,
        null=True,
        verbose_name=_("Gender"),
    )
    education = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("Education")
    )
    skill = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("Skill")
    )
    experience = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("Experience")
    )
    additional = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("Additional")
    )

    class Meta:
        verbose_name = _("Seeker Profile")
        verbose_name_plural = _("Seeker Profiles")
        ordering = ["-created_at", "-updated_at"]

    def __str__(self):
        return f"{self.user}"


class Category(NameSlugDescriptionBaseModel):
    # created_by (from the base model) records which admin added it.

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}"


class Package(CreatedAtUpdatedAtBaseModel):
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    numberofpost = models.PositiveIntegerField(verbose_name=_("Number of Posts"))
    price = models.PositiveIntegerField(verbose_name=_("Price"))

    class Meta:
        verbose_name = _("Package")
        verbose_name_plural = _("Packages")
        ordering = ["price"]

    def __str__(self):
        return f"{self.name}"


class BuyPackage(CreatedAtUpdatedAtBaseModel):
    """Running balance per employer: posts left and total money paid."""

    employer = models.OneToOneField(
        EmployerProfile,
        on_delete=models.CASCADE,
        related_name="balance",
        verbose_name=_("Employer"),
    )
    numberofpost = models.IntegerField(default=0, verbose_name=_("Number of Posts"))
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name=_("Amount")
    )

    class Meta:
        verbose_name = _("Buy Package")
        verbose_name_plural = _("Buy Packages")
        ordering = ["-created_at", "-updated_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(numberofpost__gte=0),
                name="post_balance_not_negative",
            ),
        ]

    def __str__(self):
        return f"{self.employer} ({self.numberofpost} posts)"


class Payment(CreatedAtUpdatedAtBaseModel):
    status = models.CharField(
        max_length=16,
        choices=PaymentStatusChoices.choices,
        default=PaymentStatusChoices.PENDING,
        verbose_name=_("Status"),
    )
    transid = models.CharField(
        max_length=255, unique=True, verbose_name=_("Transaction ID")
    )
    cardtype = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("Card Type")
    )
    employer = models.ForeignKey(
        EmployerProfile,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name=_("Employer"),
    )
    package = models.ForeignKey(
        Package,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("Package"),
    )
    package_name = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("Package Name")
    )
    numberofpost = models.PositiveIntegerField(
        default=0, verbose_name=_("Number of Posts")
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Amount")
    )

    class Meta:
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")
        ordering = ["-created_at", "-updated_at"]

    def __str__(self):
        return f"{self.transid} - {self.employer} ({self.status})"


class JobPost(CreatedAtUpdatedAtBaseModel):
    title = models.CharField(max_length=255, verbose_name=_("Title"))
    companyname = models.CharField(max_length=255, verbose_name=_("Company Name"))
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="jobposts",
        verbose_name=_("Category"),
    )
    location = models.CharField(max_length=255, verbose_name=_("Location"))
    type = models.CharField(
        max_length=32,
        choices=JobTypeChoices.choices,
        verbose_name=_("Type"),
    )
    requirement = models.CharField(max_length=255, verbose_name=_("Requirement"))
    education = models.CharField(max_length=255, verbose_name=_("Education"))
    experience = models.CharField(max_length=255, verbose_name=_("Experience"))
    salary = models.PositiveIntegerField(
        help_text=_("In thousands (k)"), verbose_name=_("Salary")
    )
    deadline = models.DateTimeField(verbose_name=_("Deadline"))
    employer = models.ForeignKey(
        EmployerProfile,
        on_delete=models.CASCADE,
        related_name="jobposts",
        verbose_name=_("Employer"),
    )
    editlimit = models.IntegerField(
        default=1,
        help_text=_("Edits the employer still has"),
        verbose_name=_("Edit Limit"),
    )
    status = models.CharField(
        max_length=16,
        choices=JobPostStatusChoices.choices,
        default=JobPostStatusChoices.PENDING,
        verbose_name=_("Status"),
    )

    class Meta:
        verbose_name = _("Job Post")
        verbose_name_plural = _("Job Posts")
        ordering = ["deadline"]

    def __str__(self):
        return f"{self.title}"

    @classmethod
    def open_jobs(cls):
        return cls.objects.filter(
            status=JobPostStatusChoices.APPROVED, deadline__gt=timezone.now()
        )


class JobApply(CreatedAtUpdatedAtBaseModel):
    cv = models.FileField(
        upload_to="cv/",
        storage=private_storage,
        max_length=300,
        verbose_name=_("CV"),
    )
    job = models.ForeignKey(
        JobPost,
        on_delete=models.CASCADE,
        related_name="applications",
        verbose_name=_("Job"),
    )
    seeker = models.ForeignKey(
        SeekerProfile,
        on_delete=models.CASCADE,
        related_name="applications",
        verbose_name=_("Seeker"),
    )
    status = models.CharField(
        max_length=16,
        choices=JobApplyStatusChoices.choices,
        default=JobApplyStatusChoices.APPLIED,
        verbose_name=_("Status"),
    )

    class Meta:
        verbose_name = _("Job Application")
        verbose_name_plural = _("Job Applications")
        ordering = ["-created_at", "-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "seeker"], name="one_application_per_job"
            ),
        ]

    def __str__(self):
        return f"{self.seeker} - {self.job} ({self.status})"


class Interview(CreatedAtUpdatedAtBaseModel):
    jobapply = models.OneToOneField(
        JobApply,
        on_delete=models.CASCADE,
        related_name="interview",
        verbose_name=_("Job Application"),
    )
    meetingid = models.CharField(max_length=255, verbose_name=_("Meeting ID"))
    time = models.DateTimeField(verbose_name=_("Time"))
    url = models.URLField(max_length=255, verbose_name=_("Meeting Link"))
    password = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("Meeting Password")
    )

    class Meta:
        verbose_name = _("Interview")
        verbose_name_plural = _("Interviews")
        ordering = ["time"]

    def __str__(self):
        return f"{self.jobapply} @ {self.time}"


class ContactUs(CreatedAtUpdatedAtBaseModel):
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    email = models.EmailField(max_length=255, verbose_name=_("Email"))
    mobile = models.CharField(max_length=24, verbose_name=_("Mobile"))
    comment = models.TextField(max_length=500, verbose_name=_("Comment"))

    class Meta:
        verbose_name = _("Contact Us Message")
        verbose_name_plural = _("Contact Us Messages")
        ordering = ["-created_at", "-updated_at"]

    def __str__(self):
        return f"{self.name} - {self.email}"