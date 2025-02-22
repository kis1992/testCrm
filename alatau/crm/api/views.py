from api.serializers import TaskSerializer, ConversationHistorySerializer

from board.models import Task, ConversationHistory, SettingsUser

from rest_framework import generics
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from datetime import datetime
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import redirect, render
from django.http import JsonResponse
from rest_framework import status
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from openai import OpenAI
import json
import requests
import logging
from typing import List, Set, Dict

logger = logging.getLogger(__name__)


class ListTask(generics.ListCreateAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Task.objects.filter(owner=user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class DetailTask(generics.RetrieveUpdateDestroyAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Task.objects.filter(owner=user)


class CreateHistoryView(APIView):
    """
    Создает или обновляет переписку, привязанную к конкретному owner.
    """

    def post(self, request, ownerid):
        # Получаем `owner` из User модели по ownerid
        owner = get_object_or_404(User, id=ownerid)

        # Извлекаем данные из тела запроса
        user_id = request.data.get('user_id')
        history_text = request.data.get('history')
        contact_name = request.data.get('contact_name')

        if not user_id or not history_text:
            return Response(
                {"error": "user_id and history are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Логика создания/обновления записи
        with transaction.atomic():
            # Проверяем или создаём Task
            task, _ = Task.objects.get_or_create(
                name=contact_name,
                account=user_id,
                owner=owner,
                defaults={'board_name': Task.BoardNames.TO_DO},
            )

            # Проверяем или обновляем ConversationHistory
            conversation, created = ConversationHistory.objects.get_or_create(
                task=task,
                owner=owner,
                user_id=user_id,
            )

            #timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S') [{timestamp}]
            if created:
                conversation.history = f"{history_text}"
            else:
                conversation.history += f"{history_text}"

            conversation.save()

        # Возвращаем сериализованные данные
        serializer = ConversationHistorySerializer(conversation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def get(self, request, user_id):
        """
        Получение всей переписки для user_id текущего владельца.
        """
        owner = request.user
        conversation = get_object_or_404(ConversationHistory, owner=owner, user_id=user_id)
        serializer = ConversationHistorySerializer(conversation)
        #return Response(serializer.data)
        print('History serializer: ', serializer.data['history'])
        return render(request, 'history.html', {'data': serializer.data['history']})

@method_decorator(csrf_exempt, name='dispatch')
class UserWebhookView(APIView):
    """
    Обрабатывает вебхуки для каждого пользователя по user_id.
    """
    def dispatch(self, request, *args, **kwargs):
        """
        Переопределение метода dispatch для загрузки настроек пользователя.
        """
        user_id = kwargs.get('user_id')  # Извлекаем user_id из URL
        user = get_object_or_404(User, id=user_id)

        # Извлекаем настройки пользователя и сохраняем как атрибуты экземпляра
        self.user = user
        settings = get_object_or_404(SettingsUser, user=user)
        
        # Устанавливаем глобальные переменные
        self.admin_phone = settings.admin_phone
        self.headers = {
            'Authorization': f'Bearer {settings.api_key}',
            'Content-Type': 'application/json'
        }
        self.default_conversation=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": settings.system_prompt,
                    }
                ]
            },
        ]
        self.client = OpenAI(api_key=settings.gpt_key)

        return super().dispatch(request, *args, **kwargs)

    def post(self, request,user_id):
        # Парсим данные из запроса
        try:
            data = request.data
        except Exception as e:
            logger.error(f"Error processing webhook: Invalid JSON format {e}")
            return Response({"error": "Invalid JSON format"}, status=status.HTTP_400_BAD_REQUEST)
        logger.info(f"Webhook received: {data}, admin: {self.user.username}")
        # Логика обработки вебхука
        if 'messages' in data and ('authorName' not in data.get('messages', [])[0]) and (data.get('messages', [])[0].get('chatType')!='whatsgroup'):
            messages = data.get('messages', [])

            processed_message = self.process_message(messages[0])

            client_name = messages[0].get('contact', {}).get('name')

            #обработка медиа сообщении
            
            if 'text' in processed_message:
                if client_name:
                    gpt_answer_text = self.create(processed_message,client_name)
                else:
                    gpt_answer_text = self.create(processed_message)
            elif 'contentUri' in processed_message:
                gpt_answer_text = "сейчас отвечу..."
                print(f"Отправляю сообщение админу: {self.send_message_to_manager(processed_message)}")
            else:
                gpt_answer_text = "сейчас отвечу..."
            if contains_mobile_number(processed_message['text']):
                print(f"Отправляю сообщение админу я распознал номер: {self.send_message_to_manager(processed_message, False)}")
            #обработка текстовых сообщении
            processed_message['text'] = gpt_answer_text
            #print(f"this is - - {processed_message}")
            if 'contentUri' in processed_message:
                processed_message.pop('contentUri',None)
            responses = self.send_to_wazzup(processed_message)

            print(f"Отправляю сообщение абоненту: {responses}")

            return Response({"message": "Webhook received", "responses": responses}, status=status.HTTP_200_OK)
        logger.error(f"Processing webhook:{data}")
        return Response({"message": "No valid data in request"}, status=status.HTTP_200_OK)

    def process_message(self, message):
        """
        Извлекает нужные данные из сообщения.
        """
        chanal_id = message.get('channelId')
        chat_type = message.get('chatType')
        chat_id = message.get('chatId')
        message_type = message.get('type')
        contact_name = message.get('contact', {}).get('name')

        if not all([chat_type, chat_id, message_type]):
            return None  # Пропускаем сообщения с отсутствующими данными

        # Извлекаем данные для разных типов сообщений
        if message_type == 'text':
            text_content = message.get('text')
            if not text_content:
                return None  # Пропускаем, если нет текста
            return {
                "channelId": chanal_id,
                "chatType": chat_type,
                "chatId": chat_id,
                "text": text_content,
            }
        elif message_type == 'image':
            content_uri = message.get('contentUri')
            if not content_uri:
                return None  # Пропускаем, если нет contentUri
            return {
                "channelId": chanal_id,
                "chatType": chat_type,
                "chatId": chat_id,
                "contentUri": content_uri,
            }
        elif message_type == 'audio':
            content_uri = message.get('contentUri')
            if not content_uri:
                return None  # Пропускаем, если нет contentUri
            return {
                "channelId": chanal_id,
                "chatType": chat_type,
                "chatId": chat_id,
                "contentUri": content_uri,
            }
        else:
            return None
        logger.error(f"Error processing type message: {message_type}")
        # Пропускаем другие типы сообщений
        return None

    def send_to_wazzup(self, payload):
        
        settings = get_object_or_404(SettingsUser, user=self.user)
        self.headers = {
            'Authorization': f'Bearer {settings.api_key}',
            'Content-Type': 'application/json'
        }
        try:
            response = requests.post(
                "https://api.wazzup24.com/v3/message",
                headers=self.headers,
                json=payload
            )
            #print(f"Send to wazzap: {payload}")
            return response.json()
        except requests.RequestException as e:
            return {"error": str(e)}

    def create(self, message, contact_name='Аноним'):
        # Извлекаем данные из тела запроса
        user_id = message.get('chatId')
        history_text = message.get('text')

        gpt_answer_text = ''

        if not user_id or not history_text:
            return Response(
                {"error": "user_id and history are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Логика создания/обновления записи
        with transaction.atomic():
            # Проверяем или создаём Task
            task, _ = Task.objects.get_or_create(
                account=user_id,
                owner=self.user,
                defaults={'name': contact_name,'boardName': Task.boardNames.ToDo},
            )

            # Проверяем или обновляем ConversationHistory
            conversation, created = ConversationHistory.objects.get_or_create(
                task=task,
                owner=self.user,
                user_id=user_id,
                defaults={'history': [{"role": "user", "content": history_text}]},
            )

            #timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S') [{timestamp}]
            if created:
                gpt_answer_text = self.gpt_answer([{"role": "user", "content": history_text}])
                conversation.history.append({"role": "assistant", "content":gpt_answer_text})
                conversation.save()
                logger.info(f"Create conversation: {history_text} and gpt answer: {gpt_answer_text}")
            else:
                #print(f"Данные с итории: {conversation.history} ") 
                conversation.history.append({"role": "user", "content": history_text}) 
                  
                gpt_answer_text = self.gpt_answer(conversation.history)
                conversation.history.append({"role": "assistant", "content": gpt_answer_text})
                conversation.save()
                logger.info(f"Update conversation: {history_text} and gpt answer: {gpt_answer_text}")
        return gpt_answer_text

    def gpt_answer(self, data):
        now = datetime.now()
        day_of_week = now.strftime("%A")  # Получить день недели
        current_time = now.strftime("%Y-%m-%d %H:%M:%S")  # Получить текущее время

        time_prompt = f"Сегодня {day_of_week}, {current_time}."

        settings = get_object_or_404(SettingsUser, user=self.user)
        self.default_conversation=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": time_prompt+settings.system_prompt,
                    }
                ]
            },
        ]
        self.client = OpenAI(api_key=settings.gpt_key)
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=self.default_conversation+data,
            temperature=0.35,
            max_tokens=256,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            response_format={
            "type": "text"
        })
        assistant_reply = response.choices[0].message.content
        return assistant_reply

    def send_message_to_manager(self, message, file=True):
        client_id = message.get('chatId')
        if file:
            media_link = f"Посмотри медиа файл, {message.get('contentUri')}"
        else:
            media_link = f"Указан номер для выставления счета: {message['text']}"
        history_link = f"https://megabot.alatau.kz/api/get_history/{client_id}/"
        client_number = f"+{client_id}"
        message['text'] = f"{media_link} \n" + f"а тут переписка - {history_link} \n" + f"Кстати, а вот и номер клиента {client_number}"
        if 'contentUri' in message:
            message.pop('contentUri',None)
            print(f'posle udaleniya = {message}')
        return self.send_to_wazzup(message)


def parse_datetime(dt_str: str) -> datetime:
    return datetime.strptime(dt_str, "%Y%m%d%H%M")
