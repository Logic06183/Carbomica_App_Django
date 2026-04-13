from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('facilities/', views.facilities, name='facilities'),
    path('facilities/<int:facility_id>/', views.facility_detail, name='facility_detail'),
    path('add-facility/', views.add_facility, name='add_facility'),
    path('interventions/', views.interventions, name='interventions'),
    path('optimize/<int:facility_id>/', views.optimize_interventions, name='optimize_interventions'),
    path('optimization-results/<int:scenario_id>/', views.optimization_results, name='optimization_results'),
    path('upload/emissions/', views.upload_emissions, name='upload_emissions'),
    path('upload/interventions/', views.upload_interventions, name='upload_interventions'),
    path('organisation/', views.my_organisation, name='my_organisation'),
]
