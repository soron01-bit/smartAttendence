from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('register/', views.register, name='register'),
    path('attendance/', views.attendance, name='attendance'),
    path('api/register/', views.api_register, name='api_register'),
    path('api/match/', views.api_match, name='api_match'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('api/login/', views.api_login, name='api_login'),
    path('api/update_profile/', views.api_update_profile, name='api_update_profile'),
    path('api/rescan_face/', views.api_rescan_face, name='api_rescan_face'),
]
