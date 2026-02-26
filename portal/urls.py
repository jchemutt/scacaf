# portal/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("newsletter/subscribe/", views.newsletter_subscribe, name="newsletter_subscribe"),
]