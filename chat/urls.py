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
    path('api/files/list/', views.list_files_api, name='list_files_api'),
    path('api/files/read/', views.read_file_api, name='read_file_api'),
    path('api/files/search/', views.search_files_api, name='search_files_api'),
    path('api/command/run/', views.run_command_api, name='run_command_api'),
    path('api/files/create/', views.create_file_api, name='create_file_api'),
    path('api/files/update/', views.update_file_api, name='update_file_api'),
    path('api/docx/generate/', views.generate_docx_api, name='generate_docx_api'),
    path('api/patch/apply/', views.apply_patch_api, name='apply_patch_api'),
    path('api/diff/', views.diff_api, name='diff_api'),
    path('api/workspace/set/', views.set_workspace_api, name='set_workspace_api'),
    path('api/workspace/get/', views.get_workspace_api, name='get_workspace_api'),
]
