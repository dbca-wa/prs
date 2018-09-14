from django.conf import settings


class PrsMiddleware(object):

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Reference: http://www.gnuterrypratchett.com/
        response['X-Clacks-Overhead'] = 'GNU Terry Pratchett'
        return response
