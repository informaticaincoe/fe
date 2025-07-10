{
    'name': 'Base Recursos Humanos',
    'depends': ['hr_payroll', 'hr_contract', 'l10n_sv_hr_retenciones'],
    'assets': {
        'web.assets_frontend': [
            'rrhh_base/static/src/css/inter_font.css',
            'rrhh_base/static/src/css/bootstrap.min.css',
        ],
        'web.assets_pdf': [
            'rrhh_base/static/src/css/inter_font.css',
            'rrhh_base/static/src/css/bootstrap.min.css',
        ],
    },
    'license': 'GPL-3',
    'category': 'Human Resources',
    'data': [
        'security/ir.model.access.csv',
        'views/hr_retencion_isss_views.xml',
        'views/hr_retencion_afp_views.xml',
        'views/hr_retencion_renta_views.xml',
        'views/hr_retencion_renta_tramos_views.xml',
        'views/menu_rrhh_base.xml',
        'views/hr_attendance_inherit.xml',
        "report/report.xml",
        "report/report_payslip_incoe.xml",
    ],
    'installable': True,
    # "auto_install": True,  #  Consider removing this
}
