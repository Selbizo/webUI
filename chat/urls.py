from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('health/', views.health_check, name='health_check'),
    path('api/chat/', views.chat_api, name='chat_api'),
    path('api/models/', views.get_models, name='get_models'),
]
