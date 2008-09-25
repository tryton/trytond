Models
######

Models are python classes that usually represent business object or
concepts. Such classes consist essentially of keywords, fields,
constraints and helper functions. They inherit from the OSV class
which provide the framework integration like the database abstraction,
worklows, translations, etc.


The following snippet gives a minimal example:

.. highlight:: python

::

  class Party(OSV):
      "Party"
      _description = __doc__
      _name = "relationship.party"
      name = fields.Char('Name')
  Party()

Instanciating the class make it alive for the framework. Actually
there will be only one instance per class and per database. So model
classes are essentially accessors to the underlying table.


Model Properties
****************

Model properties defines meta-informations about the model, they are
class attributes starting with and underscore.

   * ``_description``: A non technical description of the class.

   * ``_name``: The unique identifier that can be use to reference the
     class across all the framwork. The first part of it must be the
     name in which the class is defined.

   * ``_table``: The name of the database table which is mapped to
     the current class. If not set the value of ``_name`` is used with
     dots converted to underscores.

   * ``_rec_name``: The name of the main field of the class. If not
     set the field ``name`` is used (like in the above example).

   * ``_sequence``: The  name of the postgresql sequence that
     increment the ``id`` column.


   * ``_order_name``: The name of the field on which the row must
     be sorted when the underlying table is read.


   * ``_auto``: When set to ``False`` will prevent the framework from
     creating a table for this class.

   * ``_obj``: (?)

   * ``_sql``: The sql code that must be used to fetch data from the
     database. The columns outputed by the given query must reflect
     the class fields.

Some Model Properties are instance attributes which allow to update
them at other places in the framework 

   * ``_order``: A tuple defining how the row are sorted when the
     underlying table is read. E.g.: ``[('name', 'ASC'), 'age',
     'DESC']``

   * ``_error_messages``: A dictionary mapping keywords to a user
     message. E.g.: ``{'recursive_categories': 'You can not create
     recursive categories!'}``

   * ``_sql_constraints``: A list of constraints that are added on
     the underlying table. E.g.: ``('constrain_name, sql_constraint,
     'error_msg')`` where  ``'constrain_name'`` is the name of the
     sql constraint for the database, ``sql_constraint`` is the actual
     sql constraint (E.g.: ``'UNIQUE(name)'``) and ``'error_msg'`` is
     one of the key of ``_error_messages``.

   * ``_constraints``: A list of constraints that each record must
     respect. Each item of this list is a couple ``('function_name',
     'error_keyword')``, where ``'function_name'`` is the name of a
     method of the same class, which should return a boolean value
     (``False`` when the constraint is violated). ``error_keyword``
     must be one of the key of ``_sql_error_messages``.

   * ``_sql_error_messages``:

   * ``_rpc_allowed``: The list of the names of the method than are
     allowed to be called remotely.


Fields
******

Fields are class attributes that do not start with an underscore. Some
fields are automatically added on each tables: id, create_date,
create_uid, write_date, write_uid. (TODO)


Fields types
^^^^^^^^^^^^

A field can be one of the following basic types:

   * ``Char``: A string of character.

   * ``Text``: A multi-line text.

   * ``Boolean``: True or False.

   * ``Integer``: An integer number.

   * ``Float``: A floating point number.

   * ``Numeric``: Like Float, but provide an arbitrary precision on
     all operations.

   * ``Date``: A day. E.g.: 2008-12-31.

   * ``DateTime``: A time in a day. E.g.: 2008-12-31 11:30:59.

   * ``Selection``: A value from a list. E.g.: Male, Female.

   * ``Binary``: A blob. E.g.: a picture.

   * ``Sha``: Like a char but his content is never shown to the
     user. The typical usage is for password fields.

Or one of these composed types:

   * ``Property``:

   * ``Reference``:

Or one of these relation types:

   * ``Many2One``:

   * ``One2Many``:

   * ``Many2Many``:

Fields options
^^^^^^^^^^^^^^

This options are avalaible on several types of fields:

   * ``readonly``

   * ``required``

   * ``help``

   * ``select``

   * ``on_change``

   * ``states``

   * ``domain``

   * ``translate``


Other options:




Function field can be used to mimic any other type:

   * ``Function``:



Manipulating Models
###################

Create
******

Read
****

Browse
******

Write
*****

Delete
******

inheritance
###########

