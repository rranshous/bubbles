from inspect import getargspec
from itertools import chain, izip
from decorator import decorator

def iterskip(skips, iterator):
    for i in xrange(skips):
        iterator.next()
    for v in iterator:
        yield v

def get_function_args(func):
    """
    returns list of functions args + list of named args
    """
    arg_spec = getargspec(func)

    # figure out what the defaults are
    defaults = arg_spec.defaults or []
    dl = len(defaults)
    args = arg_spec.args or []
    dlo = len(args) - dl
    args, k_args = args[:dlo], args[dlo:]
    return (
        filter(lambda v: v!='self', args),
        k_args,
        defaults
    )


# Lookup of all accessors # TODO
# maps accessor name => accessor
accessor_map = {}

def register(accessor):
    global accessor_map
    accessor_map[accessor.name] = accessor
    return accessor

def fill_deps_decorator(f):
    def _fill_deps_decorator(*args, **kwargs):
        try:
            filled_args, filled_kwargs = fill_deps(f, *args, **kwargs)
        except KeyError:
            # couldn't fill all the args, we'll try and just call
            # the function
            return f(*args, **kwargs)

        return f(*filled_args, **filled_kwargs)
    return _fill_deps_decorator

# CHANGED THIS! NOW TAKES ARGUMENT MAP AS ARG

def fill_deps(accessor_map, func, *given_args, **given_kwargs):
    """
    inspects the function to find it's optional and required args
    inspects given args to see if they fill deps, tries to find
    way of filling deps from given objs

    arguments given are assumed to map correctly to the functions
    required args
    """

    # get from the function what args it expects
    f_args, f_named_args, defaults = get_function_args(func)

    # update our given kwargs to include the defaults
    # (if it's not given)
    f_named_defaults = dict(zip(f_named_args,defaults))
    f_named_defaults.update(given_kwargs)
    given_kwargs = f_named_defaults

    # our lookup for derived args
    # we know the given args are correct, so just set those
    derived_args = dict( (k,v) for k,v in izip(f_args, given_args) )

    # it's all args to us
    all_args = chain(f_args, f_named_args)

    # we already set the given args are correct, skip them
    all_args = iterskip(len(given_args), all_args)

    for f_arg in all_args:

        # if they passed us the kwarg, than skip
        if f_arg in given_kwargs: #and f_arg not in f_named_args: # not sure why this is here
            continue

        # an arg the funcion expects isn't given, see if we can
        # get it from an accessor
        accessor = accessor_map.get(f_arg)
        try:
            derived_arg = accessor.derive(f_arg, **given_kwargs)
        except Exception, ex:
            continue # could not derive

        derived_args[f_arg] = derived_arg

    # combine our new args and our given ones
    given_kwargs.update(derived_args)

    # now check and make sure all the required deps have been filled
    for f_arg in f_args:
        if not f_arg in given_kwargs:
            ex = Exception("Missing Dep: %s\n%s" % (f_arg,
                                                  accessor_map))
            ex.dep = f_arg
            raise ex

    # if they've been filled now we want to return back what we've found
    # broken down into un-named and named

    # in some cases the function calls for *args, in that case we'll have
    # no f_args but have been given args, just pass on the given args
    if given_args and len(f_args) == 0:
        to_return_args = list(given_args)
    else:
        to_return_args = [given_kwargs[a] for a in f_args]

    return (
        to_return_args,
        dict((a,given_kwargs[a]) for a in f_named_args)
    )

def context_fill_deps(context, func, *given_args, **given_kwargs):
    """
    inspects the function to find it's optional and required args
    inspects given args to see if they fill deps, tries to find
    way of filling deps from given objs

    arguments given are assumed to map correctly to the functions
    required args
    """

    accessor_map = context.accessor_map

    # get from the function what args it expects
    f_args, f_named_args, defaults = get_function_args(func)

    #print 'func: %s' % func
    #print 'given_args: %s' % str(given_args)
    #print 'given_kwargs: %s' % given_kwargs

    # update our given kwargs to include the defaults
    # (if it's not given)
    f_named_defaults = dict(zip(f_named_args, defaults))
    f_named_defaults.update(given_kwargs)
    original_given_kwargs = given_kwargs
    given_kwargs = f_named_defaults

    # our lookup for derived args
    # we know the given args are correct, so just set those
    derived_args = dict( (k,v) for k,v in izip(f_args, given_args) )

    # it's all args to us
    all_args = chain(f_args, f_named_args)

    # we already set the given args are correct, skip them
    all_args = iterskip(len(given_args), all_args)

    #print 'updated given_kwargs: %s' % given_kwargs
    #print 'f_named_args: %s' % f_named_args

    for f_arg in all_args:

        # if they passed us the kwarg, than skip
        if f_arg in given_kwargs and \
           (f_arg not in f_named_args or f_arg in original_given_kwargs):
            #print 'skipping: %s' % f_arg
            continue

        # an arg the funcion expects isn't given, see if we can
        # get it from an accessor
        accessor = accessor_map.get(f_arg)
        try:
            derived_arg = accessor.derive(f_arg, **given_kwargs)
        except Exception, ex:
            continue # could not derive

        # TODO: move this whole thing somewhere else
        #       where it's not so ghetto / hacky
        # if we got a callable, and the wrappable
        # flag is set, wrap in our context
        if context.wrap_functions and callable(derived_arg):
            try:
                derived_arg = context.create_partial(derived_arg)
            except Exception:
                pass # shrug

        derived_args[f_arg] = derived_arg

    # combine our new args and our given ones
    given_kwargs.update(derived_args)

    # now check and make sure all the required deps have been filled
    for f_arg in f_args:
        if not f_arg in given_kwargs:
            ex = Exception("Missing Dep: %s\n%s" % (f_arg,
                                                  accessor_map))
            ex.dep = f_arg
            raise ex

    # if they've been filled now we want to return back what we've found
    # broken down into un-named and named

    # in some cases the function calls for *args, in that case we'll have
    # no f_args but have been given args, just pass on the given args
    if given_args and len(f_args) == 0:
        to_return_args = list(given_args)
    else:
        to_return_args = [given_kwargs[a] for a in f_args]

    return (
        to_return_args,
        dict((a,given_kwargs[a]) for a in f_named_args)
    )

class AccessorDef(object):
    """
    obj which can translate base obj into desired obj
    """
    is_accessor_def = True
    NOT_FOUND = (True,False,-1) # random, can do better
    def __init__(self, path=''):
        self.path = path
    def transform(self, o):
        for p in self.path.split('.'):
            try:
                # try a get method first
                o = o.get(p, self.NOT_FOUND)
            except AttributeError:
                # try attribute lookup
                o = getattr(o, p, self.NOT_FOUND)
            if o is self.NOT_FOUND:
                raise Exception('Can not transform')
        return o
    def __repr__(self):
        return "<AccessorDef '%s'>" % self.path


class Accessor(object):
    """
    finds deps based on other deps
    """

    name = None # Accessor's name should be the dep name

    def derive(self, arg, **arg_lookup):
        """
        given the name of the arg we want and a lookup of all other
        args return a proxy obj to stand in arg
        """

        # go the arg lookup seeing if we have a AccessorDef which
        # can transform
        for compare_arg, compare_value in arg_lookup.iteritems():
            accessor_def = getattr(self, compare_arg, None)
            if accessor_def:
                try:
                    r = accessor_def.transform(compare_value)
                    # if it succeeds we'll go w/ it's response
                    # TODO: decide if i like proxy
                    return r
                except Exception, ex:
                    pass # not an accessor def or cant transform

        raise Exception('Could not derive')
