Views
#####

The views are used to display records of an object to the user.

In tryton, objects can have several views, it is the action, that opens the window, that tells which views must be used.

The views are built from XML that is stored in the databases with the object ir.ui.view.

There is three types of views:

    * Form

    * Tree

    * Graph



Form view
*********

The RNG that describes the xml for a form view is stored in
trytond/ir/ui/form.rng.  There is also a RNC in trytond/ir/ui/form.rnc.

Form view is used to display one record of an object.

Elements of the view are put on the screen following the rules:

    * Elements are placed on the screen from left to right, from top to bottom, according the order of the xml.

    * The screen composed of a table with a fixed number of columns and enough rows to handle all elements.

    * Elements take one or more columns when they are put in the table. If there is not enough free columns on the current row, the elements is put at the begin of the next row.


XML description
+++++++++++++++

Here is the list of common attributes:

    * "expand": A boolean to specify if the label should expand to take up any extra horizontal space.

    * "fill": A boolean to specify if the label should fill the horizontal space allocated to it in the table cell.

    * "xexpand": The same as expand but for vertical space.

    * "xfill": The same as fill but for vertical space.

    * "colspan": The number of columns the label must take in the table.

    * "states": A string of python code that will be evaluated with the field of the current record.  It must return a dictionary where keys can be:
        * 'invisible': If true, the widget will be hidden.
        * 'required': If true, the field will be required.
        * 'readonly': If true, the field will be readonly.

    * "help": The string that will be displayed when the cursor stay over the widget.


form
^^^^

Each form view must start with this tag.

    * "string": The test that will be used as default title for the tab or the window.

    * "on_write": The name of a function that will be call when the record is saved.  The function must have this form "on_write(self, cursor, user, ids, context=None)".

    * "col": The number of column for the view.

    * "cursor": The name of the field that must have the cursor by default.

label
^^^^^

Display static string.

    * "string": The string that will be display in the label.

    * "name": The name of the field from which the description will be used for string.

    * "align": The fraction of horizontal free space that must be put on the left.  0.0 means no free space to the left.  1.0 means all free space to the left.


field
^^^^^

Display a field of the object with the value of the current record.

    * "name": The name of the field.

    * "widget": The widget that must be used instead of the default one.

    * "saves": Only for One2Many fields, it is a boolean that defined if change made in the list must be save directly.

    * "help": The string that will be displayed when the cursor stay over the widget.

    * "width": The minimum width the widget should request, or -1 to unset.

    * "height": The minimum height the widget should request, or -1 to unset.

    * "readonly": Boolean to set the field readonly.

    * "required": Boolean to set the field required.

    * "mode": Only for One2Many fields, it is a comma separated list, that specify the order of of the view used to display the relation. (Example: "tree,form")

    * "completion": Only for Many2One fields, it is a boolean to set the completion of the field.

    * "invisible": The field will not be display, but it will fill cells in the table.

    * "domain": Only for One2Many, Many2One, Many2Many fields, it defines the domain that must be used when searching for relation records.


image
^^^^^

Display a image.

    * "name": the name of the image. It must be the name with the extension of an image from tryton/share/pixmaps/

separator
^^^^^^^^^

Display a horizontal separator.

    * "string": The string that will be display above the separator.

    * "name": The name of the field from which the description will be used for string.

newline
^^^^^^^

Force to use a new row.

button
^^^^^^

Display a button.

    * "string": The string that will be display inside the button.

    * "type": It can be "workflow", "object" or "action". The default is "workflow".
      It defines which type of action must be run when clicking on it.

    * "name": The name of the action:

        * "workflow": the name of the signal that will be send.

        * "object": the name of the function that will called.  The function must have this form "button(self, cursor, user, ids, context=None)".

        * "action": the id of the ir.action that will be called.

    * "confirm": A text that will be display in a confirmation popup when the button is clicked.

notebook
^^^^^^^^

It adds a notebook widget which can contain page tags.

    * "tabpos": It can be "up", "down", "left", "right".

page
^^^^

Define a new tab inside a notebook.

    * "string": The string that will be display in the tab.

    * "angle": The angle that the baseline of the label makes with the horizontal, in degrees, measured counterclockwise.

    * "col": The number of column for the page view.

group
^^^^^

Create a sub-table in a cell.

    * "string": If set a frame will be drawn around the field with a label containing the string. Otherwise, the frame will be invisible.

    * "rowspan": The number of rows the group must take in the table.

    * "col": The number of column for the group contains.

hpaned, vpaned
^^^^^^^^^^^^^^

    * "position": The pixel position of divider, a negative value means that the position is unset

child1,child2
^^^^^^^^^^^^^

Contains the two childs of a hpaned or vpaned.

properties
^^^^^^^^^^

Display a table of 4 columns with all the properties of the object.

Example
+++++++

.. highlight:: xml

::

  <form string="Party" col="6">
      <label name="name"/>
      <field name="name" xexpand="1"/>
      <label name="code"/>
      <field name="code"/>
      <label name="active"/>
      <field name="active" xexpand="0" width="100"/>
      <notebook colspan="6">
          <page string="General">
              <field name="addresses" mode="form,tree" colspan="4" height="200">
              </field>
              <label name="type"/>
              <field name="type" widget="selection"/>
              <label name="lang"/>
              <field name="lang" widget="selection"/>
              <label name="website"/>
              <field name="website" widget="url"/>
              <separator string="Categories" colspan="4"/>
              <field name="categories" colspan="4"/>
          </page>
          <page string="Accounting">
              <label name="vat_country"/>
              <field name="vat_country"/>
              <label name="vat_number"/>
              <field name="vat_number"/>
          </page>
          <page string="Properties">
              <properties/>
          </page>
      </notebook>
  </form>


Tree view
*********


Graph view
**********

The RNG that describes the xml for a graph view is stored in
trytond/ir/ui/graph.rng.  There is also a RNC in trytond/ir/ui/graph.rnc.


XML description
+++++++++++++++

graph
^^^^^

Each graph view must start with this tag.

    * "type": vbar, hbar, line, pie

    * "string": the name of the graph

    * "background": an hexaecimal value for the color of the
      background

    * "color": the main color

    * "legend": a boolean to specify if the legend must be display

x, y
^^^^

    Describe the field that must be used for axis.  "x" must contain
    only one tag "field" and "y" must at least one but may contain
    many.

field
^^^^^

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


Example
+++++++

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
