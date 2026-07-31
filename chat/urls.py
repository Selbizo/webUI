from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('health/', views.health_check, name='health_check'),
    path('api/chat/', views.chat_api, name='chat_api'),
    path('api/models/', views.get_models, name='get_models'),
    path('api/sessions/', views.get_user_sessions, name='get_user_sessions'),
    path('api/sessions/create/', views.create_session, name='create_session'),
    path('api/sessions/save/', views.save_session, name='save_session'),
    path('api/sessions/delete/', views.delete_session, name='delete_session'),
    path('api/sessions/load/', views.load_session_messages, name='load_session_messages'),
]
