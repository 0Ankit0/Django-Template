from django.shortcuts import render

def custom_400_view(request, exception):
    """Custom view to handle 400 Bad Request errors."""
    return render(request, 'errors/400.html', status=400)

def custom_403_view(request, exception):
    """Custom view to handle 403 Forbidden errors."""
    return render(request, 'errors/403.html', status=403)

def custom_404_view(request, exception):
    """Custom view to handle 404 Not Found errors."""
    return render(request, 'errors/404.html', status=404)

def custom_500_view(request):
    """Custom view to handle 500 Internal Server errors."""
    return render(request, 'errors/500.html', status=500)

# Additional custom error views can be added here as needed.