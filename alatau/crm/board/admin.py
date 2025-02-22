from django.contrib import admin

from .models import Task, ConversationHistory, SettingsUser

from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin

# Кастомизация админки для модели User
class CustomUserAdmin(UserAdmin):
    list_display = ('id', 'username', 'email', 'is_staff',)  # Добавляем поле id
    ordering = ('id',)  # Можно сортировать по id, если нужно

# Убираем стандартную регистрацию и добавляем кастомную
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
admin.site.register(Task)
admin.site.register(ConversationHistory)
admin.site.register(SettingsUser)