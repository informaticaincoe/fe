{
    'name': 'Asignaciones Dinámicas de Salario',
    'version': '1.1',
    'summary': 'Permite gestionar horas extra, comisiones y otros ingresos por empleado',
    'category': 'Human Resources',
    'author': 'Intracoe',
    'depends': ['base', 'hr', 'hr_payroll', 'l10n_sv_hr_retenciones', 'hr_work_entry_contract', 'resource'],
    'data': [
        'data/hr_overtime_data.xml',
        'data/hr_salary_assignment_data.xml',
        'data/res.configuration.csv',

        'security/ir.model.access.csv',

        'views/hr_salary_assignment_views.xml',
        'views/hr_salary_assignment_menu.xml',
        'views/hr_salary_assignment_views_inherit.xml',
        'views/res_company_contribution_view.xml',
    ],
    'installable': True,
    'application': False,
    'post_init_hook': 'ejecutar_hooks_post_init', #se ejecuta solo al instalar el módulo.
    #'post_load': 'crear_asistencias_faltantes', #se ejecuta solo al actualizar el módulo.
}
