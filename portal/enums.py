from django.db import models
from django.utils.translation import gettext_lazy as _


class PaymentStatusChoices(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    VALID = "VALID", _("Valid")
    FAILED = "FAILED", _("Failed")
    CANCELLED = "CANCELLED", _("Cancelled")


class JobPostStatusChoices(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    APPROVED = "APPROVED", _("Approved")
    REJECTED = "REJECTED", _("Rejected")


class JobTypeChoices(models.TextChoices):
    PART_TIME = "PART_TIME", _("Part Time")
    FULL_TIME = "FULL_TIME", _("Full Time")
    WORK_FROM_HOME = "WORK_FROM_HOME", _("Work From Home")
    REMOTE = "REMOTE", _("Remote")
    OTHERS = "OTHERS", _("Others")


class JobApplyStatusChoices(models.TextChoices):
    APPLIED = "APPLIED", _("Applied")
    INTERVIEW = "INTERVIEW", _("Interview")
    REJECTED = "REJECTED", _("Rejected")
