import uuid

from django.db import models
from django.contrib.auth.models import User

class SettingsUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='settings')
    api_key = models.CharField(max_length=255)
    gpt_key = models.CharField(max_length=255)
    admin_phone = models.CharField(max_length=20)
    system_prompt = models.TextField()

    def __str__(self):
        return f"Settings for {self.user.username}"

class Task(models.Model):
    class boardNames(models.TextChoices):
        ToDo = 'Новые Сделки'
        InProgress = 'В процессе'
        Review = 'На проверке'
        Done = 'Выполнено'
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE,
                              related_name='tasks')
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True,
                            editable=False)
    name = models.CharField(max_length=500)
    account = models.CharField(max_length=255, null=True, blank=True) 
    boardName = models.CharField(max_length=12, choices=boardNames.choices,
                                 default=boardNames.ToDo)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Сделка'
        verbose_name_plural = 'Сделки'

    def __str__(self):
        return str(self.name)

class ConversationHistory(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='conversation_histories')
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='conversation_histories')
    user_id = models.CharField(max_length=255)
    history = models.JSONField()

    class Meta:
        verbose_name = 'История переписки'
        verbose_name_plural = 'Истории переписки'
        unique_together = ('owner', 'user_id')

    def __str__(self):
        return f'История для {self.task.uuid} * ({self.user_id})'