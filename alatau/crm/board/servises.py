from django.http import JsonResponse
from functools import wraps

def staff_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:  # Проверяем, что пользователь авторизован
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        if not request.user.is_staff:  # Проверяем статус персонала
            return JsonResponse({'error': 'Access denied. Staff only.'}, status=403)
        
        return view_func(request, *args, **kwargs)  # Если всё ок, выполняем функцию
    return _wrapped_view
