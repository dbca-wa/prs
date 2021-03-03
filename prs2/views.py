from django.conf import settings
from django.http.response import JsonResponse
from django.views.generic import View


class StatusView(View):
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        state = {'status': 'RUNNING'}
        if settings.DEBUG:
            state['debug'] = settings.DEBUG
        return JsonResponse(state)
