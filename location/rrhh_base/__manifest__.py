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
        # 'views/hr_salary_attachment_search.xml',
        'views/hr_payroll_reports.xml',
        'views/menu_rrhh_base.xml',
        "views/hr_payslip_month_summary_views.xml",
        'views/hr_attendance_inherit.xml',
        "report/report.xml",
        "report/report_payslip_incoe.xml",
        # "report/report_override_lang.xml",
        "views/hr_payslip_views.xml",
        'data/mail_template_payslip.xml'
    ],
    'installable': True,
    # "auto_install": True,  #  Consider removing this
}
