import json

from asyncio import iscoroutinefunction
from concurrent.futures import ThreadPoolExecutor

import tornado.web

from flasky.errors import BadRequestError, MethodIsNotAllowed


# noinspection PyAttributeOutsideInit,PyAbstractClass
class DynamicHandler(tornado.web.RequestHandler):

    executor_pool = ThreadPoolExecutor()

    def initialize(self, endpoint=None, endpoint_definition=None,
                   after_request_funcs=None, before_request_funcs=None, user_loader_func=None,
                   error_handler_funcs=None, run_in_executor=None, teardown_request_funcs = None,
                   caches=None, settings=None, app_ctx=None):
        self.context = app_ctx
        #: Flasky app.
        self.run_in_executor = run_in_executor

        #: A dictionary all handlers will be registered. Keys will be method of handler.
        self.endpoint_definition = endpoint_definition

        #: Endpoint of this handler for logging purposes
        self.endpoint = endpoint

        #: List of functions will be executed after request is handled.
        self.after_request_funcs = after_request_funcs or []

        self.before_request_funcs = before_request_funcs or []

        self.error_handler_funcs = error_handler_funcs or []

        self.teardown_request_funcs = teardown_request_funcs or []

        self.user_loader_func = user_loader_func

        self.user = None

        self._body_as_json = None

        self.app_settings = settings

        for key, cache in caches.items():
            setattr(self, key, cache)

    async def post(self, *args, **kwargs):
        await self._handle('POST', *args, **kwargs)

    async def get(self, *args, **kwargs):
        await self._handle('GET', *args, **kwargs)

    async def patch(self, *args, **kwargs):
        await self._handle('PATCH', *args, **kwargs)

    async def put(self, *args, **kwargs):
        await self._handle('PUT', *args, **kwargs)

    async def options(self, *args, **kwargs):
        await self._handle('OPTIONS', *args, **kwargs)

    async def head(self, *args, **kwargs):
        await self._handle('HEAD', *args, **kwargs)

    async def delete(self, *args, **kwargs):
        await self._handle('DELETE', *args, **kwargs)

    async def _handle(self, method, *args, **kwargs):
        method_definition = self._get_method_definition(method)

        try:
            await self._do_handle(method_definition, *args, **kwargs)
        except BaseException as e:
            error_handler = self.error_handler_funcs[type(e)] \
                            if type(e) in self.error_handler_funcs \
                            else self.error_handler_funcs[None]

            await error_handler(self, e)

            for teardown_funcs in self.teardown_request_funcs:
                await teardown_funcs(self, method_definition)

    def _get_method_definition(self, method_name):
        return self.endpoint_definition.get(method_name, None)

    async def _do_handle(self, method_definition, *args, **kwargs):
        if self.user_loader_func:
            self.user = await self.user_loader_func(self, method_definition)

        handler_function = method_definition.get('function', None)
        if not handler_function:
            raise MethodIsNotAllowed()

        for before_request_func in self.before_request_funcs:
            if iscoroutinefunction(before_request_func):
                await before_request_func(self, method_definition)
            else:
                before_request_func(self, method_definition)


        await handler_function(self, *args, **kwargs)

        for after_request_func in self.after_request_funcs:
            await after_request_func(self, method_definition)

    def body_as_json(self, **kwargs):
        throw_exc = kwargs.pop("throw_exc", False)
        if not self._body_as_json:
            try:
                self._body_as_json = json.loads(self.request.body.decode('utf-8'), **kwargs)
            except json.JSONDecodeError as e:
                if throw_exc:
                    raise BadRequestError('Expected json but not found. msg={}'.format(e.args[0]), reason=e) from e
                return None
        return self._body_as_json





