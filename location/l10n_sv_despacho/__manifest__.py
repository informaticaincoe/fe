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
            'l10n_sv_despacho/static/src/js/map_field.js',
            'l10n_sv_despacho/static/src/xml/map_template.xml',
            'https://maps.googleapis.com/maps/api/js?key=AIzaSyCrGkTd0pXFZ1lZbj4DJrmsnmmXvT_DKjg',
        ],
    },
    'data': [
        'data/res.configuration.csv',
        'data/res.municipality.csv',
        "data/dispatch_sequences.xml",
        'data/dispatch_route_sequence.xml',

        'security/ir.model.access.csv',

        'views/dispatch_action.xml',

        'views/dispatch_route_view.xml',
        'views/dispatch_route_list_view.xml',
        'views/dispatch_route_reception_view.xml',
        'views/dispatch_zones_view.xml',
        'views/dispatch_route_invoice_return_views.xml',
        'views/vehicule_dispatch_route_view.xml',

        'views/dispatch_menu.xml',

        'report/dispatch_report.xml',
        'report/report_recepcion_ruta_template.xml',
        'views/vehicule_dispatch_route_view.xml',
        'report/report_carga_ruta_template.xml',
        'views/dispatch_delivery_analysis_views.xml',
        'report/dispatch_delivery_analysis_template.xml',
    ],

    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}
