from django.contrib import admin
from django.urls import path
from core.views import event


urlpatterns = [
    path('admin/', admin.site.urls),
    path('event/', event, name='event'),
]
