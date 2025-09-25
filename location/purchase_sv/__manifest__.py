# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Fields purchase sv",
    "version": "17.1",
    'license': 'LGPL-3',
    "author": "Gerardo-MiRe",
    "category": "Tools",
    'website': 'https://github.com/Gerardo-MiRe',
    "depends": [
        "purchase",
        "account",
        "l10n_sv",
    ],
    "demo": [
    ],
    "data": [
        'views/purchase.xml',
        'views/account_move.xml',
    ],
    "installable": True,
    "auto_install": False,
}
