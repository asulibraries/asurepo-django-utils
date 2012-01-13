from django.http import HttpResponse

class ImmediateResponseMiddleware(object):
    '''
    Allows views to raise a particular exception type (HttpResponse, below) 
    that wraps a response
    '''
    def process_exception(self, request, exception):
        if isinstance(exception, ImmediateHttpResponse):
            return exception.response
        return None

class ImmediateHttpResponse(Exception):
    """
    Inspired by a similar pattern in tastypie.  Use in conjunction with 
    ImmediateResponseMiddleware to interrupt the flow of processing immediately,
    returning a custom HttpResponse.
    """
    response = HttpResponse("Nothing provided.")
    
    def __init__(self, response):
        self.response = response

class MasqueradeMiddleware(object):
    '''
    Looks for a field in the active session specifying a user to masquerade as
    and sets request.user to that user, storing the real user to the session.

    This middleware is dependent on the existence of sessions, so it should be 
    deployed after ('inside') Django's session middleware.  It should probably
    be deployed after middleware like the TermsAndConditionsMiddleware which
    implement one-time intercepts, so that masquerading superusers don't get 
    redirected to (and have to accept, on behalf of the effective user) the 
    site terms.
    '''

    SESSION_KEY_BASE = 'user.base_user'
    SESSION_KEY_EFFECTIVE = 'user.effective_user'
    
    def process_request(self, request):
        request.is_masquerade_session = False
        if hasattr(request, 'session'):
            eff_user = request.session.get(self.SESSION_KEY_EFFECTIVE)
            if eff_user:
                request.user = eff_user
                request.is_masquerade_session = True

def masquerade_context(request):
    '''
    Context processor that adds an 'is_masquerade_session' variable to 
    indicate whether the user in the current session is masquerading as another
    user (this is superuser functionality).
    '''
    ms = False
    eu = None
    if hasattr(request, 'session'):
        if request.session.get(MasqueradeMiddleware.SESSION_KEY_EFFECTIVE):
            ms = True
            eu = request.session.get(MasqueradeMiddleware.SESSION_KEY_EFFECTIVE)
    return { 'is_masquerade_session': ms, 'effective_user': eu }

