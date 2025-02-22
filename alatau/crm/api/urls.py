from api.views import DetailTask, ListTask, CreateHistoryView, UserWebhookView

from django.urls import path

urlpatterns = [
    path('tasks/', ListTask.as_view()),
    path('task/<str:pk>', DetailTask.as_view()),
    path('create_history/<int:ownerid>/', CreateHistoryView.as_view(), name='create_history'),
    path('get_history/<int:user_id>/', CreateHistoryView.as_view(), name='get_history'),
    path('webhook/<int:user_id>/', UserWebhookView.as_view(), name='user_webhook'),
    ]
