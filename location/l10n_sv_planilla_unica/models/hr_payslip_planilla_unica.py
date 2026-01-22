# -*- coding: utf-8 -*-
from calendar import monthrange
from datetime import date, datetime, timedelta

from odoo import api, fields, models, _, tools, SUPERUSER_ID
import logging
import re

_logger = logging.getLogger(__name__)
try:
    from odoo.addons.common_utils.utils import constants
    from odoo.addons.common_utils.utils import config_utils

    _logger.info("SIT Modulo constants [invoice_sv-account_move]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None
    config_utils = None
# ---------------------------------------------------------------------------
# Helpers puros (fuera de clase)
# ---------------------------------------------------------------------------
def normalize_doc(num):
    """
    Normaliza documento de identificación (DUI/pasaporte/carné):
    - Quita espacios/símbolos
    - Mantiene A-Z0-9 en upper-case
    """
    s = (num or '').strip()
    return re.sub(r'[^A-Za-z0-9]+', '', s).upper()


def _norm_codes(val, fallback_list):
    """
    Normaliza códigos:
      - None -> fallback_list
      - 'str' -> ['STR']
      - [a,b] -> ['A','B']
    Devuelve lista en upper().
    """
    try:
        if isinstance(val, (list, tuple, set)):
            out = [str(x).upper() for x in val if x]
            return out or [x.upper() for x in fallback_list]
        if val:
            return [str(val).upper()]
    except Exception:
        pass
    return [x.upper() for x in fallback_list]


# ---------------------------------------------------------------------------
# Modelo Transient
# ---------------------------------------------------------------------------
class HrPayslipPlanillaUnica(models.TransientModel):
    _name = 'hr.payslip.planilla.unica'
    _description = 'Reporte de planilla única'
    _check_company_auto = True

    # -----------------------------------------------------------------------
    # Constantes de clase
    # -----------------------------------------------------------------------
    PERIOD_MONTHS = [
        ('01', 'enero'), ('02', 'febrero'), ('03', 'marzo'), ('04', 'abril'),
        ('05', 'mayo'), ('06', 'junio'), ('07', 'julio'), ('08', 'agosto'),
        ('09', 'septiembre'), ('10', 'octubre'), ('11', 'noviembre'), ('12', 'diciembre'),
    ]

    # -----------------------------------------------------------------------
    # Selecciones dinámicas
    # -----------------------------------------------------------------------
    # @api.model
    # def year_selection(self):
    #     """Rango de años (y-5 .. y+1)."""
    #     y = date.today().year
    #     return [(str(v), str(v)) for v in range(y - 5, y + 2)]

    @api.model
    def year_selection(self):
        """
        Años dinámicos tomados de hr.payslip vía ORM (read_group), respetando
        compañías permitidas. Si no hay datos, cae al rango y-5..y+1.
        """
        # compañías permitidas (multicompañía)
        allowed = self.env.context.get('allowed_company_ids') or [self.env.company.id]
        if isinstance(allowed, int):
            allowed = [allowed]

        Slip = self.env['hr.payslip']
        Planilla = self.env['hr.payslip.planilla.unica']

        domain_slip = [('company_id', 'in', allowed)]
        years_from_slips = set()

        # 1) Años desde date_from
        rows_from = Slip.read_group(
            domain=domain_slip,
            fields=['id'],
            groupby=['date_from:year'],
            lazy=False,
        )
        for r in rows_from:
            y = r.get('date_from:year')
            if y:
                years_from_slips.add(str(int(y)))

        # 2) Años desde date_to (por robustez)
        rows_to = Slip.read_group(
            domain=domain_slip,
            fields=['id'],
            groupby=['date_to:year'],
            lazy=False,
        )
        for r in rows_to:
            y = r.get('date_to:year')
            if y:
                years_from_slips.add(str(int(y)))

        # 3) Años que existen hoy en la tabla temporal (period_year)
        years_tmp = set()
        rows_tmp = Planilla.read_group(
            domain=[('company_id', 'in', allowed)],
            fields=['id'],
            groupby=['period_year'],
            lazy=False,
        )
        for r in rows_tmp:
            y = r.get('period_year')
            if y:
                years_tmp.add(str(y))

        # 4) Detectar años "basura" en la temporal (p.ej. 2026 sin nóminas)
        orphan_years = years_tmp - years_from_slips
        if orphan_years:
            # Limpia esos registros para que no vuelvan a aparecer
            Planilla.search([
                ('company_id', 'in', allowed),
                ('period_year', 'in', list(orphan_years)),
            ]).unlink()
            # Y los sacamos del set
            years_tmp -= orphan_years

        # 5) Unión final: años válidos de slips + lo que quede en la temporal
        years = years_from_slips | years_tmp

        # 6) Fallback si está vacío: ventana alrededor del año actual
        if not years:
            today = fields.Date.context_today(self)
            base = today.year
            years = {str(v) for v in range(base - 5, base + 2)}

        # Devolver selection (value, label) ordenado desc
        return [(y, y) for y in sorted(years, reverse=True)]

    # -----------------------------------------------------------------------
    # Campos base / filtros
    # -----------------------------------------------------------------------
    company_id = fields.Many2one('res.company', string='Empresa', index=True)
    period_year = fields.Selection(selection=year_selection, string='Año', index=True)
    period_month = fields.Selection(selection=PERIOD_MONTHS, string='Mes', index=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado', index=True)
    contract_id = fields.Many2one('hr.contract', string='Nómina Origen', index=True)

    # -----------------------------------------------------------------------
    # Datos de empresa
    # -----------------------------------------------------------------------
    nit_empresa = fields.Char(related='company_id.vat', string='NIT empresa')
    numero_isss_empresa = fields.Char(related='company_id.isss_patronal', string='ISSS patronal')
    correlativo_centro_trabajo = fields.Char(
        string='Correlativo centro de trabajo',
        compute='_compute_correlativo_centro_trabajo',
        readonly=True,
    )

    # -----------------------------------------------------------------------
    # Datos del empleado (related/compute, no persistentes)
    # -----------------------------------------------------------------------
    primer_nombre = fields.Char(string="Primer nombre", related='employee_id.primer_nombre', readonly=True, store=False)
    segundo_nombre = fields.Char(string="Segundo nombre", related='employee_id.segundo_nombre', readonly=True, store=False)
    primer_apellido = fields.Char(string="Primer apellido", related='employee_id.primer_apellido', readonly=True, store=False)
    segundo_apellido = fields.Char(string="Segundo apellido", related='employee_id.segundo_apellido', readonly=True, store=False)
    apellido_casada = fields.Char(string="Apellido de casada", related='employee_id.apellido_casada', readonly=True, store=False)

    tipo_documento_empleado = fields.Char(
        string="Tipo de documento",
        compute='_compute_tipo_documento_empleado',
        readonly=True, store=False,
    )
    num_documento_empleado = fields.Char(
        string="Número de documento del trabajador",
        compute="_compute_num_documento_empleado",
        readonly=True, store=False,
    )
    num_isss = fields.Char(string="Número afiliación al ISSS", related='employee_id.ssnid', readonly=True, store=False)

    # -----------------------------------------------------------------------
    # AFP (desde contrato activo)
    # -----------------------------------------------------------------------
    afp_id = fields.Char(string='AFP', compute='_compute_afp_id', store=False, readonly=True)
    afp_tipo = fields.Char(string='Tipo AFP', compute='_compute_tipo_afp', store=False, readonly=True)

    # -----------------------------------------------------------------------
    # Totales planilla / métricas
    # -----------------------------------------------------------------------
    periodo_planilla = fields.Char('Periodo planilla', readonly=True)

    total_worked_days = fields.Float('Días laborados', readonly=True)
    total_worked_hours = fields.Float('Horas laboradas', readonly=True)  # total (no promedio)

    quincena1_gross = fields.Float('Q1 gross', readonly=True)
    quincena2_gross = fields.Float('Q2 gross', readonly=True)
    salario_pagar = fields.Float('Salario a pagar', readonly=True)

    pago_adicional = fields.Float('Pago adicional', readonly=True)
    vacaciones = fields.Float('Vacaciones', readonly=True)
    vacaciones_days = fields.Float('Días de vacaciones', readonly=True)
    vacaciones_hours = fields.Float('Horas de vacaciones', readonly=True)
    has_incapacidad = fields.Boolean('Tiene incapacidad', readonly=True)

    # -----------------------------------------------------------------------
    # Códigos observación
    # -----------------------------------------------------------------------
    codigo_observacion_1 = fields.Char(
        string='Código observación 1', compute='_compute_codigos_observacion', store=False, readonly=True)
    codigo_observacion_2 = fields.Char(
        string='Código observación 2', compute='_compute_codigos_observacion', store=False, readonly=True)

    # -----------------------------------------------------------------------
    # Cómputo de contrato
    # -----------------------------------------------------------------------
    def _get_active_contract(self, employee, period_year, period_month):
        """
        Retorna el contrato ACTIVO del empleado dentro del mes (más reciente).
        """
        # ... cálculo de first_day y last_day del período ...
        Contract = self.env['hr.contract']
        return Contract.search([
            ('employee_id', '=', employee.id),
        ], order='date_start desc', limit=1)

    # -----------------------------------------------------------------------
    # Cómputos de identificación
    # -----------------------------------------------------------------------
    @api.depends('employee_id', 'period_year', 'period_month')
    def _compute_tipo_documento_empleado(self):
        """Determina tipo de documento: 01=DUI, 02=Pasaporte."""
        for rec in self:
            emp = rec.employee_id
            tipo = ''
            if emp:
                if (emp.identification_id or '').strip():
                    tipo = '01'
                elif (emp.passport_id or '').strip():
                    tipo = '02'
            rec.tipo_documento_empleado = tipo

    @api.depends('employee_id', 'period_year', 'period_month', 'tipo_documento_empleado')
    def _compute_num_documento_empleado(self):
        """Normaliza número de documento según tipo."""
        for rec in self:
            emp = rec.employee_id
            if not emp:
                rec.num_documento_empleado = ''
                continue
            if rec.tipo_documento_empleado == '02':
                rec.num_documento_empleado = (emp.passport_id or '').strip()
            else:
                rec.num_documento_empleado = normalize_doc(emp.identification_id)

    # -----------------------------------------------------------------------
    # Correlativo centro de trabajo normalizado 3 digitos
    # -----------------------------------------------------------------------
    @api.depends('company_id', 'company_id.correlativo_centro_trabajo')
    def _compute_correlativo_centro_trabajo(self):
        for rec in self:
            raw = rec.company_id.correlativo_centro_trabajo or ''
            raw = str(raw).strip()

            if not raw:
                rec.correlativo_centro_trabajo = ''
                continue

            # Si es numérico -> pad a 3 dígitos
            try:
                rec.correlativo_centro_trabajo = str(int(raw)).zfill(3)
            except ValueError:
                # Si por alguna razón no es numérico, se devuelve tal cual (o recortar, como prefieras)
                rec.correlativo_centro_trabajo = raw[:3]

    # -----------------------------------------------------------------------
    # AFP
    # -----------------------------------------------------------------------
    @api.depends('employee_id', 'period_year', 'period_month')
    def _compute_afp_id(self):
        """Obtiene nombre/código AFP desde contrato activo (afp_id o afp Char)."""
        for rec in self:
            afp_txt = ''
            try:
                if rec.employee_id and rec.period_year and rec.period_month:
                    c = self._get_active_contract(rec.employee_id, rec.period_year, rec.period_month)
                    if c:
                        if hasattr(c, 'afp_id') and getattr(c, 'afp_id') is not None:
                            v = c.afp_id
                            if hasattr(v, 'id'):
                                name = getattr(v, 'name', '') or ''
                                code = getattr(v, 'code', '') or ''
                                afp_txt = (name or code or '').strip()
                            else:
                                afp_txt = str(v).strip()
                        elif hasattr(c, 'afp') and c.afp:
                            afp_txt = str(c.afp).strip()
            except Exception:
                _logger.exception("_compute_afp_id: error obteniendo AFP emp=%s",
                                  rec.employee_id.id if rec.employee_id else None)
            rec.afp_id = afp_txt

    @api.depends('afp_id')
    def _compute_tipo_afp(self):
        """
        Mapea AFP textual a código:
          - CRECER/MAX -> 'MAX'
          - CONFIA     -> 'COF'
          - IPSFA      -> 'IPSFA'
          - otro/vacío -> ''
        """
        for rec in self:
            val = (rec.afp_id or '').strip().lower()
            crec = getattr(constants, 'AFP_CRECER', 'crecer').lower() if constants else 'crecer'
            conf = getattr(constants, 'AFP_CONFIA', 'confia').lower() if constants else 'confia'
            if val in (crec, 'max'):
                rec.afp_tipo = 'MAX'
            elif val in (conf, 'confía', 'cof'):
                rec.afp_tipo = 'COF'
            elif 'ipsfa' in val:
                rec.afp_tipo = 'IPSFA'
            else:
                rec.afp_tipo = ''

    # -----------------------------------------------------------------------
    # Códigos observación
    # -----------------------------------------------------------------------
    @api.depends('pago_adicional', 'vacaciones_days', 'afp_tipo')
    def _compute_codigos_observacion(self):
        """
        Reglas y prioridad:
          - default                                         '00'
          - pago_adicional > 0                              '02'
          - aprendiz - tipo de contrato == practicas        '03'
          - afp_tipo == 'IPSFA'                             '04'
          - vacaciones_days > 1                             '09'
          - pagos + vacaciones                              '10'
        """
        for rec in self:
            pagos = float(rec.pago_adicional or 0.0)
            vacdias = float(rec.vacaciones_days or 0.0)

            is_ipsfa = (rec.afp_tipo or '').upper() == 'IPSFA'
            has_incap = bool(rec.has_incapacidad)

            has_pagos = pagos > 0.0
            has_vacas = vacdias > 1.0

            fecha_actual = datetime.now()
            mes_actual_numero = fecha_actual.month

            _logger.info("REC %s", rec.employee_id)
            _logger.info("REC %s", rec.contract_id)
            _logger.info("REC %s %s", rec.contract_id.date_start, type(rec.contract_id.date_start))
            _logger.info("REC %s %s", rec.contract_id.date_start, type(rec.contract_id.date_start))

            contract_state = rec.contract_id.state
            contract_start_date = rec.contract_id.date_start

            _logger.info("mes_actual_numero %s", mes_actual_numero)
            _logger.info("contract_start_date %s", contract_start_date)

            codes = []
            ct_code = getattr(getattr(rec.contract_id, 'contract_type_id', False), 'code', '')
            if ct_code == 'Apprenticeship' and '03' not in codes:
                codes.append('03')
            if has_pagos and has_vacas:
                codes.append('10')
            if has_incap and '06' not in codes:
                codes.append('06')
            if is_ipsfa and '13' not in codes:
                codes.append('13')
            if has_pagos and '10' not in codes:
                codes.append('02')
            if has_vacas and '10' not in codes:
                codes.append('09')
            if contract_state in ["close", "cancel"] and '7' not in codes:
                codes.append('07')
            if contract_state in ["open"] and contract_start_date.month == mes_actual_numero and '8' not in codes:
                codes.append('08')
            while len(codes) < 2:
                codes.append('00')

            rec.codigo_observacion_1 = codes[0]
            rec.codigo_observacion_2 = codes[1]

    # -----------------------------------------------------------------------
    # Motor: reconstrucción del dataset
    # -----------------------------------------------------------------------
    @staticmethod
    def _month_bounds(y, m):
        y = int(y);
        m = int(m)
        last = monthrange(y, m)[1]
        return date(y, m, 1), date(y, m, last)

    def rebuild_from_payslips(self, period_year: str, period_month: str, company_id: int = None):
        """
        Reconstruye registros (uno por empleado) para (año, mes, empresa):
          - Q1/Q2 (gross), salario (Q1+Q2)
          - pagos adicionales (bonos+comisiones)
          - vacaciones (monto + días/horas)
          - totales de días y horas trabajadas
        """
        import time
        t0 = time.time()

        # 1) Borrar previos (TransientModel)
        del_dom = [
            ('company_id', '=', company_id),
            ('period_year', '=', str(period_year)),
            ('period_month', '=', period_month),
            ('create_uid', '=', self.env.uid),
        ]
        self.search(del_dom).unlink()

        # 2) Buscar nóminas del mes
        dom_mes = []
        if company_id:
            dom_mes.append(('company_id', '=', company_id))
        start, end = self._month_bounds(period_year, period_month)
        dom_mes = [('company_id', '=', company_id),
                   ('date_from', '>=', start),
                   ('date_to', '<=', end)]

        slips_mes = self.env['hr.payslip'].search(dom_mes)

        # 3) Acumuladores
        q_map = {}               # emp_id -> {'q1': float, 'q2': float}
        days_hours_by_emp = {}   # emp_id -> {'d': float, 'h': float} (totales)
        vac_dias_por_emp = {}    # emp_id -> float
        vac_horas_por_emp = {}   # emp_id -> float
        empleados_con_incap = set()

        # WD codes que representan vacaciones
        vac_wd_defaults = ['VAC', 'VACACIONES', 'VAC_PAY']
        VAC_WD_CODES = {c.upper() for c in getattr(constants, 'WD_CODES_VACACIONES', vac_wd_defaults)}
        INCAP_WD_CODES = {c.upper() for c in getattr(constants, 'WD_CODES_INCAPACIDAD', ['LEAVE110'])}

        # 3.1) Recorrer slips: Q1/Q2 + días/horas + vacaciones(días/horas)
        for ps in slips_mes:
            emp_id = ps.employee_id.id

            # Quincena
            quin_raw = getattr(ps, 'quin1cena', 0) or 0
            try:
                quin = int(str(quin_raw).strip())
            except Exception:
                quin = 0

            # Gross (preferir gross_wage; fallback BASIC)
            try:
                gw = ps.read(['gross_wage'])[0].get('gross_wage') or 0.0
            except Exception:
                lines_basic = self.env['hr.payslip.line'].search([
                    ('slip_id', '=', ps.id),
                    ('category_id.code', '=', 'BASIC')
                ])
                gw = sum(lines_basic.mapped('total') or [0.0])

            # Días/horas totales del slip (todas las lines worked_days)
            d = sum(ps.worked_days_line_ids.mapped('number_of_days') or [0.0])
            h = sum(ps.worked_days_line_ids.mapped('number_of_hours') or [0.0])

            # Vacaciones (días/horas) desde worked_days_line_ids
            for wd in ps.worked_days_line_ids:
                code_wd = (wd.code or wd.work_entry_type_id.code or '').upper()
                if code_wd in VAC_WD_CODES:
                    vac_dias_por_emp[emp_id] = vac_dias_por_emp.get(emp_id, 0.0) + float(wd.number_of_days or 0.0)
                    vac_horas_por_emp[emp_id] = vac_horas_por_emp.get(emp_id, 0.0) + float(wd.number_of_hours or 0.0)

                if code_wd in INCAP_WD_CODES:
                    empleados_con_incap.add(emp_id)
            # Acumular Q1/Q2
            bucket = q_map.setdefault(emp_id, {'q1': 0.0, 'q2': 0.0})
            if quin == 1:
                bucket['q1'] += float(gw)
            elif quin == 2:
                bucket['q2'] += float(gw)

            # Acumular días/horas (totales)
            agg = days_hours_by_emp.setdefault(emp_id, {'d': 0.0, 'h': 0.0})
            agg['d'] += float(d or 0.0)
            agg['h'] += float(h or 0.0)

        # 4) Pagos adicionales (bonos+comisiones) y vacaciones (monto) desde hr.payslip.line
        bono_codes = _norm_codes(getattr(constants, 'ASIGNACION_BONOS', 'bono'), ['BONO'])
        comi_codes = _norm_codes(getattr(constants, 'ASIGNACION_COMISIONES', 'comision'), ['COMISION'])
        vac_codes = _norm_codes(getattr(constants, 'CODES_VACACIONES', ['VAC', 'VACACIONES']), ['VACACIONES'])

        lines = self.env['hr.payslip.line'].search([
            ('slip_id', 'in', slips_mes.ids),
            ('code', 'in', bono_codes + comi_codes + vac_codes),
        ])

        # Conteo diagnóstico (opcional)
        counts_by_code = {}
        for ln in lines:
            c = (ln.code or '').upper()
            counts_by_code[c] = counts_by_code.get(c, 0) + 1

        pago_adic_por_emp = {}  # bono+comision (monto)
        vac_por_emp = {}        # vacaciones (monto)
        for ln in lines:
            emp_id = ln.slip_id.employee_id.id
            code = (ln.code or '').upper()
            amt = float(ln.total or 0.0)

            if code in vac_codes:
                vac_por_emp[emp_id] = vac_por_emp.get(emp_id, 0.0) + amt
            elif code in bono_codes or code in comi_codes:
                pago_adic_por_emp[emp_id] = pago_adic_por_emp.get(emp_id, 0.0) + amt

        # 5) Crear registros (uno por empleado)
        to_create = []
        emp_ids = set(q_map.keys()) | set(pago_adic_por_emp.keys()) | set(vac_por_emp.keys()) | set(days_hours_by_emp.keys())

        for emp_id in sorted(emp_ids):
            qvals = q_map.get(emp_id, {'q1': 0.0, 'q2': 0.0})
            q1 = float(qvals.get('q1') or 0.0)
            q2 = float(qvals.get('q2') or 0.0)
            salario_total = q1 + q2

            pago_adic = float(pago_adic_por_emp.get(emp_id, 0.0))
            vac_monto = float(vac_por_emp.get(emp_id, 0.0))

            dh = days_hours_by_emp.get(emp_id, {'d': 0.0, 'h': 0.0})
            total_days = float(dh.get('d') or 0.0)
            total_hours = float(dh.get('h') or 0.0) / total_days if total_days > 0 else 0.0  # total horas por dia

            vac_dias = float(vac_dias_por_emp.get(emp_id, 0.0))
            vac_horas = float(vac_horas_por_emp.get(emp_id, 0.0))

            # Inferir compañía
            sample = slips_mes.filtered(lambda s: s.employee_id.id == emp_id)[:1]
            comp = (company_id and self.env['res.company'].browse(company_id)) or \
                   (sample and sample.company_id) or self.env.company

            employee = self.env['hr.employee'].browse(emp_id)
            active_contract = self._get_active_contract(employee, period_year, period_month)

            vals = {
                'company_id': comp.id,
                'employee_id': emp_id,
                'contract_id': active_contract.id if active_contract else False,
                'period_year': str(period_year),
                'period_month': period_month,
                'periodo_planilla': f"{period_month}{period_year}",
                'quincena1_gross': q1,
                'quincena2_gross': q2,
                'salario_pagar': salario_total,
                'pago_adicional': pago_adic,
                'vacaciones': vac_monto,
                'total_worked_days': total_days,
                'total_worked_hours': total_hours,
                'vacaciones_days': vac_dias,
                'vacaciones_hours': vac_horas,
                'has_incapacidad': emp_id in empleados_con_incap,
            }
            to_create.append(vals)

        created = self.create(to_create) if to_create else self.browse()
        return len(created)

    # ----------------------------------------------
    # Helpers de periodo/empresa (internos del modelo)
    # ----------------------------------------------
    def _pu_get_period_company(self):
        """
        Resuelve (year, month, company_id) a usar:
        - Si hay un registro en self y trae period_year/period_month/company_id, usa esos.
        - Si no, usa hoy + self.env.company.
        """
        today = fields.Date.context_today(self)
        y = str(today.year)
        m = f"{today.month:02d}"
        cid = self.env.company.id

        if self:
            rec = self[0]
            if rec.period_year:
                y = str(rec.period_year)
            if rec.period_month:
                m = rec.period_month
            if rec.company_id:
                cid = rec.company_id.id
        return y, m, cid

    # ----------------------------------------------
    # Actualizar datos temporales y recargar UI
    # ----------------------------------------------

    def _iter_periods(self, company_id):
        """Devuelve (YYYY, MM) existentes en hr.payslip para la compañía, robusto a idiomas."""
        Slip = self.env['hr.payslip']
        rows = Slip.read_group(
            domain=[('company_id', '=', company_id)],
            fields=['date_to:max'],  # usamos un agregado de fecha REAL
            groupby=['date_to:month'],
            lazy=False,
        )
        periods = set()
        for r in rows:
            dt = r.get('date_to:max') or r.get('date_to')
            if dt:
                # Asegura tipo date
                if not isinstance(dt, date):
                    dt = fields.Date.to_date(dt)
                periods.add((str(dt.year), f"{dt.month:02d}"))
            else:
                for cond in (r.get('__domain') or []):
                    if isinstance(cond, (list, tuple)) and cond[:2] == ['date_to', '>=']:
                        d0 = cond[2]
                        if not isinstance(d0, date):
                            d0 = fields.Date.to_date(d0)
                        periods.add((str(d0.year), f"{d0.month:02d}"))
                        break

        return sorted(periods, key=lambda t: (int(t[0]), int(t[1])))

    def rebuild_all_periods(self, company_id):
        """Reconstruye TODAS las filas (una por empleado x mes) para la compañía."""
        # Limpia lo generado previamente por este usuario para esa compañía
        self.search([('company_id', '=', company_id), ('create_uid', '=', self.env.uid)]).unlink()

        count = 0
        for y, m in self._iter_periods(company_id):
            count += self.rebuild_from_payslips(y, m, company_id)
        return count

    def action_refresh_tmp(self):
        """Ahora genera TODOS los meses de cada compañía activa en el switcher."""
        companies = self.env.companies or self.env.company
        for c in companies:
            self.rebuild_all_periods(c.id)
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    # -----------------------------------------------------------------------
    # Acción: construir mes actual y abrir lista
    # -----------------------------------------------------------------------
    def get_action_planilla_unica(self):
        return self.action_refresh_tmp()




