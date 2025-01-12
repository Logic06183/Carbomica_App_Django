from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('facilities/', views.facilities, name='facilities'),
    path('add-facility/', views.add_facility, name='add_facility'),
    path('interventions/', views.interventions, name='interventions'),
    path('optimize/<int:facility_id>/', views.optimize_interventions, name='optimize_interventions'),
    path('optimization-results/<int:scenario_id>/', views.optimization_results, name='optimization_results'),
]
