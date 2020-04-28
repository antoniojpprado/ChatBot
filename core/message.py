import logging.config
import numpy
import os

import pytz
import telegram
from bot_webhook.settings import TOKEN
from core.models import Contact, Interaction
from datetime import datetime
from django.db import connections
from pytz import timezone
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
        if 'callback' in msg:
            callback(msg)
            if msg['option'] == 'graph':
                options_callback(msg)

            else:
                options_start(msg, msg_text=False)

        else:
            if login(msg):
                options_start(msg)

            else:
                msg_login(msg)

    except Exception as error:
        logger.exception(error)


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


def callback(msg):
    """
    Processar o retorno ao contato.
    :param msg: Mensagem recebida
    """
    try:
        # Obter o código para execução da solicitação:
        interaction = get_interaction(msg)
        if interaction is None:
            raise ValueError('Nao foi possivel atender a callback {}'.format(msg))
        # Obter os dados:
        dic = get_data(sql=interaction.code)
        if dic is None:
            raise ValueError('Nao foi possivel atender a callback {}'.format(msg))
        # Obter timezone
        client_timezone = get_timezone(user=msg['user_id'])
        if client_timezone is None:
            raise ValueError('Fuso horario do cliente {} nao localizado para atender ao callback.'.
                             format(msg['user_id']))
        # Construir:
        if msg['option'] == 'graph':
            plt = make_graph(data=dic,
                             client_timezone=client_timezone,
                             graph_type=interaction.type,
                             label=interaction.graph_labels)
        else:
            plt = make_table(data=dic,
                             client_timezone=client_timezone,
                             label=interaction.table_labels)
        # Apresentar:
        if plt:
            msg_callback(chat=msg['user_id'])

    except ValueError as error:
        logger.exception(error)


def get_data(sql):
    """
    Obter dados na base do App Care.
    :param msg: Mensagem do contato.
    :param sql: Query da ser executada.
    :return: Lista dos dicionários com os dados.
    """
    try:
        # Estabelecer conexão e obter os dados:
        cur = connections['app'].cursor()
        cur.execute(sql)
        data = cur.fetchall()
        # Gerar dicionário:
        fieldnames = [name[0] for name in cur.description]
        result = []
        for row in data:
            rowset = []
            for field in zip(fieldnames, row):
                rowset.append(field)
            result.append(dict(rowset))
        # Encerrar:
        cur.close()
        return result
    except ValueError:
        logger.exception('Nao foram obtidos dados com a sql: {}'.format(sql))
        return None


def get_interaction(msg):
    """
    Obtem a instrução a ser executada
    :param msg: Mensagem do contato
    :return: instrução
    """
    try:
        # Obter o código da SQL query a ser consultada, na base de dados, e a executa:
        interaction = Interaction.objects.get(input=msg['callback'])
        return interaction
    except Interaction.DoesNotExist:
        logger.exception(
            'Nao localizado o comando {} na base de dados. '.format(msg['callback']))
        return None


def get_graph_labels(label):
    """
    Declarar em dicionário, as variáveis e seus conteúdos definidos na base de dados'
    :param label: Registro graph_labels, na base de dados do chatbot.
    :return: Dicionário contendo os dados.
    """
    exec(label, globals())  # Declarar title, xlabel e ylabel.
    label = {'title': title, 'xlabel': xlabel, 'ylabel': ylabel}
    return label


def get_table_labels(label):
    """
    Declarar em dicionário, as variáveis e seus conteúdos definidos na base de dados'
    :param label: Registro graph_labels, na base de dados do chatbot.
    :return: Dicionário contendo os dados.
    """
    exec(label, globals())  # Declarar títulos das colunas.
    col_labels = [col_0, col_1, col_2]
    return col_labels


def get_timezone(user):
    """
    Obtem o timezone definido para o cliente, em seu cadastro, em sua base de dados.
    :param user: Identificação do contato cliente.
    :return: O timezone do cliente.
    """
    try:
        user = Contact.objects.get(user_id=user)
        sql = "SELECT timezone " \
              "FROM company " \
              "INNER JOIN accounts_user ON company.company_id = accounts_user.company_id " \
              "WHERE accounts_user.phone_number = '{}';".format(user.phone_number)
        fuse = get_data(sql)
    except Contact.DoesNotExist:
        logger.exception('Nao foi localizado o usuario {} na banco de dados do ChatBot'.format(user))
        return None
    return fuse[0]['timezone']


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


