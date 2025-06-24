{
    'name': 'Base Recursos Humanos',
    'depends': ['hr_payroll', 'hr_contract'],
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
        'views/menu_rrhh_base.xml',
        # 'security/add_group_to_admin.xml',
        "report/report.xml",
        "report/report_payslip_incoe.xml",
    ],
    'installable': True,
    # "auto_install": True,  #  Consider removing this
}
