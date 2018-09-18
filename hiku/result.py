"""
    hiku.result
    ~~~~~~~~~~~

    In all examples query results are showed in **denormalized** form, suitable
    for reading (by humans) and for serializing into simple formats, into `JSON`
    for example. But this is not how `Hiku` stores result internally.

    Internally `Hiku` stores result in a fully **normalized** form. So result in
    `Hiku` is also a graph structure with references between objects. This
    approach has lots of advantages:

      - normalization helps to heavily reduce size of serialized result when we
        need to transfer it (this avoids data duplication)
      - it reduces internal memory usage and simplifies work with data
        internally
      - gives ability to cache, precisely and effortlessly update local state
        on the client

"""
from collections import defaultdict

from .types import RecordMeta, OptionalMeta, SequenceMeta
from .query import Node, Field, Link, merge
from .graph import Link as GraphLink, Field as GraphField, Many, Maybe
from .utils import cached_property


class Index(defaultdict):
    ROOT = '__root__'

    def __init__(self):
        super(Index, self).__init__(lambda: defaultdict(dict))

    @cached_property
    def root(self):
        return self[self.ROOT][self.ROOT]

    def ref(self, node, ident):
        return Reference(self, node, ident)

    def root_ref(self):
        return Reference(self, self.ROOT, self.ROOT)

    def finish(self):
        for value in self.values():
            value.default_factory = None
        self.default_factory = None


class Reference(object):
    __slots__ = ('index', 'node', 'ident')

    def __init__(self, index, node, ident):
        self.index = index
        self.node = node
        self.ident = ident

    def __getitem__(self, item):
        try:
            obj = self.index[self.node][self.ident]
        except KeyError:
            raise AssertionError('Object {}[{!r}] is missing in the index'
                                 .format(self.node, self.ident))
        try:
            return obj[item]
        except KeyError:
            raise AssertionError('Field {}[{!r}].{} is missing in the index'
                                 .format(self.node, self.ident, item))


class Proxy(object):
    __slots__ = ('__ref__', '__node__')

    def __init__(self, ref, query_node):
        self.__ref__ = ref
        self.__node__ = query_node

    def __wrap__(self, query_obj, value):
        if isinstance(query_obj, Field):
            return value
        elif isinstance(value, Reference):
            return self.__class__(value, query_obj.node)
        elif (
            isinstance(value, list) and value
            and isinstance(value[0], Reference)
        ):
            return [self.__class__(ref, query_obj.node) for ref in value]
        else:
            return value

    def __getitem__(self, item):
        try:
            obj = self.__node__.result_map[item]
        except KeyError:
            raise KeyError("Field {!r} wasn't requested in the query"
                           .format(item))
        value = self.__ref__[obj.index_key]
        return self.__wrap__(obj, value)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(e)


def _denormalize_type(type_, result, query_obj):
    if isinstance(query_obj, Field):
        return result
    elif isinstance(query_obj, Link):
        if isinstance(type_, SequenceMeta):
            return [_denormalize_type(type_.__item_type__, item, query_obj)
                    for item in result]
        elif isinstance(type_, OptionalMeta):
            return (_denormalize_type(type_.__type__, result, query_obj)
                    if result is not None else None)
        else:
            assert isinstance(type_, RecordMeta), type(type_)
            field_types = type_.__field_types__
            return {
                f.name: _denormalize_type(
                    field_types[f.name], result[f.name], f)
                for f in query_obj.node.fields
            }
    assert False, (type_, query_obj)


def _denormalize(graph, graph_obj, result, query_obj):
    if isinstance(query_obj, Node):
        return {f.name: _denormalize(graph, graph_obj.fields_map[f.name],
                                     result[f.name], f)
                for f in query_obj.fields}

    elif isinstance(query_obj, Field):
        return result

    elif isinstance(query_obj, Link):
        if isinstance(graph_obj, GraphField):
            type_ = graph_obj.type
            return _denormalize_type(type_, result, query_obj)

        elif isinstance(graph_obj, GraphLink):
            graph_node = graph.nodes_map[graph_obj.node]
            if graph_obj.type_enum is Many:
                return [_denormalize(graph, graph_node, v, query_obj.node)
                        for v in result]
            elif graph_obj.type_enum is Maybe and result is None:
                return None
            else:
                return _denormalize(graph, graph_node, result, query_obj.node)

        else:
            return _denormalize(graph, graph_obj, result, query_obj.node)


def denormalize(graph, result, query):
    """Transforms normalized result (graph) into simple hierarchical structure

    This hierarchical structure will follow query structure.

    Example::

        query = hiku.readers.simple.read('[:foo]')
        norm_result = hiku_engine.execute(graph, query)
        result = hiku.result.denormalize(graph, norm_result, query)
        assert result == {'foo': 'value'}

    :param graph: :py:class:`~hiku.graph.Graph` definition
    :param result: result of the query
    :param query: executed query, instance of the :py:class:`~hiku.query.Node`
    """
    return _denormalize(graph, graph.root, result, merge([query]))
