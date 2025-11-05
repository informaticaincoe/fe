# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
import logging

_logger = logging.getLogger(__name__)
import base64

try:
    from odoo.addons.common_utils.utils import constants
    from odoo.addons.common_utils.utils import config_utils

    _logger.info("SIT Modulo constants [invoice_sv-account_move]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None
    config_utils = None


AFP_MAP = {
    getattr(constants, 'AFP_CONFIA', 'CONFIA'): 'COF',
    getattr(constants, 'AFP_CRECER', 'CRECER'): 'MAX',
    getattr(constants, 'AFP_IPSFA', 'IPSFA'): '',  # se deja vacío para IPSFA
}


class HrPayslipPlanillaUnicaWizard(models.TransientModel):
    _name = 'hr.payslip.planilla.unica.wizard'
    _description = 'Asistente: Planilla Única (ORM)'

    company_id = fields.Many2one('res.company', string='Empresa', default=lambda s: s.env.company, required=True)
    period_year = fields.Selection(
        selection=lambda self: [(str(y), str(y)) for y in range(fields.Date.today().year - 5, fields.Date.today().year + 2)],
        string='Año', required=True
    )

    period_month = fields.Selection(
        selection=[(f'{m:02d}', _(m_name)) for m, m_name in [
            (1, 'enero'), (2, 'febrero'), (3, 'marzo'), (4, 'abril'),
            (5, 'mayo'), (6, 'junio'), (7, 'julio'), (8, 'agosto'),
            (9, 'septiembre'), (10, 'noviembre'.replace('noviembre','octubre')),  # evita traducción forzada
            (11, 'noviembre'), (12, 'diciembre')
        ]],
        string='Mes', required=True
    )

    estructura_codes = fields.Char(
        string='Códigos de estructura (coma)',
        help="Filtra hr.payslip.struct_id.code. Ej: INCOE,PLAN_VAC",
        default='INCOE,PLAN_VAC'
    )

    numero_anexo = fields.Char(string="Número del anexo",
                               default=lambda s: str(s.env.context.get('numero_anexo') or ''))

    line_ids = fields.One2many('hr.payslip.planilla.unica.line', 'wizard_id', string='Líneas')

    def _struct_domain(self):
        codes = [c.strip() for c in (self.estructura_codes or '').split(',') if c.strip()]
        return [('struct_id.code', 'in', codes)] if codes else []

    def action_compute(self):
        self.ensure_one()
        self.line_ids.unlink()

        # --- 1) Cargar payslips del período/empresa/estructura
        dom = [
            ('company_id', '=', self.company_id.id),
            ('period_year', '=', self.period_year),
            ('period_month', '=', int(self.period_month)),
        ] + self._struct_domain()
        # (opcional: estado 'done' si lo usan)
        # dom.append(('state', '=', 'done'))

        Payslip = self.env['hr.payslip'].sudo()
        slips = Payslip.search(dom)

        if not slips:
            _logger.info("No hay hr.payslip para %s-%s en %s", self.period_month, self.period_year, self.company_id.display_name)
            return {
                'type': 'ir.actions.act_window',
                'name': _("Planilla Única (sin resultados)"),
                'res_model': 'hr.payslip.planilla.unica.line',
                'view_mode': 'tree',
                'domain': [('wizard_id', '=', self.id)],
                'target': 'current',
            }

        slip_ids = slips.ids

        # Índice clave (company, employee, dept, year, month)
        def _key(ps):
            dept_id = ps.employee_id.department_id.id or False
            return (ps.company_id.id, ps.employee_id.id, dept_id, str(ps.period_year), f"{int(ps.period_month):02d}")

        # --- 2) Agregados base por payslip (basic_wage)
        # Sumamos basic_wage por clave y guardamos referencias (employee/contract)
        bucket = {}
        for ps in slips:
            k = _key(ps)
            rec = bucket.setdefault(k, {
                'company_id': ps.company_id.id,
                'employee_id': ps.employee_id.id,
                'department_id': ps.employee_id.department_id.id or False,
                'period_year': str(ps.period_year),
                'period_month': f"{int(ps.period_month):02d}",

                'basic_wage_sum': 0.0,
                'desc_falta_sum': 0.0,
                'comisiones_sum': 0.0,
                'bono_sum': 0.0,
                'overtime_sum': 0.0,
                'viaticos_sum': 0.0,
                'vacaciones_sum': 0.0,

                'worked_days_sum': 0.0,
                'worked_hours_sum': 0.0,

                'num_documento': '',
                'tipo_documento': '',
                'numero_isss_empleado': '',
                'afp_id': '',
            })
            # basic_wage puede estar en contrato o en payslip; usamos el de payslip para reproducir tu SQL
            rec['basic_wage_sum'] += (ps.basic_wage or 0.0)

        # --- 3) Días/horas trabajadas (hr.payslip.worked_days)
        WD = self.env['hr.payslip.worked_days'].sudo()
        for wd in WD.search([('payslip_id', 'in', slip_ids)]):
            ps = wd.payslip_id
            k = _key(ps)
            if k in bucket:
                bucket[k]['worked_days_sum'] += (wd.number_of_days or 0.0)
                bucket[k]['worked_hours_sum'] += (wd.number_of_hours or 0.0)

        # --- 4) Líneas de nómina por código (hr.payslip.line)
        codes = ['COMISION', 'OVERTIME', 'VIATICO', 'VACACIONES', 'BONO', 'DESC_FALTA_SEPTIMO']
        PL = self.env['hr.payslip.line'].sudo()
        for line in PL.search([('slip_id', 'in', slip_ids), ('code', 'in', codes)]):
            ps = line.slip_id
            k = _key(ps)
            if k not in bucket:
                continue
            amt = (line.amount or 0.0)
            c = line.code
            if c == 'COMISION':
                bucket[k]['comisiones_sum'] += amt
            elif c == 'OVERTIME':
                bucket[k]['overtime_sum'] += amt
            elif c == 'VIATICO':
                bucket[k]['viaticos_sum'] += amt
            elif c == 'VACACIONES':
                bucket[k]['vacaciones_sum'] += amt
            elif c == 'BONO':
                bucket[k]['bono_sum'] += amt
            elif c == 'DESC_FALTA_SEPTIMO':
                bucket[k]['desc_falta_sum'] += amt

        # --- 5) Datos de identificación / ISSS / AFP (por empleado/contrato del período)
        for ps in slips:
            k = _key(ps)
            if k not in bucket:
                continue
            emp = ps.employee_id
            num_doc = ''
            tipo_doc = ''
            if emp.identification_id:
                # DUI prioriza; deja solo dígitos
                num_doc = ''.join([d for d in emp.identification_id if d.isdigit()])
                tipo_doc = '01'
            elif emp.passport_id:
                num_doc = (emp.passport_id or '').replace(' ', '').upper()
                tipo_doc = '02'

            bucket[k]['num_documento'] = num_doc
            bucket[k]['tipo_documento'] = tipo_doc
            bucket[k]['numero_isss_empleado'] = (emp.ssnid or '')

            afp_raw = (ps.contract_id.afp_id or '') if ps.contract_id else (emp.contract_id.afp_id or '')
            bucket[k]['afp_id'] = AFP_MAP.get(afp_raw, '')

        # --- 6) Crear líneas
        Line = self.env['hr.payslip.planilla.unica.line'].sudo()
        to_create = []
        for k, v in bucket.items():
            salario_pagar = (v['basic_wage_sum'] or 0.0) - abs(v['desc_falta_sum'] or 0.0)
            total_comisiones = (v['comisiones_sum'] or 0.0)  # si necesitas campo separado

            to_create.append({
                'wizard_id': self.id,
                'company_id': v['company_id'],
                'employee_id': v['employee_id'],
                'department_id': v['department_id'],
                'period_year': v['period_year'],
                'period_month': v['period_month'],
                'periodo_planilla': f"{v['period_month']}{v['period_year']}",

                'num_documento': v['num_documento'],
                'tipo_documento': v['tipo_documento'],
                'numero_isss_empleado': v['numero_isss_empleado'],
                'afp_id': v['afp_id'],

                'total_worked_days': v['worked_days_sum'],
                'total_worked_hours': v['worked_hours_sum'],

                'salario_pagar': salario_pagar,
                'comisiones': v['comisiones_sum'],
                'total_comisiones': total_comisiones,
                'total_overtime': v['overtime_sum'],
                'viaticos': v['viaticos_sum'],
                'vacaciones': v['vacaciones_sum'],
                'pago_adicional': (v['comisiones_sum'] or 0.0) + (v['bono_sum'] or 0.0),

                'numero_anexo': self.numero_anexo or '',
            })

        if to_create:
            Line.create(to_create)

        return {
            'type': 'ir.actions.act_window',
            'name': _("Planilla Única"),
            'res_model': 'hr.payslip.planilla.unica.line',
            'view_mode': 'tree,form',
            'domain': [('wizard_id', '=', self.id)],
            'target': 'current',
            'context': dict(self.env.context, default_wizard_id=self.id),
        }

    def action_export_csv(self):
        self.ensure_one()
        recs = self.line_ids
        if not recs:
            return
        csv_bytes = self.env['anexo.csv.utils'].generate_csv(
            recs, numero_anexo=self.numero_anexo or "", view_id=None, include_header=False
        )
        att = self.env["ir.attachment"].create({
            "name": f"planilla_unica_{self.period_month}{self.period_year}.csv",
            "type": "binary",
            "datas": base64.b64encode(csv_bytes),
            "res_model": self._name,
            "res_id": self.id,
            "public": True,
        })
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{att.id}?download=true",
            "target": "self",
        }
