# -*- coding: utf-8 -*-
from odoo import api, fields, models
from collections import defaultdict
import logging
_logger = logging.getLogger(__name__)

class HrPayslipMonthSummary(models.Model):
    _name = 'hr.payslip.month.summary'
    _description = 'Resumen mensual por empleado (Q1+Q2)'
    _rec_name = 'display_name'
    _order = 'period_year desc, period_month desc, employee_name asc'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # opcional para notas

    # Claves de agrupación
    employee_id = fields.Many2one('hr.employee', string='Empleado', index=True, required=True, readonly=True)
    employee_name = fields.Char(related='employee_id.name', string='Nombre', store=False, readonly=True)
    department_id = fields.Many2one('hr.department', string='Departamento', readonly=True)
    department_name = fields.Char(related='department_id.complete_name', string='Departamento', store=False, readonly=True)

    period_year = fields.Char(string='Año', required=True, index=True, readonly=True)
    period_month = fields.Selection(selection=lambda self: self.env['hr.payslip'].PERIOD_MONTHS,
                                    string='Mes', required=True, index=True, readonly=True)

    # Referencias a las nóminas del mes
    payslip_q1_id = fields.Many2one('hr.payslip', string='Slip Q1', readonly=True)
    payslip_q2_id = fields.Many2one('hr.payslip', string='Slip Q2', readonly=True)

    # Totales mensuales (Q1+Q2) → replican tu lógica de cálculo de lista
    total_worked_days = fields.Float(string='Días laborados', readonly=True)
    total_worked_hours = fields.Float(string='Horas laboradas', readonly=True)

    salario_pagar = fields.Float(string='Salario a pagar', readonly=True)
    comisiones = fields.Float(string='Comisiones', readonly=True)
    total_overtime = fields.Float(string='Horas extras', readonly=True)
    viaticos = fields.Float(string='Viáticos ordinarios', readonly=True)
    bonos = fields.Float(string='Bonos', readonly=True)
    total_viaticos_a_pagar = fields.Float(string='Total viáticos', readonly=True)
    total_devengado = fields.Float(string='Total devengado', readonly=True)

    isss = fields.Float(string='ISSS', readonly=True)
    isr = fields.Float(string='ISR', readonly=True)
    afp = fields.Float(string='AFP Crecer', readonly=True)
    afp_confia = fields.Float(string='AFP Confia', readonly=True)
    afp_IPSFA = fields.Float(string='IPSFA', readonly=True)
    otros = fields.Float(string='Otros', readonly=True)
    bancos = fields.Float(string='Bancos', readonly=True)
    venta_empleados = fields.Float(string='Venta a empleados', readonly=True)
    prestamos_incoe = fields.Float(string='Préstamos INCOE', readonly=True)
    fsv = fields.Float(string='Fondo social vivienda', readonly=True)

    total_descuentos = fields.Float(string='Total descuentos', readonly=True)
    sueldo_liquido = fields.Float(string='Líquido a recibir', readonly=True)

    display_name = fields.Char(string='Resumen', compute='_compute_display_name', store=False)

    @api.depends('employee_name', 'period_year', 'period_month')
    def _compute_display_name(self):
        for rec in self:
            mes = dict(self.env['hr.payslip'].PERIOD_MONTHS).get(rec.period_month or '', rec.period_month or '')
            rec.display_name = f"{rec.employee_name or ''} - {mes} {rec.period_year or ''}"

    # ---------------------- Generador del resumen ----------------------
    @api.model
    def action_generate_month(self, year=None, month=None, struct_code='INCOE'):
        """
        Genera/actualiza los resúmenes del mes/año indicado (por estructura opcional).
        - year: '2025'
        - month: '08'
        - struct_code: código de tu estructura (por defecto 'INCOE').
        """
        if not year or not month:
            today = fields.Date.context_today(self)
            year = str(today.year)
            month = f"{today.month:02d}"

        # Traer nóminas del periodo (ambas quincenas) de la estructura indicada
        domain = [
            ('period_year', '=', year),
            ('period_month', '=', month),
        ]
        if struct_code:
            domain += [('struct_id.code', '=', struct_code)]

        payslips = self.env['hr.payslip'].search(domain)

        # Agrupar por empleado
        # Agrupar por empleado (usar IDs, no recordsets)
        grouped = defaultdict(lambda: {'q1': None, 'q2': None, 'dept_id': False})
        for slip in payslips:
            emp_id = slip.employee_id.id
            if slip.period_quincena == '1':
                grouped[emp_id]['q1'] = slip
            elif slip.period_quincena == '2':
                grouped[emp_id]['q2'] = slip
            if not grouped[emp_id]['dept_id']:
                grouped[emp_id]['dept_id'] = slip.employee_id.department_id.id or False

        # Borrar previos del mismo periodo para no duplicar
        to_delete = self.search([('period_year', '=', year), ('period_month', '=', month)])
        if to_delete:
            to_delete.unlink()

        records_vals = []
        Employee = self.env['hr.employee']
        for emp_id, data in grouped.items():
            employee = Employee.browse(emp_id)
            q1 = data['q1']
            q2 = data['q2']

            # ---- tus helpers tal cual ----
            def _calc_salario_pagar(slip):
                if not slip:
                    return 0.0
                descuento_falta = sum(slip.line_ids.filtered(lambda l: l.code == 'DESC_FALTA_SEPTIMO').mapped('amount'))
                salario_base = slip.basic_wage or 0.0
                return round(salario_base - abs(descuento_falta), 2)

            def _sum_line_amount(slip, code):
                return abs(sum(slip.line_ids.filtered(lambda l: l.code == code).mapped('amount'))) if slip else 0.0

            def _worked_days(slip):
                if not slip:
                    return 0.0
                lines = slip.worked_days_line_ids.filtered(lambda l: l.name in ('Asistencia', 'Vacaciones'))
                return sum(lines.mapped('number_of_days'))

            def _worked_hours(slip):
                if not slip:
                    return 0.0
                lines = slip.worked_days_line_ids.filtered(lambda l: l.name in ('Asistencia', 'Vacaciones'))
                return sum(lines.mapped('number_of_hours'))

            # ---- totales por slip (igual que tu código) ----
            salario_pagar_q1 = _calc_salario_pagar(q1)
            salario_pagar_q2 = _calc_salario_pagar(q2)

            _logger.warning("SALARIO TOTAL %s", salario_pagar_q1)
            bonos_q1 = _sum_line_amount(q1, 'BONO')
            bonos_q2 = _sum_line_amount(q2, 'BONO')
            comisiones_q1 = _sum_line_amount(q1, 'COMISION')
            comisiones_q2 = _sum_line_amount(q2, 'COMISION')
            overtime_q1 = _sum_line_amount(q1, 'OVERTIME')
            overtime_q2 = _sum_line_amount(q2, 'OVERTIME')
            viaticos_q1 = _sum_line_amount(q1, 'VIATICO') + bonos_q1
            viaticos_q2 = _sum_line_amount(q2, 'VIATICO') + bonos_q2

            total_viaticos_q1 = viaticos_q1 + overtime_q1
            total_viaticos_q2 = viaticos_q2 + overtime_q2

            total_dev_q1 = total_viaticos_q1 + salario_pagar_q1 + comisiones_q1
            total_dev_q2 = total_viaticos_q2 + salario_pagar_q2 + comisiones_q2

            isss_q1 = _sum_line_amount(q1, 'ISSS');
            isss_q2 = _sum_line_amount(q2, 'ISSS')
            isr_q1 = _sum_line_amount(q1, 'RENTA') or _sum_line_amount(q1, 'DEV_RENTA')
            isr_q2 = _sum_line_amount(q2, 'RENTA') or _sum_line_amount(q2, 'DEV_RENTA')
            afp_q1 = _sum_line_amount(q1, 'AFP');
            afp_q2 = _sum_line_amount(q2, 'AFP')
            afp_conf_q1 = _sum_line_amount(q1, 'AFP_CONF');
            afp_conf_q2 = _sum_line_amount(q2, 'AFP_CONF')
            ipsfa_q1 = _sum_line_amount(q1, 'IPSFA');
            ipsfa_q2 = _sum_line_amount(q2, 'IPSFA')
            otros_q1 = _sum_line_amount(q1, 'OTROS');
            otros_q2 = _sum_line_amount(q2, 'OTROS')
            bancos_q1 = _sum_line_amount(q1, 'BANCO');
            bancos_q2 = _sum_line_amount(q2, 'BANCO')
            venta_emp_q1 = _sum_line_amount(q1, 'VENTA_EMPLEADOS');
            venta_emp_q2 = _sum_line_amount(q2, 'VENTA_EMPLEADOS')
            prestamos_q1 = _sum_line_amount(q1, 'PRESTAMOS');
            prestamos_q2 = _sum_line_amount(q2, 'PRESTAMOS')
            fsv_q1 = _sum_line_amount(q1, 'FSV');
            fsv_q2 = _sum_line_amount(q2, 'FSV')

            total_desc_q1 = isss_q1 + isr_q1 + afp_q1 + otros_q1 + bancos_q1 + fsv_q1 + prestamos_q1 + venta_emp_q1
            total_desc_q2 = isss_q2 + isr_q2 + afp_q2 + otros_q2 + bancos_q2 + fsv_q2 + prestamos_q2 + venta_emp_q2

            sueldo_liq_q1 = total_dev_q1 - total_desc_q1
            sueldo_liq_q2 = total_dev_q2 - total_desc_q2

            records_vals.append({
                'employee_id': emp_id,
                'department_id': data['dept_id'],
                'period_year': year,
                'period_month': month,
                'payslip_q1_id': q1.id if q1 else False,
                'payslip_q2_id': q2.id if q2 else False,

                'total_worked_days': _worked_days(q1) + _worked_days(q2),
                'total_worked_hours': _worked_hours(q1) + _worked_hours(q2),

                'salario_pagar': salario_pagar_q1 + salario_pagar_q2,
                'comisiones': comisiones_q1 + comisiones_q2,
                'total_overtime': overtime_q1 + overtime_q2,
                'viaticos': viaticos_q1 + viaticos_q2,
                'bonos': bonos_q1 + bonos_q2,
                'total_viaticos_a_pagar': total_viaticos_q1 + total_viaticos_q2,
                'total_devengado': total_dev_q1 + total_dev_q2,

                'isss': isss_q1 + isss_q2,
                'isr': isr_q1 + isr_q2,
                'afp': afp_q1 + afp_q2,
                'afp_confia': afp_conf_q1 + afp_conf_q2,
                'afp_IPSFA': ipsfa_q1 + ipsfa_q2,
                'otros': otros_q1 + otros_q2,
                'bancos': bancos_q1 + bancos_q2,
                'venta_empleados': venta_emp_q1 + venta_emp_q2,
                'prestamos_incoe': prestamos_q1 + prestamos_q2,
                'fsv': fsv_q1 + fsv_q2,

                'total_descuentos': total_desc_q1 + total_desc_q2,
                'sueldo_liquido': sueldo_liq_q1 + sueldo_liq_q2,
            })

        if records_vals:
            self.create(records_vals)

        # Abrir la vista lista del resumen generado
        action = self.env.ref('rrhh_base.action_hr_payslip_month_summary').sudo().read()[0]
        action['context'] = {'search_default_period': 1}
        action['domain'] = [('period_year', '=', year), ('period_month', '=', month)]
        return action

