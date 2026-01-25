from django.shortcuts import render

def get_test_view(request):
    from django.http import JsonResponse
    return JsonResponse({'message': 'This is a test view'})
