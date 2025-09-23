# -*- coding: utf-8 -*-
{
    'name': "Anexos MH",
    'summary': """Anexos MH""",
    'author': "INCOE (Brenda Chacon, Kren Burgos, Francisco Flores",
    'website': "http://www.incoe.net",
    'license': 'GPL-3',
    'category': 'Localization',
    'version': '17.1.0',
    'depends': ['base',
                'base_sv',
                'account',
                'phone_validation',
                'l10n_latam_base',
                ],
    'data': [
        "security/ir.model.access.csv",
        "views/report_anexos_search_action.xml",
        'views/view_anexo_consumidor_final.xml',
        'views/view_anexo_contribuyentes.xml',
        'views/view_anexo_compras.xml',
        'views/view_anexo_sujeto_excluido.xml',
        'views/view_anexo_casilla162.xml',
        'views/view_anexo_documentos_anulados_y_extraviados.xml',

        "views/report_anexos_action.xml",
        # 'views/anexos_report_views.xml',

    ],
    'demo': [
        # 'demo.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'country_code': 'SV',
    # 'post_init_hook': 'drop_data',
}
