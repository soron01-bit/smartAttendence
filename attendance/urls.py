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
    path('institute/register/', views.institute_register_view, name='institute_register'),
    path('institute/login/', views.institute_login_view, name='institute_login'),
    path('institute/logout/', views.institute_logout_view, name='institute_logout'),
    path('institute/dashboard/', views.institute_dashboard_view, name='institute_dashboard'),
    path('api/institute/register/', views.api_institute_register, name='api_institute_register'),
    path('api/institute/login/', views.api_institute_login, name='api_institute_login'),
    path('api/institute/update_details/', views.api_update_institute_details, name='api_update_institute_details'),
    path('api/institute/delete_user/', views.api_institute_delete_user, name='api_institute_delete_user'),
    path('institute/attendance-logs/', views.institute_attendance_logs_view, name='institute_attendance_logs'),
    path('api/institute/delete_attendance/', views.api_institute_delete_attendance, name='api_institute_delete_attendance'),
    path('api/institute/delete/', views.api_institute_delete, name='api_institute_delete'),
]
