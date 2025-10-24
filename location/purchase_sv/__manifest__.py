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
        "l10n_sv_mh_anexos"
    ],
    "demo": [
    ],
    "data": [
        "security/ir.model.access.csv",

        'views/purchase.xml',
        'views/account_move.xml',
        'views/account_move_reversal.xml',
        'views/account_move_line_view.xml',
        "views/exp_duca_views.xml",
        "views/account_move_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}