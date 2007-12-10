import os, sys, imp
import itertools
from sets import Set
from config import CONFIG
import tools
import pooler
from netsvc import Logger, LOG_ERROR, LOG_INFO
import zipfile

OPJ = os.path.join
ADDONS_PATH = OPJ(os.path.dirname(__file__), 'addons')
sys.path.insert(1, ADDONS_PATH)

class Graph(dict):

    def add_node(self, name, deps):
        max_depth, father = 0, None
        for i in [Node(x, self) for x in deps]:
            if i.depth >= max_depth:
                father = i
                max_depth = i.depth
        if father:
            father.add_child(name)
        else:
            Node(name, self)

    def __iter__(self):
        level = 0
        done = Set(self.keys())
        while done:
            level_modules = [(name, module) for name, module in self.items() \
                    if module.depth==level]
            for name, module in level_modules:
                done.remove(name)
                yield module
            level += 1


class Singleton(object):

    def __new__(cls, name, graph):
        if name in graph:
            inst = graph[name]
        else:
            inst = object.__new__(cls)
            graph[name] = inst
        return inst


class Node(Singleton):

    def __init__(self, name, graph):
        super(Node, self).__init__()
        self.name = name
        self.graph = graph
        self.datas = None
        if not hasattr(self, 'childs'):
            self.childs = []
        if not hasattr(self, 'depth'):
            self.depth = 0

    def add_child(self, name):
        node = Node(name, self.graph)
        node.depth = self.depth + 1
        if node not in self.childs:
            self.childs.append(node)
        for attr in ('init', 'update', 'demo'):
            if hasattr(self, attr):
                setattr(node, attr, True)
        self.childs.sort(lambda x, y: cmp(x.name, y.name))

    def has_child(self, name):
        return Node(name, self.graph) in self.childs or \
                bool([c for c in self.childs if c.has_child(name)])

    def __setattr__(self, name, value):
        super(Node, self).__setattr__(name, value)
        if name in ('init', 'update', 'demo'):
            CONFIG[name][self.name] = 1
            for child in self.childs:
                setattr(child, name, value)
        if name == 'depth':
            for child in self.childs:
                setattr(child, name, value + 1)

    def __iter__(self):
        return itertools.chain(iter(self.childs),
                *[iter(x) for x in self.childs])

    def __str__(self):
        return self.pprint()

    def pprint(self, depth=0):
        res = '%s\n' % self.name
        for child in self.childs:
            res += '%s`-> %s' % ('    ' * depth, child.pprint(depth + 1))
        return res

def create_graph(module_list, force=None):
    if force is None:
        force = []
    graph = Graph()
    packages = []

    for module in module_list:
        if module[-4:] == '.zip':
            module = module[:-4]
        terp_file = OPJ(ADDONS_PATH, module, '__terp__.py')
        mod_path = OPJ(ADDONS_PATH, module)
        if module in ('ir', 'workflow', 'res'):
            root_path = os.path.dirname(__file__)
            terp_file = OPJ(root_path, module, '__terp__.py')
            mod_path = OPJ(root_path, module)
        if os.path.isfile(terp_file) or zipfile.is_zipfile(mod_path+'.zip'):
            try:
                info = eval(tools.file_open(terp_file).read())
            except:
                Logger().notify_channel('init', LOG_ERROR,
                        'addon:%s:eval file %s' % (module, terp_file))
                raise
            if info.get('installable', True):
                packages.append((module, info.get('depends', []), info))

    current, later = Set([x[0] for x in packages]), Set()
    while packages and current > later:
        package, deps, datas = packages[0]

        # if all dependencies of 'package' are already in the graph,
        # add 'package' in the graph
        if reduce(lambda x, y: x and y in graph, deps, True):
            if not package in current:
                packages.pop(0)
                continue
            later.clear()
            current.remove(package)
            graph.add_node(package, deps)
            node = Node(package, graph)
            node.datas = datas
            for kind in ('init', 'demo', 'update'):
                if (package in CONFIG[kind]) \
                        or ('all' in CONFIG[kind]) \
                        or (kind in force):
                    setattr(node, kind, True)
        else:
            later.add(package)
            packages.append((package, deps, datas))
        packages.pop(0)

    for package in later:
        Logger().notify_channel('init', LOG_ERROR,
                'addon:%s:Unmet dependency' % package)
    return graph

def init_module_objects(cursor, module_name, obj_list):
    Logger().notify_channel('init', LOG_INFO,
            'addon:%s:creating or updating database tables' % module_name)
    for obj in obj_list:
        obj.auto_init(cursor)

