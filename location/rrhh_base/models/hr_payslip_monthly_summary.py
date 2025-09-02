from datetime import date
from odoo import api, fields, models, tools


class HrPayslipMonthlySummary(models.Model):
    _name = 'hr.payslip.monthly.summary'
    _description = 'Resumen mensual de nómina (suma quincenas)'
    _auto = False
    _order = 'period_year desc, period_month desc, employee_id'

    PERIOD_MONTHS = [
        ('01', 'enero'), ('02', 'febrero'), ('03', 'marzo'),
        ('04', 'abril'), ('05', 'mayo'), ('06', 'junio'),
        ('07', 'julio'), ('08', 'agosto'), ('09', 'septiembre'),
        ('10', 'octubre'), ('11', 'noviembre'), ('12', 'diciembre'),
    ]

    @api.model
    def year_selection(self):
        y = date.today().year
        # Ajusta el rango a tu gusto
        years = list(range(y - 5, y + 2))
        return [(str(v), str(v)) for v in years]

    period_year = fields.Selection(selection=year_selection, string='Año', readonly=True, index=True)
    period_month = fields.Selection(selection=PERIOD_MONTHS, string='Mes', readonly=True, index=True)

    employee_id = fields.Many2one('hr.employee', string='Empleado', readonly=True)
    department_id = fields.Many2one('hr.department', string='Departamento', readonly=True)

    # === Totales agregados (suma de ambas quincenas) ===
    total_worked_days = fields.Float('Días laborados', readonly=True)
    total_worked_hours = fields.Float('Horas laboradas', readonly=True)

    salario_pagar = fields.Float('Salario a pagar', readonly=True)
    comisiones = fields.Float('Comisiones', readonly=True)
    total_comisiones = fields.Float('Total comisiones', readonly=True) #comisiones normales + vacaciones
    total_overtime = fields.Float('Horas extras', readonly=True)

    viaticos = fields.Float('Viáticos ordinarios', readonly=True)
    total_viaticos_a_pagar = fields.Float('Total viáticos', readonly=True)
    vacaciones = fields.Float('Vacaciones', readonly=True)

    total_devengado = fields.Float('Total devengado', readonly=True)

    isss = fields.Float('ISSS', readonly=True)
    isr = fields.Float('ISR', readonly=True)
    afp = fields.Float('AFP Crecer', readonly=True)
    afp_confia = fields.Float('AFP Confia', readonly=True)
    afp_IPSFA = fields.Float('ipsfa', readonly=True)
    otros = fields.Float('Otros', readonly=True)
    bancos = fields.Float('Bancos', readonly=True)
    venta_empleados = fields.Float('Venta empleados', readonly=True)
    prestamos_incoe = fields.Float('Préstamos INCOE', readonly=True)
    fsv = fields.Float('FSV', readonly=True)

    total_descuentos = fields.Float('Total descuentos', readonly=True)
    sueldo_liquido = fields.Float('Líquido a recibir', readonly=True)

    @api.model
    def _select(self):
        return """
            WITH wd AS (
                SELECT
                    wd.payslip_id,
                    COALESCE(SUM(wd.number_of_days), 0)  AS worked_days,
                    COALESCE(SUM(wd.number_of_hours), 0) AS worked_hours
                FROM hr_payslip_worked_days wd
                GROUP BY wd.payslip_id
            ),
            pl AS (
                SELECT
                    l.slip_id,
                    /* Ingresos/Percepciones */
                    COALESCE(SUM(CASE WHEN l.code = 'COMISION'   THEN l.amount ELSE 0 END), 0) AS comisiones,
                    COALESCE(SUM(CASE WHEN l.code = 'OVERTIME'   THEN l.amount ELSE 0 END), 0) AS overtime,
                    COALESCE(SUM(CASE WHEN l.code = 'BONO'       THEN l.amount ELSE 0 END), 0) AS bonos,
                    COALESCE(SUM(CASE WHEN l.code = 'VIATICO'    THEN l.amount ELSE 0 END), 0) AS viaticos,
                    COALESCE(SUM(CASE WHEN l.code = 'VACACIONES' THEN l.amount ELSE 0 END), 0) AS vacaciones,

                    /* Descuentos */
                    COALESCE(SUM(CASE WHEN l.code = 'DESC_FALTA_SEPTIMO' THEN l.amount ELSE 0 END), 0) AS desc_falta,
                    COALESCE(SUM(CASE WHEN l.code = 'ISSS'       THEN l.amount ELSE 0 END), 0) AS isss,
                    COALESCE(SUM(CASE WHEN l.code = 'RENTA'      THEN l.amount ELSE 0 END), 0) AS renta,
                    COALESCE(SUM(CASE WHEN l.code = 'DEV_RENTA'  THEN l.amount ELSE 0 END), 0) AS dev_renta,
                    COALESCE(SUM(CASE WHEN l.code = 'AFP'        THEN l.amount ELSE 0 END), 0) AS afp,
                    COALESCE(SUM(CASE WHEN l.code = 'AFP_CONF'   THEN l.amount ELSE 0 END), 0) AS afp_confia,
                    COALESCE(SUM(CASE WHEN l.code = 'AFP_IPSFA'  THEN l.amount ELSE 0 END), 0) AS afp_ipsfa,

                    COALESCE(SUM(CASE WHEN l.code = 'OTROS'           THEN l.amount ELSE 0 END), 0) AS otros,
                    COALESCE(SUM(CASE WHEN l.code = 'BANCO'           THEN l.amount ELSE 0 END), 0) AS bancos,
                    COALESCE(SUM(CASE WHEN l.code = 'VENTA_EMPLEADOS' THEN l.amount ELSE 0 END), 0) AS venta_empleados,
                    COALESCE(SUM(CASE WHEN l.code = 'PRESTAMOS'       THEN l.amount ELSE 0 END), 0) AS prestamos_incoe,
                    COALESCE(SUM(CASE WHEN l.code = 'FSV'             THEN l.amount ELSE 0 END), 0) AS fsv
                FROM hr_payslip_line l
                GROUP BY l.slip_id
            )
            SELECT
                MIN(ps.id)                             AS id,
                ps.employee_id                         AS employee_id,
                emp.department_id                      AS department_id,
                ps.period_year                         AS period_year,
                ps.period_month                        AS period_month,

                /* Días / horas */
                COALESCE(SUM(wd.worked_days), 0)       AS total_worked_days,
                COALESCE(SUM(wd.worked_hours), 0)      AS total_worked_hours,

                /* Salario a pagar por slip */
                SUM( COALESCE(ps.basic_wage, 0) - ABS(COALESCE(pl.desc_falta, 0)) ) AS salario_pagar,

                /* Viáticos ordinarios (solo VIATICO) */
                SUM(COALESCE(pl.viaticos, 0))          AS viaticos,

                /* Total comisiones = comisiones + vacaciones + bonos */
                SUM(COALESCE(pl.comisiones, 0) + ABS(COALESCE(pl.vacaciones, 0)) + ABS(COALESCE(pl.bonos, 0)) ) AS total_comisiones,

                /* Horas extra */
                SUM(COALESCE(pl.overtime, 0))          AS total_overtime,

                /* Total viáticos a pagar = viáticos + overtime */
                SUM(COALESCE(pl.viaticos, 0) + COALESCE(pl.overtime, 0)) AS total_viaticos_a_pagar,

                SUM(COALESCE(pl.vacaciones, 0))        AS vacaciones,

                /* Total devengado */
                SUM( COALESCE(ps.basic_wage, 0) - ABS(COALESCE(pl.desc_falta, 0))
                    + COALESCE(pl.comisiones, 0)
                    + COALESCE(pl.viaticos, 0) + COALESCE(pl.bonos, 0) + COALESCE(pl.overtime, 0) + COALESCE(pl.vacaciones, 0)
                ) AS total_devengado,

                /* Descuentos */
                SUM(ABS(COALESCE(pl.isss, 0)))         AS isss,
                SUM(ABS(COALESCE(pl.renta, 0)) - ABS(COALESCE(pl.dev_renta, 0))) AS isr,
                SUM(ABS(COALESCE(pl.afp, 0)))          AS afp,
                SUM(ABS(COALESCE(pl.afp_confia, 0)))   AS afp_confia,
                SUM(ABS(COALESCE(pl.afp_ipsfa, 0)))    AS afp_ipsfa,
                SUM(ABS(COALESCE(pl.otros, 0)))        AS otros,
                SUM(ABS(COALESCE(pl.bancos, 0)))       AS bancos,
                SUM(ABS(COALESCE(pl.venta_empleados, 0))) AS venta_empleados,
                SUM(ABS(COALESCE(pl.prestamos_incoe, 0))) AS prestamos_incoe,
                SUM(ABS(COALESCE(pl.fsv, 0)))          AS fsv,

                /* Total descuentos (tu convención) */
                SUM(
                    ABS(COALESCE(pl.isss, 0)) +
                    (ABS(COALESCE(pl.renta, 0)) - ABS(COALESCE(pl.dev_renta, 0))) +
                    ABS(COALESCE(pl.afp, 0)) +
                    ABS(COALESCE(pl.otros, 0)) +
                    ABS(COALESCE(pl.bancos, 0)) +
                    ABS(COALESCE(pl.fsv, 0)) +
                    ABS(COALESCE(pl.prestamos_incoe, 0)) +
                    ABS(COALESCE(pl.venta_empleados, 0))
                ) AS total_descuentos,

                /* Líquido = devengado - descuentos (recalculado) */
                (
                 SUM( COALESCE(ps.basic_wage, 0) - ABS(COALESCE(pl.desc_falta, 0))
                    + COALESCE(pl.comisiones, 0)
                    + COALESCE(pl.viaticos, 0) + COALESCE(pl.bonos, 0) + COALESCE(pl.overtime, 0) + COALESCE(pl.vacaciones, 0)
                ) 
                -
                SUM(
                    ABS(COALESCE(pl.isss, 0)) +
                    (ABS(COALESCE(pl.renta, 0)) - ABS(COALESCE(pl.dev_renta, 0))) +
                    ABS(COALESCE(pl.afp, 0)) +
                    ABS(COALESCE(pl.otros, 0)) +
                    ABS(COALESCE(pl.bancos, 0)) +
                    ABS(COALESCE(pl.fsv, 0)) +
                    ABS(COALESCE(pl.prestamos_incoe, 0)) +
                    ABS(COALESCE(pl.venta_empleados, 0))
                )) AS sueldo_liquido
        """

    @api.model
    def _from(self):
        return """
            FROM hr_payslip ps
            JOIN hr_employee emp ON emp.id = ps.employee_id
            LEFT JOIN wd ON wd.payslip_id = ps.id
            LEFT JOIN pl ON pl.slip_id = ps.id
            JOIN hr_payroll_structure s ON s.id = ps.struct_id
        """

    @api.model
    def _where(self):
        return """
            WHERE s.code IN ('INCOE', 'PLAN_VAC')
              AND ps.struct_id IS NOT NULL
              /* Opcional: solo confirmadas/pagadas */
              /* AND ps.state IN ('done','paid') */
        """

    @api.model
    def _group_by(self):
        return """
            GROUP BY
                ps.employee_id,
                emp.department_id,
                ps.period_year,
                ps.period_month
        """

    def init(self):
        tools.drop_view_if_exists(self._cr, 'hr_payslip_monthly_summary')
        self._cr.execute(f"""
            CREATE OR REPLACE VIEW hr_payslip_monthly_summary AS
            {self._select()}
            {self._from()}
            {self._where()}
            {self._group_by()}
        """)


