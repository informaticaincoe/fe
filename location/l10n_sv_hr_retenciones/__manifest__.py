{
    "name": "Deducciones",
    "version": "1.0",
    "license": "LGPL-3",
    "author": "Intracoe",
    "category": "Human Resources - Deducciones",
    "depends": [
        "hr", "hr_payroll"
    ],
    "data": [
        "data/hr.retencion.isss.csv",
        "data/hr.retencion.afp.csv",
        "data/hr.retencion.renta.csv",
        "data/hr.retencion.tramo.csv",

        "security/ir.model.access.csv",

        "data/estructura_salarial_incoe.xml",

        "data/deduccion_ISSS_data.xml",
        "data/deduccion_AFP_data.xml",
        "data/deduccion_ISR_data.xml",
        "data/deduccion_FSV_data.xml",
        "data/deduccion_fondo_pensiones_data.xml",
        "data/deduccion_venta_empleados.xml",
        "data/deduccion_prestamos.xml",
        "data/deduccion_otras.xml",

        "views/hr_payslip_form_inherit.xml",
    ],
    "installable": True,
    "auto_install": False,
    "summary": "Deducciones de Renta, ISSS y AFP para planilla",
    "description": "Gestiona deducciones automáticas de ISR, AFP e ISR según tramos.",
    'post_init_hook': 'post_init_configuracion_reglas',
}