def load_module_graph(cursor, graph, **kwargs):
    # **kwargs is passed directly to convert_xml_import
    package_todo = []
    statusi = 0
    for package in graph:
        module = package.name
        Logger().notify_channel('init', LOG_INFO, 'addon:%s' % module)
        sys.stdout.flush()
        pool = pooler.get_pool(cursor.dbname)
        modules = pool.instanciate(module)
        cursor.execute('SELECT state, demo FROM ir_module_module WHERE name = %s',
                (module,))
        (package_state, package_demo) = (cursor.rowcount and cursor.fetchone()) \
                or ('uninstalled', False)
        idref = {}
        if hasattr(package, 'init') \
                or hasattr(package, 'update') \
                or (package_state in ('to install', 'to upgrade')):
            init_module_objects(cursor, module, modules)
            for kind in ('init', 'update'):
                for filename in package.datas.get('%s_xml' % kind, []):
                    mode = 'update'
                    if hasattr(package, 'init') or package_state=='to install':
                        mode = 'init'
                    Logger().notify_channel('init', LOG_INFO,
                            'addon:%s:loading %s' % (module, filename))
                    ext = os.path.splitext(filename)[1]
                    if ext == '.csv':
                        tools.convert_csv_import(cursor, module,
                                os.path.basename(filename),
                                tools.file_open(OPJ(module, filename)).read(),
                                idref, mode=mode)
                    elif ext == '.sql':
                        queries = tools.file_open(OPJ(module,
                            filename)).read().split(';')
                        for query in queries:
                            new_query = ' '.join(query.split())
                            if new_query:
                                cursor.execute(new_query)
                    else:
                        tools.convert_xml_import(cursor, module,
                                tools.file_open(OPJ(module, filename)).read(),
                                idref, mode=mode, **kwargs)
            if hasattr(package, 'demo') \
                    or (package_demo and package_state != 'installed'):
                for xml in package.datas.get('demo_xml', []):
                    ext = os.path.splitext(xml)[1]
                    Logger().notify_channel('init', LOG_INFO,
                            'addon:%s:loading %s' % (module, xml))
                    if ext == '.csv':
                        tools.convert_csv_import(cursor, module,
                                os.path.basename(xml),
                                tools.file_open(OPJ(module, xml)).read(), idref,
                                noupdate=True)
                    else:
                        tools.convert_xml_import(cursor, module,
                                tools.file_open(OPJ(module, xml)).read(), idref,
                                noupdate=True, **kwargs)
                cursor.execute('UPDATE ir_module_module SET demo = %s ' \
                        'WHERE name = %s', (True, package.name))
            package_todo.append(package.name)
            cursor.execute("UPDATE ir_module_module SET state = 'installed' " \
                    "WHERE state IN ('to upgrade', 'to install') " \
                        "AND name = %s", (package.name,))
        cursor.commit()
        statusi += 1

    pool = pooler.get_pool(cursor.dbname)
    pool.get('ir.model.data')._process_end(cursor, 1, package_todo)
    cursor.commit()

def register_classes():
    module_list = os.listdir(ADDONS_PATH)
    module_list.append('ir')
    module_list.append('workflow')
    import ir
    import workflow
    import res
    for package in create_graph(module_list):
        module = package.name
        Logger().notify_channel('init', LOG_INFO,
                'addon:%s:registering classes' % module)
        sys.stdout.flush()

        if module in ('ir', 'workflow', 'res'):
            continue

        if not os.path.isfile(OPJ(ADDONS_PATH, module+'.zip')):
            # XXX must restrict to only addons paths
            imp.load_module(module, *imp.find_module(module))
        else:
            import zipimport
            mod_path = OPJ(ADDONS_PATH, module+'.zip')
            try:
                zimp = zipimport.zipimporter(mod_path)
                zimp.load_module(module)
            except zipimport.ZipImportError:
                Logger().notify_channel('init', LOG_ERROR,
                        'Couldn\'t find module %s' % module)

def load_modules(database, force_demo=False, update_module=False):
    cursor = database.cursor()
    force = []
    if force_demo:
        force.append('demo')
    if update_module:
        cursor.execute("SELECT name FROM ir_module_module " \
                "WHERE state IN ('installed', 'to install', " \
                    "'to upgrade', 'to remove')")
    else:
        cursor.execute("SELECT name FROM ir_module_module " \
                "WHERE state IN ('installed', 'to upgrade', 'to remove')")
    module_list = [name for (name,) in cursor.fetchall()]
    graph = create_graph(module_list, force)
    report = tools.AssertionReport()
    load_module_graph(cursor, graph, report=report)
    if report.get_report():
        Logger().notify_channel('init', LOG_INFO, 'assert:%s' % report)

    for kind in ('init', 'demo', 'update'):
        CONFIG[kind] = {}

    if update_module:
        cursor.execute("SELECT name FROM ir_module_module " \
                "WHERE state IN ('to remove')")
        for (mod_name,) in cursor.fetchall():
            pool = pooler.get_pool(cursor.dbname)
            cursor.execute('SELECT model,res_id FROM ir_model_data ' \
                    'WHERE NOT noupdate AND module = %s ' \
                    'ORDER BY id DESC', (mod_name,))
            for rmod, rid in cursor.fetchall():
                # TODO: Improved
                # I can not use the class_pool has _table could be
                # defined in __init__ and I can not use the pool has
                # the module could not be loaded in the pool
                uid = 1
                pool.get(rmod).unlink(cursor, uid, [rid])
            cursor.commit()
        # TODO: remove menu without actions of childs
        cursor.execute('DELETE FROM ir_ui_menu ' \
                'WHERE (id NOT IN (' \
                        'SELECT parent_id FROM ir_ui_menu ' \
                            'WHERE parent_id IS NOT NULL)) ' \
                    'AND (id NOT IN (' \
                        'SELECT res_id FROM ir_values ' \
                            'WHERE model = \'ir.ui.menu\')) ' \
                    'AND (id NOT IN (' \
                        'SELECT res_id FROM ir_model_data ' \
                            'WHERE model = \'ir.ui.menu\'))')

        cursor.execute("UPDATE ir_module_module SET state = %s " \
                "WHERE state IN ('to remove')", ('uninstalled',))
        cursor.commit()
        pooler.restart_pool(cursor.dbname)
    cursor.close()
