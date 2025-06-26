{
    'name': 'Asignaciones Dinámicas de Salario',
    'version': '1.0',
    'summary': 'Permite gestionar horas extra, comisiones y otros ingresos por empleado',
    'category': 'Human Resources',
    'author': 'Intracoe',
    'depends': ['base', 'hr', 'hr_payroll'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_salary_assignment_views.xml',
        'views/hr_salary_assignment_menu.xml',
    ],
    'installable': True,
    'application': False,
}
