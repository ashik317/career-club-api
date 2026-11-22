# from rest_framework import status
# from rest_framework.decorators import api_view, permission_classes
# from rest_framework.permissions import AllowAny
# from rest_framework.response import Response
# from rest_framework.reverse import reverse
#
# from portal.models import Category, Package
# from .accounts import public
# from .serializers import CategorySerializer, ContactSerializer, PackageSerializer
#
#
# @api_view(["GET"])
# @permission_classes([AllowAny])
# def root(request):
#     """Entry point: where each area starts.  The full list is in API.md."""
#     def link(name):
#         return reverse(f"api:{name}", request=request)
#     return Response({
#         "name": "Career Club API",
#         "categories": link("categories"),
#         "packages": link("packages"),
#         "contact": link("contact"),
#         "user_login": link("user_login"),
#         "employer_login": link("employer_login"),
#         "admin_login": link("admin_login"),
#     })
#
#
# @api_view(["GET"])
# @permission_classes([AllowAny])
# def categories(request):
#     return Response(CategorySerializer(Category.objects.all(), many=True).data)
#
#
# @api_view(["GET"])
# @permission_classes([AllowAny])
# def packages(request):
#     return Response(PackageSerializer(Package.objects.all(), many=True).data)
#
#
# @public(["POST"])
# def contact(request):
#     """contactus.php was linked from every login page but missing from the source."""
#     serializer = ContactSerializer(data=request.data)
#     serializer.is_valid(raise_exception=True)
#     serializer.save()
#     return Response({"detail": "Thank you. Your message has been sent."},
#                     status=status.HTTP_201_CREATED)
