from odoo import _, api, fields, models, tools
import logging
from lxml import etree
from datetime import date
from email.utils import parseaddr, formataddr
import base64, re

try:
    import unicodedata
except Exception:
    unicodedata = None

_logger = logging.getLogger(__name__)


class HrPayslipPlanillaUnica(models.Model):
    _name = 'hr.payslip.planilla.unica'
    _description = 'Reporte de planilla unica'
    _auto = False  # es una vista SQL, no tabla física
    _check_company_auto = True  # respeta reglas multi-compañía automáticamente

    # Catálogo de meses para filtros
    PERIOD_MONTHS = [
        ('01', 'enero'), ('02', 'febrero'), ('03', 'marzo'), ('04', 'abril'),
        ('05', 'mayo'), ('06', 'junio'), ('07', 'julio'), ('08', 'agosto'),
        ('09', 'septiembre'), ('10', 'octubre'), ('11', 'noviembre'), ('12', 'diciembre'),
    ]

    @api.model
    def year_selection(self):
        y = date.today().year
        return [(str(v), str(v)) for v in range(y - 5, y + 2)]

    # campos base
    company_id = fields.Many2one('res.company', string='Empresa', readonly=True, index=True)
    period_year = fields.Selection(selection=year_selection, string='Año', readonly=True, index=True)
    period_month = fields.Selection(selection=PERIOD_MONTHS, string='Mes', readonly=True, index=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado', readonly=True, index=True)
    department_id = fields.Many2one('hr.department', string='Departamento', readonly=True)

    nit_empresa = fields.Char(related='company_id.vat', string='Nit empresa', readonly=True, index=True)
    numero_isss_empresa = fields.Char(related='company_id.isss_patronal', string='ISSS patronal', readonly=True,
                                      index=True)

    periodo_planilla = fields.Char('periodo_planilla', readonly=True)

    num_documento = fields.Char('Nùmero documento', readonly=True)
    tipo_documento = fields.Char('Tipo documento', readonly=True)
    numero_isss_empleado = fields.Char('Nùmero ISSS empleado ', readonly=True)
    institucion_previsional = fields.Char('Institucion Previsional', readonly=True)
    afp_id = fields.Char(string='AFP', readonly=True)

    primer_nombre = fields.Char(related='employee_id.primer_nombre', readonly=True)
    segundo_nombre = fields.Char(related='employee_id.segundo_nombre', readonly=True)
    primer_apellido = fields.Char(related='employee_id.primer_apellido', readonly=True)
    segundo_apellido = fields.Char(related='employee_id.segundo_apellido', readonly=True)

    total_worked_days = fields.Float('Días laborados', readonly=True)
    total_worked_hours = fields.Float('Horas laboradas', readonly=True)

    salario_pagar = fields.Float('Salario a pagar', readonly=True)
    comisiones = fields.Float('Comisiones', readonly=True)
    total_comisiones = fields.Float('Total comisiones', readonly=True)
    total_overtime = fields.Float('Horas extras', readonly=True)

    viaticos = fields.Float('Viáticos ordinarios', readonly=True)
    total_viaticos_a_pagar = fields.Float('Total viáticos', readonly=True)
    vacaciones = fields.Float('Vacaciones', readonly=True)

    total_devengado = fields.Float('Total devengado', readonly=True)

    isss = fields.Float('ISSS', readonly=True)
    isr = fields.Float('ISR', readonly=True)
    afp = fields.Float('AFP Crecer', readonly=True)
    afp_confia = fields.Float('AFP Confia', readonly=True)
    afp_ipsfa = fields.Float('IPSFA', readonly=True)
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
                SELECT wd.payslip_id,
                       COALESCE(SUM(wd.number_of_days), 0)  AS worked_days,
                       COALESCE(SUM(wd.number_of_hours), 0) AS worked_hours
                FROM hr_payslip_worked_days wd
                GROUP BY wd.payslip_id
            ),
            pl AS (
                SELECT l.slip_id,
                       COALESCE(SUM(CASE WHEN l.code='COMISION'   THEN l.amount ELSE 0 END),0) AS comisiones,
                       COALESCE(SUM(CASE WHEN l.code='OVERTIME'   THEN l.amount ELSE 0 END),0) AS overtime,
                       COALESCE(SUM(CASE WHEN l.code='VIATICO'    THEN l.amount ELSE 0 END),0) AS viaticos,
                       COALESCE(SUM(CASE WHEN l.code='VACACIONES' THEN l.amount ELSE 0 END),0) AS vacaciones,
                       COALESCE(SUM(CASE WHEN l.code='DESC_FALTA_SEPTIMO' THEN l.amount ELSE 0 END),0) AS desc_falta
                FROM hr_payslip_line l
                GROUP BY l.slip_id
            )
            SELECT
                MIN(ps.id)                         AS id,
                ps.company_id                      AS company_id,
                ps.employee_id                     AS employee_id,
                emp.department_id                  AS department_id,

                -- periodos como texto (para selections del modelo)
                ps.period_year::text               AS period_year,
                LPAD(ps.period_month::text, 2, '0') AS period_month,

                -- concatenación MM-YYYY calculada en SQL
                (LPAD(ps.period_month::text, 2, '0') || ps.period_year::text) AS periodo_planilla,

                -- DUI o Pasaporte -> num_documento
                MAX(
                  CASE
                    WHEN COALESCE(NULLIF(emp.identification_id::text, ''), '') <> '' THEN
                         regexp_replace(emp.identification_id::text, '\D', '', 'g')   -- solo dígitos
                    WHEN COALESCE(NULLIF(emp.passport_id::text, ''), '') <> '' THEN
                         UPPER(translate(emp.passport_id::text, ' ', ''))             -- quita espacios
                    ELSE NULL
                  END
                ) AS num_documento,
                
                -- Tipo de documento: 01 = DUI, 02 = Pasaporte (prioriza DUI si hay ambos)
                MAX(
                  CASE
                    WHEN COALESCE(NULLIF(emp.identification_id::text, ''), '') <> '' THEN '01'
                    WHEN COALESCE(NULLIF(emp.passport_id::text, ''), '') <> '' THEN '02'
                    ELSE NULL  -- o '00' si quieres marcar “sin documento”
                  END
                ) AS tipo_documento,

                -- numero ISSS
                MAX(emp.ssnid)::text AS numero_isss_empleado,
                
                -- institucion previsional
                MAX(c.afp_id) AS afp_id,


                -- necesarios porque existen en el modelo
                COALESCE(SUM(wd.worked_days), 0)   AS total_worked_days,
                COALESCE(SUM(wd.worked_hours), 0)  AS total_worked_hours,

                -- métricas solicitadas
                SUM(COALESCE(ps.basic_wage,0) - ABS(COALESCE(pl.desc_falta,0)))      AS salario_pagar,
                SUM(COALESCE(pl.comisiones,0))                                        AS comisiones,
                SUM(COALESCE(pl.viaticos,0))                                          AS viaticos,
                SUM(COALESCE(pl.vacaciones,0))                                        AS vacaciones,
                SUM(COALESCE(pl.overtime,0))                                          AS total_overtime
        """

    @api.model
    def _from(self):
        return """
            FROM hr_payslip ps
            JOIN hr_employee emp ON emp.id = ps.employee_id
            LEFT JOIN wd ON wd.payslip_id = ps.id
            LEFT JOIN pl ON pl.slip_id = ps.id
            LEFT JOIN hr_contract c ON c.id = ps.contract_id
            JOIN hr_payroll_structure s ON s.id = ps.struct_id
        """

    @api.model
    def _where(self):
        return """
            WHERE s.code IN ('INCOE', 'PLAN_VAC')
              AND ps.struct_id IS NOT NULL
        """

    @api.model
    def _group_by(self):
        return """
            GROUP BY
                ps.company_id,
                ps.employee_id,
                emp.department_id,
                ps.period_year,
                ps.period_month
        """

    def init(self):
        tools.drop_view_if_exists(self._cr, 'hr_payslip_planilla_unica')
        self._cr.execute(f"""
            CREATE OR REPLACE VIEW hr_payslip_planilla_unica AS
            {self._select()}
            {self._from()}
            {self._where()}
            {self._group_by()}
        """)

