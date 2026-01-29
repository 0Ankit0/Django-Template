from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import ListView

from . import models


class NotificationListView(LoginRequiredMixin, ListView):
    """List all notifications."""
    template_name = 'notifications/list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    login_url = reverse_lazy('iam:login')
    
    def get_queryset(self):
        return models.Notification.objects.filter(
            user=self.request.user
        ).order_by('-created_at')


@login_required
def mark_notification_read(request, pk):
    """Mark a notification as read (HTMX endpoint)."""
    notification = get_object_or_404(
        models.Notification, pk=pk, user=request.user
    )
    notification.is_read = True
    notification.save()
    
    if request.headers.get('HX-Request'):
        return render(request, 'notifications/partials/notification_item.html', {
            'notification': notification
        })
    
    return redirect('notifications:list')


@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read."""
    models.Notification.objects.filter(
        user=request.user, is_read=False
    ).update(is_read=True)
    
    messages.success(request, 'All notifications marked as read.')
    
    if request.headers.get('HX-Request'):
        return HttpResponse('')
    
    return redirect('notifications:list')

