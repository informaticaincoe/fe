{
    "name": "RRHH - Planilla Única",
    "depends": [
        "base",
        "hr",
        "hr_payroll",
        "rrhh_base",
        "l10n_sv_hr_asignaciones",
        "l10n_sv_hr_retenciones",
    ],
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
        "views/hr_payslip_menu.xml",
        "views/hr_employees_planilla_unica_data.xml",
        "views/hr_payslip_planilla_unica_reporte.xml",
    ],
    'installable': True,
}
