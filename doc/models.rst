Models
######

Models are python classes that usually represent real-life object or
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

Keywords
********

Keywords defines meta-informations about the model:

   * ``_description``: A non technical description of the class.

   * ``_name``: The unique identifier that can be use to reference the
     class across all the framwork. The first part of it must be the
     name in which the class is defined.

   * ``_table``: The name of the database table which is mapped to
     the current class. If not set the value of ``_name`` is used with
     dots converted to underscores.

   * ``_rec_name``: The name of the main field of the class. If not
     set the field ``name`` is used (like in the above example).

   * ``_sequence``: The name of the field on which the result must
     be sorted when the underling table is read.


   * ``_order_name``

   * ``_order``

   * ``_auto``: When set to ``False`` will prevent the framework from
     creating a table for this class.

   * ``_obj``

   * ``_sql``: The sql code that must be used to fetch data from the
     database. The columns outputed by the given query must reflect
     the class fields.

Fields
******

Fields types
^^^^^^^^^^^^

A field can be one of the following basic types:

   * ``Char``: A string of character.

   * ``Text``: A mulit-line text.

   * ``Boolean``: True or False.

   * ``Integer``: An integer number.

   * ``Float``: A floating point number.

   * ``Numeric``: Like Float, but provide an arbitrary precision on
     all operations.

   * ``Date``: A day. E.g.: 2008-12-31.

   * ``DateTime``: A time in a day. E.g.: 2008-12-31 11:30:59.

   * ``Selection``: A list of values E.g.: Male, Female.

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

Write
*****

Delete
******

