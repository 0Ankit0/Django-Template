from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers

# Create your views here.
@cache_page(60 * 15)  
@vary_on_headers('Authorization')
class TestView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = 'tenancy'

    def get(self, request):
        return Response({"message": "Hello, World!"})