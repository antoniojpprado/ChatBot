import os
import logging.config
import numpy
import telegram
import time
from bot_webhook.settings import TOKEN
from core.models import Contact, Interaction
from django.db import connections
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from matplotlib import pyplot
from matplotlib.font_manager import FontProperties
from pythonjsonlogger import jsonlogger
from tempfile import NamedTemporaryFile

bot = telegram.Bot(token=TOKEN)

# Habilitar logging:
logging.config.fileConfig('logging.ini', disable_existing_loggers=False)
logger = logging.getLogger(__name__)
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)

def proccess(json_telegram):
    """
    Recebe a mensagem, enviada pela view, e solicita a autorização do contato,
    para então interagir com ele, conforme for.
    :param json_telegram: Mensagem recebida
    """
    msg = msg_handler(json_telegram)
    try:
        starttime = time.time()
        # Y = (10 / 0)
        if 'callback' in msg:
            if msg['option'] == 'graph':
                callback_graph(msg)
                options_callback(msg)

            else:
                if msg['option'] == 'spread':
                    callback_spread(msg)
                options_start(msg, msg_text=False)

        else:
            if login(msg):
                options_start(msg)

            else:
                msg_login(msg)

        endtime = time.time()
        duration = endtime - starttime
        logger.info("Processando mensagem:", extra={"run_duration": duration})

    except Exception as error:
        logger.exception(error)


def msg_handler(json_telegram):
    """
    Extrai os dados que serão manipulados, da mensagem enviada pelo Telegram.
    :param json_telegram: Mensagem recebida.
    :return: Dicionário msg com os dados a serem manipulados.
    """
    if 'callback_query' in json_telegram:
        user_id = json_telegram['callback_query']['from']['id']
        first_name = json_telegram['callback_query']['from']['first_name']
        last_name = json_telegram['callback_query']['from']['last_name']
        callback = json_telegram['callback_query']['data']
        if callback == 'start':
            option = callback

        else:
            if 'Graph' in callback:
                option = 'graph'
                callback = callback.replace('Graph ', '')

            else:
                option = 'spread'
                callback = callback.replace('Spread ', '')

        msg = {'user_id': user_id,
               'first_name': first_name,
               'last_name': last_name,
               'callback': callback,
               'option': option}

    else:
        user_id = json_telegram['message']['from']['id']
        first_name = json_telegram['message']['from']['first_name']
        last_name = json_telegram['message']['from']['last_name']
        msg = {'user_id': user_id, 'first_name': first_name, 'last_name': last_name}

        if 'contact' in json_telegram['message']:
            msg['phone_number'] = json_telegram['message']['contact']['phone_number']

    return msg


def login(msg):
    """
    Verifica se o usuário consta na base de dados do App Care e interage com o contato.
    Também registra na base do bot, os dados do novo contato do bot, caso ainda não exista.
    :param msg: Mensagem recebida
    :return: Falso ou verdadeiro, para a autorização do contato.
    """
    try:
        # Verifica se o usuário existe na base da dados do Bot
        contact = Contact.objects.get(user_id=msg['user_id'])

    except Contact.DoesNotExist:
        try:
            # Verifica se o contato é cadastrado na base do App Care.
            if user_app(msg['phone_number']):
                # Salva o contato na base de dados do Bot.
                Contact(
                    user_id=msg['user_id'],
                    first_name=msg['first_name'],
                    last_name=msg['last_name'],
                    phone_number=msg['phone_number']
                ).save()

            else:
                bot.send_message(
                    text='Olá {0} {1}!\n\n'
                         'Não te localizei como um usuário registrado.\n\n'
                         'Solicite o cadastro no App Care e retorne para que eu possa te atender.\n\n'
                         'Obrigado pelo contato.'.format(msg['first_name'], msg['last_name']),
                    chat_id=msg['user_id'])
                return False

        except BaseException:
            return False

    return True


