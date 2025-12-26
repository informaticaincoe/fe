{
    'name': 'Base Recursos Humanos',
    'depends': ['hr_contract', 'l10n_sv_hr_retenciones', 'hr_payroll'],
    'assets': {
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
        'views/hr_payroll_reports.xml',
        'views/menu_rrhh_base.xml',
        "report/report.xml",
        "report/override_payment_report.xml",
        "report/report_payslip_incoe.xml",
        "views/hr_payslip_views.xml",
        'data/mail_template_payslip.xml',
        "views/hr_payslips_send_lotes.xml"
    ],
    'installable': True,
}
