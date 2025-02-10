def form_method_middlewares(get_response):
    def middleware(request):
        if request.method == 'POST' and '_method' in request.POST:
            request.method = request.POST['_method'].upper()
        return get_response(request)
    return middleware
