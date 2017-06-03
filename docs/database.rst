Using Database :sup:`feat. SQLAlchemy`
======================================

Hiku provides support for loading data from SQL databases using SQLAlchemy_
library, but Hiku doesn't requires to use it's ORM layer, it requires only Core
SQLAlchemy_ functionality - tables definition and expression language to
construct SELECT queries.

Prerequisites
~~~~~~~~~~~~~

.. note:: Source code of this example can be found
    `on GitHub <https://github.com/vmagamedov/hiku/blob/master/docs/test_database.py>`_.

We will translate our previous example from the :doc:`basics`, but now all
the data is stored in the SQLite database:

.. literalinclude:: test_database.py
    :lines: 3-39

Graph definition
~~~~~~~~~~~~~~~~

Defined tables can be exposed as graph of nodes:

.. _guide-database-graph:

.. literalinclude:: test_database.py
    :lines: 43-91
    :linenos:
    :emphasize-lines: 6,8,12-14,16,19,20,22,40-41

In the previous examples all the data was available as data structures, so no
special access method was required. With databases we will require a database
connection in order to fetch any data from it. Hiku provides simple and implicit
way to solve this issue without using global variables (thread-locals) - by
providing query execution context.

Query execution context is a simple mapping, where you can store and read values
during query execution. In this example we are using ``SA_ENGINE_KEY`` constant
:sup:`[19]` as a key to access our SQLAlchemy's engine. In order to access query
context :py:func:`~hiku.engine.pass_context` decorator should be used
:sup:`[19]` and then ``to_characters_query`` function :sup:`[20]` will receive
it as a first positional argument. ``SA_ENGINE_KEY`` constant is used to get
SQLAlchemy's engine from the context :sup:`[22]` in order to execute SQL query.

:py:class:`~hiku.sources.sqlalchemy.FieldsQuery` :sup:`[8]` and
:py:class:`~hiku.sources.sqlalchemy.LinkQuery` :sup:`[12-14]` are using context
in the same manner.

Hiku's SQLAlchemy support is provided by
:py:class:`hiku.sources.sqlalchemy.FieldsQuery` and
:py:class:`hiku.sources.sqlalchemy.Field` to express table columns as fields in
the node. And by :py:class:`hiku.sources.sqlalchemy.LinkQuery` and
:py:class:`hiku.sources.sqlalchemy.Link` to express relations between tables as
links between nodes.

``direct_link`` :sup:`[16]` is a special case: when one table contains foreign
key to the other table - `many-to-one` relation or `one-to-one` relation, no
additional queries needed to make a direct link between those tables as nodes.
``character`` link :sup:`[40-41]` is a good example of such direct link.

Other relation types require to make additional query in order to fetch linked
node ids. ``to_actors_query`` :sup:`[12-14]` for example. Such queries require
selecting only one table, ``actor_table`` in this example. SQL query will be
looking like this:

.. code-block:: sql

    SELECT actor.id FROM actor
      WHERE actor.character_id IN (character_ids);

List of ``character_ids`` we already know (it is an ``id`` field of the current
node), all we need is to fetch ``actor.id`` column to make a link from
``character`` node to the ``actor`` node.
:py:class:`~hiku.sources.sqlalchemy.LinkQuery` does this for you.

Querying graph
~~~~~~~~~~~~~~

For testing purposes let's define helper function ``execute``:

.. literalinclude:: test_database.py
    :lines: 95-105

Testing one to many link:

.. literalinclude:: test_database.py
    :lines: 108-133
    :dedent: 4

Testing many to one link:

.. literalinclude:: test_database.py
    :lines: 136-164
    :dedent: 4

.. _SQLAlchemy: http://www.sqlalchemy.org