def msg_login(msg):
    """
    Interage com o contato, solicitando os seus dados para autorizar o acesso.
    :param msg: Mensagem do contato
    """
    reply_markup = telegram.ReplyKeyboardMarkup(
        [[telegram.KeyboardButton('Click para Login', request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    bot.sendMessage(msg['user_id'], 'Preciso autorizar seu acesso.', reply_markup=reply_markup)


def user_app(phone_number):
    """
    Verifica a existência do contato, na base de dados do App Care.
    :param phone_number: Utilizado como identificação do usuário.
    :return: Dados do user.
    """
    cur = connections['app'].cursor()
    sql = "SELECT id FROM accounts_user WHERE phone_number = '{}'".format(phone_number)
    cur.execute(sql)
    user = cur.fetchone()
    cur.close()
    return user


def options_start(msg, msg_text=True):
    """
    Apresenta ao contato, a lista de opções.
    :param msg: Mensagem do contato.
    :param msg_text: Se deve apresentar texto.
    """
    interaction = Interaction.objects.all().values('input').order_by('input')
    interaction = list(interaction)
    button_list = []
    for row in interaction:
        button_list.append(InlineKeyboardButton(row['input'], callback_data='Graph {}'.format(row['input'])))
    reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=2))
    if msg_text:
        text = 'Olá {0} {1}!\nTenho disponível estas informações:'.format(msg['first_name'], msg['last_name'])
    else:
        text = 'Disponível:'
    bot.send_message(text=text, chat_id=msg['user_id'], reply_markup=reply_markup)


def options_callback(msg):
    """
    Apresenta ao contato, a lista de opções.
    :param msg: Mensagem do contato.
    :param msg_text: Se deve apresentar texto.
    """
    button_list_callback = [
        InlineKeyboardButton('Planilha dos Dados', callback_data='Spread {}'.format(msg['callback'])),
        InlineKeyboardButton('Retornar ao início', callback_data='start')
    ]
    reply_markup = InlineKeyboardMarkup(build_menu(button_list_callback, n_cols=2))
    text = 'Também tenho disponível:'
    bot.send_message(text=text, chat_id=msg['user_id'], reply_markup=reply_markup)


def callback_graph(msg):
    """
    Apresentar o gráfico de barras, relativo a opção escolhida.
    :param msg: Mensagem recebida
    """
    # Obtem o código da SQL query a ser consultada, na base de dados, e a executa:
    interaction = Interaction.objects.get(input=msg['callback'])
    code = interaction.code
    dic = get_data(code)
    # Constrói a lista de dados para os eixos x e y:
    xaxis = []
    yaxis = []
    for row in dic:
        xaxis.append('{:02d}:{:02d}'.format(row[0].hour, row[0].minute))
        yaxis.append(row[1])
    # Construir o gráfico de barras:
    exec(interaction.graph_labels, globals())  # Declarar title, xlabel e ylabel.
    xordem = numpy.arange(len(xaxis))
    graph = pyplot.bar(xordem, yaxis, color='royalblue', alpha=0.7)
    pyplot.xticks(xordem, xaxis)
    pyplot.grid(color='#95a5a6', linestyle='--', linewidth=2, axis='y', alpha=0.7)
    pyplot.title(title)
    pyplot.xlabel(xlabel)
    pyplot.ylabel(ylabel)
    pyplot.xticks(rotation=45, fontsize=6)
    # Definir cores em vermelho para horário de ponta:
    rows = len(dic)
    for i in range(rows):
        if 4 <= dic[i][0].hour <= 6:
            graph[i].set_color('r')
    # Apresentar o gráfico:
    pyplot.savefig('teste.png', format='png')
    pyplot.show()
    bot.sendPhoto(chat_id=msg['user_id'], photo=open('/home/antonio/Documents/estudos/bot2/teste.png', 'rb'))


def callback_spread(msg):
    """
    Apresentar tabela com os dados, relativo a opção escolhida.
    :param msg: Mensagem recebida
    """
    # Obter o código da SQL query a ser consultada, na base de dados, e a executa:
    interaction = Interaction.objects.get(input=msg['callback'])
    code = interaction.code
    dic = get_data(code)
    # Construir a lista de dados:
    table_values = []
    count = 0
    for row in dic:
        if count == 24:
            img = make_table(table_values)
            bot.sendPhoto(chat_id=msg['user_id'], photo=open(img, 'rb'))
            table_values = []
            count = 0
            os.unlink(img)
        table_values.append(['{:02d}:{:02d}'.format(row[0].hour, row[0].minute), row[1]])
        count += 1


def make_table(table_values):
    """
    Construir uma tabela.
    :param table_values: Lista de valores que compõe a tabela.
    :return: Path da imagem da tabela criada.
    """
    # Construir a tabela:
    col_labels = ['Hora', 'Valor']
    table = pyplot.table(cellText=table_values,
                         colWidths=[0.1] * 3,
                         colLabels=col_labels,
                         loc='center')
    table.auto_set_font_size(False)
    table.scale(4, 4)
    pyplot.axis('off')
    n_rows = len(table_values)
    # Centralizar primeira coluna:
    cells = table.properties()['celld']
    for i in range(n_rows+1):
        cells[i, 0]._loc = 'center'
    # Bold na primeira linha:
    cells[0, 0].set_text_props(fontproperties=FontProperties(weight='bold'))
    cells[0, 1].set_text_props(fontproperties=FontProperties(weight='bold'))
    # Tamanho das fontes:
    table.set_fontsize(24)
    # Cores da tabela:
    table[(0, 0)].set_facecolor('#c5d4e6')
    table[(0, 1)].set_facecolor('#c5d4e6')
    color = 'white'
    for row in range(n_rows):
        table[(row+1, 0)].set_facecolor(color)   # A primeira linha, cabeçalho, tem cor específica.
        table[(row+1, 1)].set_facecolor(color)
        color = '#e2e9f2' if color == 'white' else 'white'
    # Apresentar a tabela:
    img = NamedTemporaryFile(delete=False)
    pyplot.savefig(img, bbox_inches='tight', pad_inches=0.05)
    pyplot.show()
    return img.name


def build_menu(buttons, n_cols, header_buttons=None, footer_buttons=None):
    """
    Constrói um menu com os botões das opções para o contato.
    :param buttons: Os botões que compõe o menu.
    :param n_cols: Quantidade de colunas que deverá conter o menu.
    :param header_buttons: Cabeçalho dos botões.
    :param footer_buttons: Rodabé dos botões.
    :return: O menu.
    """
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, [header_buttons])
    if footer_buttons:
        menu.append([footer_buttons])
    return menu


def get_data(sql):
    cur = connections['app'].cursor()
    cur.execute(sql)
    data = cur.fetchall()
    cur.close()
    return data
