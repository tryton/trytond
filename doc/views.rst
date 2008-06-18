==========
Graph view
==========

The dtd that describe the xml for a graph view is stored in
trytond/ir/ui/graph.dtd.

***************
XML description
***************

* tag "graph":

    * "type": vbar, hbar, line, pie

    * "string": the name of the graph

    * "background": an hexaecimal value for the color of the
      background

    * "color": the main color

    * "legend": a boolean to specify if the legend must be display

* tag "x", "y":

    Describe the field that must be used for axis.  "x" must contain
    only one tag "field" and "y" must at least one but may contain
    many.

* tag "field":

    * "name": the name of the field on the object to use

    * "string": allow to override the string that comes from the
      object

    * "key": can be used to distinguish fields with the same name but
      that are different with domain

    * "domain": a string that is evaluate with the object value as
      context. If the result is true the field value is added to the
      graph otherwise not

    * "fill": defined if the graph must be fill

    * "empty": defined if the line graph must put a point for missing
      date


* Example

.. highlight:: xml

::

  <graph string="Invoice by date" type="vbar">
    <x>
        <field name="invoice_date"/>
    </x>
    <y>
        <field name="total_amount"/>
    </y>
  </graph>
