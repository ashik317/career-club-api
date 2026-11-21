"""
Job-seeker endpoints (the old /user/*.php pages).

Search, apply, applied jobs, interview schedule, interview tips and profile
were linked from the PHP navbar but their files were missing from the source,
so they are rebuilt here from the database schema.
"""
from datetime import timedelta

from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from portal.models import Interview, JobPost
from .accounts import error
from .auth import IsJobSeeker
from .serializers import (
    ApplySerializer, InterviewSerializer, JobSearchSerializer, MyApplicationSerializer,
    UserSerializer,
)

INTERVIEW_TIPS = [   # placeholder text; the original page was not in the source
    "Read the job post again and note how your experience matches each requirement.",
    "Learn what the company does and prepare two or three questions of your own.",
    "Prepare short examples of past work: the situation, what you did, and the result.",
    "For an online interview, test your camera, microphone and connection beforehand.",
    "Join a few minutes early and keep your CV open in front of you.",
    "Answer the question that was asked; it is fine to pause and think first.",
    "Afterwards, send a short thank-you note.",
]


def user_view(methods):
    def decorator(view):
        return api_view(methods)(permission_classes([IsJobSeeker])(view))
    return decorator


def _context(request):
    applied = set(request.user.applications.values_list("job_id", flat=True))
    return {"request": request, "applied": applied}


@user_view(["GET", "PUT", "PATCH"])
def profile(request):
    """Send multipart/form-data to upload "image" (jpg/png)."""
    if request.method == "GET":
        return Response(UserSerializer(request.user, context={"request": request}).data)
    serializer = UserSerializer(request.user, data=request.data, partial=True,
                                context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@user_view(["GET"])
def jobs(request):
    """
    Open jobs (approved, deadline not passed).  Optional filters:
      ?keyword=    title, requirement or company contains
      ?location=   location contains
      ?category=   category id
      ?quick=      deadline24 | parttime | wfh   (the home page "Quick Links")
    """
    params = request.query_params
    rows = JobPost.open_jobs().select_related("category")
    keyword = params.get("keyword", "").strip()
    location = params.get("location", "").strip()
    if keyword:
        rows = rows.filter(Q(title__icontains=keyword) | Q(requirement__icontains=keyword)
                           | Q(companyname__icontains=keyword))
    if location:
        rows = rows.filter(location__icontains=location)
    if params.get("category", "").isdigit():
        rows = rows.filter(category_id=params["category"])
    quick = params.get("quick")
    if quick == "deadline24":
        rows = rows.filter(deadline__lte=timezone.now() + timedelta(hours=24))
    elif quick == "parttime":
        rows = rows.filter(type__iexact="Part Time")
    elif quick == "wfh":
        rows = rows.filter(type__iexact="Work From Home")
    return Response(JobSearchSerializer(rows, many=True, context=_context(request)).data)


@user_view(["GET"])
def job_detail(request, pk):
    job = get_object_or_404(JobPost.open_jobs().select_related("category"), pk=pk)
    return Response(JobSearchSerializer(job, context=_context(request)).data)


@user_view(["POST"])
def job_apply(request, pk):
    """Apply with a CV: multipart/form-data with a PDF in the "cv" field."""
    job = get_object_or_404(JobPost.open_jobs(), pk=pk)
    already = error("You have already applied for this job.", "already_applied",
                    status.HTTP_409_CONFLICT)
    if request.user.applications.filter(job=job).exists():
        return already
    serializer = ApplySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        application = serializer.save(job=job, category=job.category, user=request.user)
    except IntegrityError:               # two requests at once
        return already
    return Response(MyApplicationSerializer(application, context=_context(request)).data,
                    status=status.HTTP_201_CREATED)


@user_view(["GET"])
def applications(request):
    rows = request.user.applications.select_related("job", "job__category")
    return Response(MyApplicationSerializer(rows, many=True, context=_context(request)).data)


@user_view(["GET"])
def interviews(request):
    rows = (Interview.objects.filter(user=request.user)
            .select_related("jobpost", "employer", "user"))
    return Response(InterviewSerializer(rows, many=True).data)


@user_view(["GET"])
def interview_tips(request):
    return Response({"tips": INTERVIEW_TIPS})
