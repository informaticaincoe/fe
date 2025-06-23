{
    'name': 'Base Recursos Humanos',
    'depends': ['hr_payroll', 'hr_contract'],
    'license': 'GPL-3',
    'category': 'Human Resources',
    'data': [
        'security/ir.model.access.csv',
        # 'views/hr_inherit_id.xml',
        'views/menu_rrhh_base.xml',
        # 'security/add_group_to_admin.xml',
        "report/report.xml",
        "report/report_payslip_incoe.xml",
    ],
    'installable': True,
    #"auto_install": True,  #  Consider removing this
}