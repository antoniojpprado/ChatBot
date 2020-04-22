import json
from django.http.response import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from core.message import proccess


@csrf_exempt
def event(request):
    json_telegram = json.loads(request.body)
    proccess(json_telegram)
    return HttpResponse()
