from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.utils.formats import localize
import datetime
from django.utils.timezone import make_aware
from .servises import staff_required

from .forms import NewUserForm


@login_required
def home(request):
    all_tasks = []
    t_list = request.user.tasks.all()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    dates = request.GET.get('dates')
    

    if dates:
        start_date, end_date = map(str.strip, dates.split('to'))

    if not start_date and not end_date:
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=30)
    else:
        # Преобразуем параметры в объекты datetime
        try:
            if start_date:
                start_date = make_aware(datetime.datetime.strptime(start_date, '%Y-%m-%d'))#.replace(hour=0, minute=0, second=1))
            if end_date:
                end_date = make_aware(datetime.datetime.strptime(end_date, '%Y-%m-%d'))#.replace(hour=23, minute=59, second=59))
        except ValueError:
            return {"error": "Invalid date format. Use YYYY-MM-DD."}

    #print(t_list)
    if not t_list:
        form = AuthenticationForm()
        return render(request=request, template_name='login.html',
                    context={'login_form': form})

    #t_list = t_list.filter(date__range=(start_date, end_date))
    #t_list = t_list.filter(date__date__gte=end_date, date__date__lte=start_date)
    #print(f'This is tasks: {t_list}')
    for t in t_list:
        t_dict = {
            'uuid': str(t.uuid),
            'name': f'{t.name} +{t.account}' if t.name is not None else 'Без названия',
            'boardName': t.boardName,
            'date': str(localize(t.date)),
            'account': t.account,
        }
        all_tasks.append(t_dict)
        print(f'This is tasks: {all_tasks}')
    return render(request, 'index.html', {'tasks': all_tasks})


def register_request(request):
    if request.method == 'POST':
        form = NewUserForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request,
                             'Аккаунт зарегистрирован: '
                             'добро пожаловать на сайт!')
            return redirect('board:login')
        messages.error(request, 'Не удалось зарегистрировать аккаунт. '
                                'Проверьте корректность данных и '
                                'попробуйте еще раз!')
    form = NewUserForm()
    return render(request=request,
                  template_name='register.html',
                  context={'register_form': form})


def login_request(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.info(request,
                              f'Вы вошли на сайт под ником {username}.')
                return redirect('board:home')
            else:
                messages.error(request, 'Неверные имя и/или пароль.')
        else:
            messages.error(request, 'Неверные имя и/или пароль.')
    form = AuthenticationForm()
    return render(request=request, template_name='login.html',
                  context={'login_form': form})


def logout_request(request):
    logout(request)
    messages.info(request, 'Вы вышли из аккаунта.')
    return redirect('board:login')

@staff_required
def activation_and_stop(request):
    return render(request=request, template_name='activation.html')

def webhook_add_webhook(webhook_url,api_key_wazzup):
    
    url = 'https://api.wazzup24.com/v3/webhooks'
    headers = {
        'Authorization': f'Bearer {api_key_wazzup}',
        'Content-Type': 'application/json'
    }

    data = {
        "webhooksUri": f"{webhook_url}webhook",
        "subscriptions": {
            "messagesAndStatuses": True,
            "contactsAndDealsCreation": True
        }
    }

    response_data = requests.patch(url, headers=headers, json=data)
    print(f'Подписываю {webhook_url} ***{response_data.json}')

    response_get = requests.get(url,headers={'Authorization': f'Bearer {api_key_wazzup}',})
    print(f'Проверяю {webhook_url} ***{response_get.json}')

    data_get = response_get.json()

    if data_get['webhooksUri'] == f"{webhook_url}webhook":

        return True
   
    else:

        return False
