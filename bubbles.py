from accessor import fill_deps
from inspect import isfunction, ismethod
from functools import wraps

class DirectAccessor(object):
    """ accessor which simply will return you the value
    it's created with when u ask
    """
    def __init__(self, key, value):
        self.key = self.name = key
        self.value = value
    def derive(self, arg, **lookup):
        """ just return our value """
        return self.value
    def __repr__(self):
        return '<DirectAccessor "%s">' % self.key
DA = DirectAccessor

class Context(object):

    def __init__(self, mapping=None, wrap_functions=True):
        self.mapping = mapping or {}
        self.accessor_map = {}
        self.wrap_functions = wrap_functions
        self.update(**self.mapping)

        # update our mapping to include this context
        # will also set resulting access map against self
        self.update(context=self)

    def get(self, item):
        """
        return the context obj for the given item name
        """

        accessor = self.accessor_map.get(item)
        if not accessor:
            return None

        v = accessor.derive(item, **self.mapping)

        # if we got a callable, and the wrappable
        # flag is set, wrap in our context
        if self.wrap_functions and callable(v):
            return self.create_partial(v)

        return v

    def __getattr__(self, attr):
        """
        access context objects via attribute lookup
        """


        # check the parent first
        try:
            return object.__getattr__(self, attr)
        except AttributeError:
            pass

        # we are overriding getattr as opposed to getattribute
        # so that normal class attributes take precidence
        # over context attributes
        if attr in self.accessor_map:
            return self.get(attr)

    def extend(self, context):
        """
        extend this context to include the values of another
        """
        self.update(context.mapping)

    def update(self, **kwargs):
        """
        add to our mapping / update our accessor map
        """

        self.mapping.update(kwargs)
        self.accessor_map = self.build_accessor_map(self.mapping)

    def add(self, k, v):
        """
        add a new k / v to our mapping
        """
        self.update(**{k:v})

    def copy(self):
        return build_context(self.mapping)

    @staticmethod
    def build_accessor_map(mapping):
        """
        given a mapping of k/v to use in the accessor
        map create an accessor map for dep fills
        """
        return dict( ( k, DA(k, mapping[k]) ) for k in mapping )

    def decorate(self, fn):
        """
        creates a decorator wrapping a function in this context
        """

        @wraps(fn)
        def _fn(*args, **kwargs):
            return self.create_partial(fn)(*args, **kwargs)

        return _fn

    def create_partial(self, fn, *p_args, **p_kwargs):
        """
        returns a callable which has been wrapped
        with the passed argument

        passed arguments are added to end of resulting
        callables args
        """

        @wraps(fn)
        def resulting_callable(*c_args, **c_kwargs):
            # create a set of argsuments which are
            # the args passed to the this callable concat'd
            # with the one's passed to the create_partial call
            cp_args = c_args + p_args

            # update the args passed in to partial with those
            # passed to this callable
            cp_kwargs = p_kwargs.copy()
            cp_kwargs.update(c_kwargs)

            # get the args and kwargs we are going to pass
            # to our resulting
            f_args, f_kwargs = fill_deps(self.accessor_map, fn,
                                         *cp_args, **cp_kwargs)

            """
            # if flag is set, wrap the callables being passed in
            if self.wrap_functions:

                # wrap the normal args
                for i, arg in enumerate(f_args):
                    if isfunction(arg) or ismethod(arg):
                        # make sure it's not already wrapped
                        if not getattr(arg, 'is_wrapped', False):
                            v = self.create_partial(arg)
                            f_args[i] = v
                    else:
                        f_args[i] = arg

                # wrap the kwargs
                for k, v in f_kwargs.items():
                    if isfunction(v) or ismethod(v):
                        # make sure it's not already wrapped
                        if not getattr(v, 'is_wrapped', False):
                            v = self.create_partial(v)
                            f_kwargs[k] = v
                    else:
                        f_kwargs[k] = v
            """

            # call the function we're wrapping with the derived args
            return fn( *f_args, **f_kwargs )

        resulting_callable.is_wrapped = True
        resulting_callable.context = self

        # return our wrapper
        return resulting_callable

    def __call__(self, fn, *args, **kwargs):
        """
        call the function within the context
        """
        return self.create_partial(fn)(*args, **kwargs)

def build_context(*context_pieces, **kwargs):
    context = {}

    # update the context from the kwargs
    if kwargs:
        context.update(kwargs)

    for context_piece in context_pieces:
        # check if dict, update context w/ k/v pairs
        # todo: check if Mapping instead ?
        if hasattr(context_piece, 'items'):
            context.update( context_piece )

        # if iterator, take first two values as
        # k/v for context
        elif hasattr(context_piece, 'next'):
            for d in context_piece:
                try:
                    context[d[0]] = d[1]
                except IndexError:
                    pass

    # return our context
    return Context(context)

