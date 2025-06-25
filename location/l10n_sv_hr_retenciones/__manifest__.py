{
    "name": "Deducciones",
    "version": "1.0",
    "license": "LGPL-3",
    "author": "Intracoe",
    "category": "Human Resources",
    "depends": [
        "hr", "hr_payroll"
    ],
    "data": [
        "report/report.xml",
        "report/report_payslip_incoe.xml",
        "data/deduccion_afp_data.xml",
        "data/deduccion_isss_data.xml",

        "data/hr.retencion.isss.csv",
        "data/hr.retencion.afp.csv",
        "data/hr.retencion.renta.csv",
        "data/hr.retencion.tramo.csv",

        "security/ir.model.access.csv",

        #"views/hr_retencion_view.xml",
        #"views/hr_retencion_tramo_view.xml",

        "data/deduccion_ISSS_data.xml",
        "data/deduccion_afp_data.xml",
        "data/deduccion_ISR_data.xml",
        "views/hr_payslip_form_inherit.xml",
        "views/hr_payslip_report_inherit.xml",
    ],
    "installable": True,
    "auto_install": False,
    "summary": "Deducciones de Renta, ISSS y AFP para planilla",
    "description": "Gestiona deducciones automáticas de ISR, AFP e ISR según tramos.",
    'post_init_hook': 'post_init_configuracion_reglas',
}