def make_graph(data, client_timezone, graph_type, label):
    """
    Construir um gráfico.
    :param data: Dicionário com os dados
    :param client_timezone: Timezone do contato cliente
    :param graph_type: Tipos: column, pizza, ...
    :param label: Labels
    """
    try:
        # Construir a lista de dados para os eixos:
        xaxis = []
        yaxis_a = []
        yaxis_b = []
        for row in data:
            dt = row['time'].replace(tzinfo=pytz.utc).astimezone(pytz.timezone(client_timezone))
            xaxis.append('{:02d}:{:02d}'.format(dt.hour, dt.minute))
            yaxis_a.append(row['point'])
            yaxis_b.append(row['out_point'])
        # Construir o gráfico de barras:
        xordem = numpy.arange(len(xaxis))
        if graph_type == 'Column':
            pyplot.bar(xordem, yaxis_a, label='Ponta', color='red', alpha=0.7)
            pyplot.bar(xordem, yaxis_b, label='Fora Ponta', color='royalblue', alpha=0.7, bottom=yaxis_a)
        else:
            raise ValueError('Interaction Type nao previsto: {} em callback_graph()'.format(graph_type))
        pyplot.xticks(xordem, xaxis)
        pyplot.grid(color='#95a5a6', linestyle='--', linewidth=2, axis='y', alpha=0.7)
        # Obter legendas:
        label = get_graph_labels(label=label)
        # Cabeçalho
        make_header(title=label['title'], equipment=data[0]['equipment_name'])
        # Legenda Valores
        pyplot.ylabel(label['ylabel'])
        # Legenda Rodapé
        pyplot.xlabel(label['xlabel'])
        pyplot.xticks(rotation=45, fontsize=6)
        data_hora = datetime.now()
        data_hora = data_hora.astimezone(timezone(client_timezone))
        data_hora = '{}'.format(data_hora.strftime('%d/%m/%Y %H:%M'))
        pyplot.figtext(x=0.89, y=0.01, s=data_hora, horizontalalignment='right', fontsize=6)
        # Legenda Barras
        pyplot.legend(fontsize=6)
        return True

    except ValueError as error:
        logger.exception(error)
        return None


def make_header(title, equipment=None, fontsize_title=14, logo=True):
    if logo:
        logo = pyplot.imread('logo_equiplex.png')
        pyplot.figimage(logo, 30, 433)
    pyplot.title(title, fontsize=fontsize_title)
    if equipment:
        pyplot.figtext(0.9, 0.9, equipment, horizontalalignment='right', fontsize=8)


def make_table(data, client_timezone, label):
    """
    Construir uma tabela.
    :param data: Dicionário com os dados
    :param client_timezone: Timezone do contato cliente
    :param label: Labels
    """
    try:
        # Obter legendas:
        label = get_table_labels(label=label)
        # Container da imagem:
        fig, ax = pyplot.subplots(figsize=(10, 5))
        fig.subplots_adjust(top=3.5)
        # Cabeçalho
        make_header(title=label[0],
                    fontsize_title=28,
                    logo=None)
        # Construir a lista de dados:
        ax.axis('off')
        table_values = []
        for row in data:
            dt = row['time'].replace(tzinfo=pytz.utc).astimezone(pytz.timezone(client_timezone))
            table_values.append(['{:02d}:{:02d}'.format(dt.hour, dt.minute),
                                 row['out_point'],
                                 row['point']])
        # Construir a tabela:
        table = ax.table(cellText=table_values,
                             colWidths=[0.1] * 3,
                             colLabels=label,
                             colColours=['#B9D1F8'] * 3,
                             colLoc=['center', 'right', 'right'],
                             loc='center')
        table.auto_set_font_size(False)
        table.scale(4, 4)
        n_rows = len(table_values)
        # Centralizar primeira coluna:
        cells = table.properties()['celld']
        for i in range(n_rows+1):
            cells[i, 0]._loc = 'center'
        # Bold na primeira linha:
        cells[0, 0].set_text_props(fontproperties=FontProperties(weight='bold'))
        cells[0, 1].set_text_props(fontproperties=FontProperties(weight='bold'))
        cells[0, 2].set_text_props(fontproperties=FontProperties(weight='bold'))
        # Tamanho das fontes:
        table.set_fontsize(24)
        color = '#FFFFF8'
        for row in range(n_rows):
            table[(row+1, 0)].set_facecolor(color)
            table[(row+1, 1)].set_facecolor(color)
            table[(row+1, 2)].set_facecolor(color)
            color = '#EBF0F8' if color == '#FFFFF8' else '#FFFFF8'
        # Cores das bordas
        for key, cell in table.get_celld().items():
            cell.set_edgecolor('#9EB5DB')
        return table

    except Exception as error:
        logger.exception(error)
        return None


def msg_callback(chat):
    """
    Enviar a imagem ao Telegram
    :param chat: Identificação da mensagem
    """
    img = NamedTemporaryFile(delete=False)
    img = img.name
    pyplot.savefig(img, bbox_inches='tight', format='png')
    pyplot.show()
    bot.sendPhoto(chat_id=chat, photo=open(img, 'rb'))
    os.unlink(img)


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
