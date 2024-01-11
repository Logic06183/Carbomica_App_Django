from django.urls import path
from . import views

urlpatterns = [
    path("add_facility/", views.add_facility, name="add_facility"),
    # Add more paths here for other views in your app
]