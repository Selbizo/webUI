import os
import json
import uuid
from openai import OpenAI
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

LM_STUDIO_BASE_URL = os.environ.get('LM_STUDIO_BASE_URL', 'http://localhost:1234/v1')
DEFAULT_MODEL = os.environ.get('DEFAULT_MODEL', '')

client = OpenAI(
    base_url=LM_STUDIO_BASE_URL,
    api_key='not-needed'
)

def get_available_models():
    try:
        models = client.models.list()
        model_ids = [model.id for model in models.data]
        print(f"Found models: {model_ids}")
        return model_ids
    except Exception as e:
        print(f"Error getting models: {e}")
        return []

def index(request):
    if not request.user.is_authenticated:
        return render(request, 'chat/login.html')
    return render(request, 'chat/index.html')

@csrf_exempt
def login_view(request):
    if request.method == 'GET':
        return render(request, 'chat/login.html')
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
            
            print(f"Login attempt for user: {username}")
            
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                print(f"User {username} authenticated successfully")
                login(request, user)
                return JsonResponse({'success': True})
            else:
                print(f"Authentication failed for user: {username}")
                return JsonResponse({'success': False, 'error': 'Неверные учетные данные'}, status=401)
        except Exception as e:
            print(f"Login error: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def logout_view(request):
    logout(request)
    return redirect('/')

def health_check(request):
    models = get_available_models()
    return JsonResponse({
        'status': 'ready',
        'lm_studio_url': LM_STUDIO_BASE_URL,
        'available_models': models,
        'user': request.user.username if request.user.is_authenticated else None,
        'model_count': len(models)
    })

@csrf_exempt
@require_http_methods(['POST'])
def chat_api(request):
    try:
        data = json.loads(request.body)
        messages = data.get('messages', [])
        model = data.get('model', DEFAULT_MODEL) or (get_available_models()[0] if get_available_models() else '')
        
        if not model:
            return JsonResponse({'error': 'No model specified and no models available'}, status=500)
        
        session_id = data.get('session_id')
        if session_id and request.user.is_authenticated:
            from .models import ChatSession
            try:
                session = ChatSession.objects.get(session_id=session_id, user=request.user)
                stored_messages = session.messages
                messages = stored_messages + messages
            except ChatSession.DoesNotExist:
                pass
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=data.get('temperature', 0.7),
            max_tokens=data.get('max_tokens', -1),
            stream=data.get('stream', False)
        )
        
        if data.get('stream', False):
            from django.http import StreamingHttpResponse
            def event_stream():
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        yield f"data: {json.dumps({'content': chunk.choices[0].delta.content})}\n\n"
                if session_id:
                    yield f"data: {json.dumps({'session_id': session_id})}\n\n"
            response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
            if session_id and request.user.is_authenticated:
                try:
                    session = ChatSession.objects.get(session_id=session_id, user=request.user)
                    session.messages = messages + [{'role': 'assistant', 'content': '...'}]
                    session.save()
                except ChatSession.DoesNotExist:
                    pass
            return response
        else:
            result = {
                'content': response.choices[0].message.content,
                'model': response.model
            }
            
            if session_id and request.user.is_authenticated:
                result['session_id'] = session_id
                try:
                    session = ChatSession.objects.get(session_id=session_id, user=request.user)
                    session.messages = messages + [{'role': 'assistant', 'content': result['content']}]
                    session.save()
                except ChatSession.DoesNotExist:
                    pass
            
            return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(['GET'])
def get_models(request):
    models = get_available_models()
    print(f"get_models() returning {len(models)} models: {models}")
    return JsonResponse({'models': models})


@csrf_exempt
@require_http_methods(['GET'])
def get_user_sessions(request):
    from .models import ChatSession
    if request.user.is_authenticated:
        sessions = ChatSession.objects.filter(user=request.user).order_by('-updated_at')[:20]
    else:
        sessions = ChatSession.objects.filter(user__isnull=True).order_by('-updated_at')[:20]
    sessions_list = [
        {
            'session_id': session.session_id,
            'created_at': session.created_at.isoformat(),
            'updated_at': session.updated_at.isoformat()
        }
        for session in sessions
    ]
    return JsonResponse({'sessions': sessions_list})


@csrf_exempt
@require_http_methods(['POST'])
def create_session(request):
    if request.user.is_authenticated:
        session_id = str(uuid.uuid4())
        from .models import ChatSession
        session = ChatSession.objects.create(
            session_id=session_id,
            user=request.user,
            messages=[]
        )
        return JsonResponse({'session_id': session_id})
    else:
        return JsonResponse({'error': 'Unauthorized'}, status=401)


@csrf_exempt
@require_http_methods(['POST'])
def save_session(request):
    if not request.user.is_authenticated:
        return HttpResponseForbidden({'error': 'Unauthorized'}, status=401)
    
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        messages = data.get('messages', [])
        
        from .models import ChatSession
        session, created = ChatSession.objects.get_or_create(
            session_id=session_id,
            user=request.user
        )
        session.messages = messages
        session.save()
        
        return JsonResponse({'success': True, 'session_id': session_id})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
