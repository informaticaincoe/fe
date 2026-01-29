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
        'web',
        'l10n_sv_dpto',
        'l10n_sv_hacienda',
        'stock',
        'sale',
        'fleet',
        'hr',
        'account',
        'mail',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_sv_despacho/static/src/js/leaflet_zone_map_field.js',
        ],
    },
    'data': [
        'data/res.configuration.csv',
        'data/res.municipality.csv',
        'security/ir.model.access.csv',

        'views/dispatch_route_view.xml',
        'views/dispatch_route_list_view.xml',
        'views/dispatch_route_reception_view.xml',
        'views/dispatch_zones_view.xml',
        'views/dispatch_route_invoice_return_views.xml',

        'views/dispatch_action.xml',

        'views/dispatch_menu.xml',

    ],

    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}
