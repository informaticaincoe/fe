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
        "l10n_sv_hacienda_contingencia",
        "l10n_invoice_sv",
    ],
    "demo": [
    ],
    "data": [
        'views/purchase.xml',
        'views/account_move.xml',
        'views/account_move_reversal.xml',
        'views/account_move_line_view.xml',
    ],
    "installable": True,
    "auto_install": False,
}
