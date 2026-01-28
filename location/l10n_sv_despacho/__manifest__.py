{
    'name': 'Despachos',
    'summary': 'Gestión de despachos',
    'description': """
    Módulo para la gestión de despachos.
    """,
    'author': 'INCOE (Brenda Chacon, Karen Burgos, Francisco Flores)',
    'website': 'http://www.incoe.net',
    'category': 'Inventory',
    'version': '18.0.1.0.1',
    'depends': [
        'stock',
        'sale',
        'fleet',
        'hr',
        'account',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/dispatch_action.xml',
        'views/dispatch_menu.xml',
        'views/dispatch_route_view.xml',
        'views/dispatch_route_list_view.xml',
    ],
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}
