# -*- coding: utf-8 -*-
{
    'name': "Facturacion de El Salvador",
    'summary': """Facturacion de El Salvador""",
    'description': """
       Facturacion de El Salvador.
       Permite Imprimir los tres tipos de facturas utilizados en El Salvador
        - Consumidor Final
        - Credito Fiscal
        - Exportaciones
      Tambien permite imprimir los documentos que retifican:
        - Anulaciones.
        - Nota de Credito
        - Anulaciones de Exportacion
      Valida que todos los documentos lleven los registros requeridos por ley
        """,
    'author': "Intelitecsa(Francisco Trejo)",
    'website': "http://www.intelitecsa.com",
    "images": ['static/description/banner.png',
               'static/description/icon.png',
               'static/description/thumbnail.png'],
    'price': 125.00,
    'currency': 'EUR',
    'license': 'GPL-3',
    'category': 'Contabilidad',
    'version': '17.1',
    'depends': ['base', 'l10n_sv', 'account', 'product', 'mail'],
    'assets': {
        # Para el back-end (interfaz de usuario de Odoo):
        'web.assets_backend': [
            'https://cdn.jsdelivr.net/npm/bootstrap@5.4.0/dist/css/bootstrap.min.css',
        ],
        # Si también quieres en la parte pública / website:
        'web.assets_frontend': [
            'https://cdn.jsdelivr.net/npm/bootstrap@5.4.0/dist/css/bootstrap.min.css',
        ],
        'web.assets_pdf': [
            'l10n_invoice_sv/static/src/css/bootstrap.min.css',
        ],
    },
    'data': [
        'views/account_journal.xml',
        'views/posicion_arancel_view.xml',
        'views/product_template_view.xml',
        'views/account_move_view.xml',
        'views/account_tax.xml',
        'data/journal_data.xml',
        'data/mail_template_data.xml',
        'report/report_invoice_anu.xml',
        'report/report_invoice_ccf.xml',
        'report/report_invoice_fcf.xml',
        'report/report_invoice_exp.xml',
        'report/report_invoice_ndc.xml',
        'report/report_invoice_digital.xml',
        'report/report_invoice_ticket.xml',
        'report/invoice_report.xml',
        'report/report_invoice_main.xml',
        'security/ir.model.access.csv',
        'wizard/account_move_reversal.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    # 'post_init_hook': 'set_data',
}
