from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('convert/', views.convert_view, name='convert'),
    path('status/<uuid:document_id>/', views.check_conversion_status, name='conversion_status'),
    path('download/<uuid:document_id>/', views.download_view, name='download'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('transactions/', views.transactions_view, name='transactions'),
    path('add-balance/', views.add_balance_view, name='add_balance'),
]