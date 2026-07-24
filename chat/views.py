import os
from openai import OpenAI
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

LM_STUDIO_BASE_URL = os.environ.get('LM_STUDIO_BASE_URL', 'http://localhost:1234/v1')
DEFAULT_MODEL = os.environ.get('DEFAULT_MODEL', '')

client = OpenAI(
    base_url=LM_STUDIO_BASE_URL,
    api_key='not-needed'
)

def get_available_models():
    try:
        models = client.models.list()
        return [model.id for model in models.data]
    except Exception:
        return []

def index(request):
    return render(request, 'chat/index.html')

def health_check(request):
    return JsonResponse({
        'status': 'ready',
        'lm_studio_url': LM_STUDIO_BASE_URL,
        'available_models': get_available_models()
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
            return StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        else:
            return JsonResponse({
                'content': response.choices[0].message.content,
                'model': response.model
            })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(['GET'])
def get_models(request):
    models = get_available_models()
    return JsonResponse({'models': models})
