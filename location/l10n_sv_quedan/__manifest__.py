{
    'name': 'Gestión de Quedanes (El Salvador)',
    'version': '1.0',
    'summary': 'Permite registrar y controlar quedanes de proveedores',
    'author': 'INCOE IT',
    'category': 'Accounting',
    'depends': ['account'],
    'data': [
    'security/ir.model.access.csv',
    'data/account_quedan_sequence.xml',
    'views/account_quedan_views.xml',
],

    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
