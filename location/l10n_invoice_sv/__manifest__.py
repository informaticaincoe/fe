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
        'views/retencion_recibida1_view.xml',
        'views/menu_retencion_recibida_1.xml',
        'views/res_partner_configuracion_pagos_default.xml',

        'data/journal_data.xml',
        'data/mail_template_data.xml',
        'report/report_invoice_anu.xml',
        'report/report_invoice_ccf.xml',
        'report/report_invoice_fcf.xml',
        'report/report_invoice_exp.xml',
        'report/report_invoice_ndc.xml',
        'report/report_invoice_cse.xml',
        'report/report_invoice_ndd.xml',
        'report/report_invoice_digital.xml',
        'report/report_invoice_ticket.xml',
        'report/invoice_report.xml',
        'report/report_invoice_main.xml',
        'security/ir.model.access.csv',
        'wizard/account_move_reversal.xml',
        'views/account_lines.xml',
        'views/sale_order.xml',
        'data/account_retention_accounts.xml',
        'data/account_discount.xml',
        'views/res_partner_contribuyente.xml',
        'views/account_move_fechas_view.xml',
        'views/report_invoice_switch.xml',
        'views/account_move_print_pdf.xml'

    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    # 'post_init_hook': 'set_data',
}
