from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('add-facility/', views.add_facility, name='add_facility'),
    path('interventions/', views.interventions, name='interventions'),
]
