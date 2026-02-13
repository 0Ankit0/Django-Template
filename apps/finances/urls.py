from django.urls import path

from . import views

app_name = "finances"

urlpatterns = [
    path("finances/", views.FinancesView.as_view(), name="index"),
    path("finances/payment-methods/", views.PaymentMethodsView.as_view(), name="payment_methods"),
    path("finances/subscription/", views.SubscriptionView.as_view(), name="subscription"),
    path("finances/plans/add/", views.AddPlanView.as_view(), name="add_plan"),
]
