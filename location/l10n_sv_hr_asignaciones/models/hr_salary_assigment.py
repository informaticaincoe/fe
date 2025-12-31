from odoo import models, fields, api, _
from datetime import datetime, timedelta, date
from odoo.exceptions import UserError, ValidationError
import logging
import unicodedata
import re
from odoo.tools import float_round
import traceback

_logger = logging.getLogger(__name__)

# Intentamos importar utilidades comunes
try:
    from odoo.addons.common_utils.utils import constants
    from odoo.addons.common_utils.utils import config_utils
    _logger.info("SIT Modulo config_utils [Asignaciones[]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    constants = None
    config_utils = None

class HrSalaryAssignment(models.Model):
    _name = 'hr.salary.assignment'
    _description = 'Salary Assignment'

    PERIOD_MONTHS = [
        ('01', 'enero'), ('02', 'febrero'), ('03', 'marzo'),
        ('04', 'abril'), ('05', 'mayo'), ('06', 'junio'),
        ('07', 'julio'), ('08', 'agosto'), ('09', 'septiembre'),
        ('10', 'octubre'), ('11', 'noviembre'), ('12', 'diciembre'),
    ]

    # Campos principales de la asignación
    employee_id = fields.Many2one('hr.employee', string='Empleado', check_company=True)
    horas_extras_ids = fields.One2many(
        'hr.horas.extras',
        'salary_assignment_id',
        string='Horas Extras'
    )
    tipo = fields.Selection([
        ('OVERTIME', 'Horas extras'),
        ('COMISION', 'Comisión'),
        ('VIATICO', 'Viáticos'),
        ('BONO', 'Bono'),
        ('DEV_RENTA', 'Devolucion de renta'),

    ], string='Tipo')
    monto = fields.Float("Monto", required=False)
    periodo = fields.Date("Periodo", required=True)
    description = fields.Text(string="Descripción", help="Descripción")
    payslip_id = fields.Many2one('hr.payslip', string='Histórico (Boleta)', help="Si se desea vincular con un recibo de pago.", check_company=True)

    # horas_diurnas = fields.Char("Horas extras diurnas", invisible=False)
    # horas_nocturnas = fields.Char("Horas extras nocturnas", invisible=False)
    # horas_diurnas_descanso = fields.Char("Horas extras diurnas dia descanso", invisible=False)
    # horas_nocturnas_descanso = fields.Char("Horas extras nocturnas dia descanso", invisible=False)
    # horas_diurnas_asueto = fields.Char("Horas diurnas dia de asueto", invisible=False)
    # horas_nocturnas_asueto = fields.Char("Horas nocturnas dia de asueto", invisible=False)

    mostrar_horas_extras = fields.Boolean(string="Mostrar Horas Extras", default=False, store=True)

    codigo_empleado = fields.Char(string="Código de empleado", store=False)

    company_id = fields.Many2one("res.company", string="Compañía", required=True, default=lambda self: self.env.company, index=True,)

    # ----- Filtro por año, mes y dia -----
    employee_name = fields.Char(
        string="Nombre del Empleado",
        compute='_compute_employee_name',
        store=True,
        help="Nombre completo del empleado para búsquedas y agrupaciones."
    )

    def year_selection(self):
        current_year = date.today().year
        years = list(range(current_year - 3, current_year + 2))
        return [(str(y), str(y)) for y in years]

    period_year = fields.Selection(
        selection=year_selection,
        string='Año',
        compute='_compute_period_fields',
        store=True,
        index=True
    )
    period_month = fields.Selection(
        selection=PERIOD_MONTHS,
        string='Mes',
        compute='_compute_period_fields',
        store=True,
        index=True
    )
    period_quincena = fields.Selection(
        selection=[('1', '1ª quincena'), ('2', '2ª quincena')],
        string='Quincena',
        compute='_compute_period_fields',
        store=True,
        index=True
    )

    # Métodos compute para los nuevos campos
    @api.depends('employee_id.name')
    def _compute_employee_name(self):
        for rec in self:
            rec.employee_name = rec.employee_id.name or False

    @api.depends('periodo')
    def _compute_period_fields(self):
        for rec in self:
            if rec.periodo:
                d = rec.periodo
                rec.period_year = str(d.year)
                rec.period_month = f"{d.month:02d}"
                rec.period_quincena = '1' if d.day <= 15 else '2'
            else:
                rec.period_year = False
                rec.period_month = False
                rec.period_quincena = False

    def unlink(self):
        for asignacion in self:
            payslip = asignacion.payslip_id
            if payslip and payslip.state in ['done', 'paid']:
                raise UserError(_("No puede eliminar la asignación porque está vinculada a una boleta que ya fue procesada o pagada."))
        return super(HrSalaryAssignment, self).unlink()

    def _as_float(self, val):
        try:
            return round(float(val or 0.0), 4)
        except Exception:
            return 0.0

    def _horas_iguales(self, v1, v2):
        try:
            return abs(self._as_float(v1) - self._as_float(v2)) < 0.0001
        except Exception:
            return False

    def _calcular_monto_horas_extras(self, empleado, horas_dict):
        try:
            # dias_mes = 30
            # horas_laboradas = 8

            contrato = empleado.contract_id
            if not contrato:
                raise UserError("No se encontró contrato para el empleado.")

            cid = empleado.company_id.id
            self = self.with_company(cid)  # ✅ asegura contexto
            dias_mes = config_utils.get_dias_promedio_salario(self.env, cid)

            calendar = contrato.resource_calendar_id
            if not calendar:
                raise UserError("No se encontró el horario de trabajo para el empleado.")
            horas_laboradas = calendar.hours_per_day if calendar else 8
            HORAS_JORNADA_LEGAL = 8

            _logger.info("HORAS LABORADAS %s", horas_laboradas)
            _logger.info("HORAS LABORADASsss %s", calendar.hours_per_day )


            conversion = {
                'monthly': 1, 'semi-monthly': 2, 'bi-weekly': 52 / 12 / 2,
                'weekly': 52 / 12, 'daily': 30, 'bimonthly': 0.5,
                'quarterly': 1 / 3, 'semi-annually': 1 / 6, 'annually': 1 / 12,
            }
            factor = conversion.get(contrato.schedule_pay)
            if factor is None:
                raise UserError(f"Frecuencia de pago no soportada: {contrato.schedule_pay}")

            salario_base = float(contrato.wage or 0.0) * factor
            salario_hora = round((salario_base / dias_mes) / HORAS_JORNADA_LEGAL, 4)

            recargos = {
                'diurna': 0, 'nocturna': 0, 'diurna_descanso': 0, 'nocturna_descanso': 0,
                'diurna_asueto': 0, 'nocturna_asueto': 0
            }
            if config_utils:
                cid = empleado.company_id.id
                recargos = {
                    'diurna': float(config_utils.get_config_value(self.env, 'he_diurna', cid) or 0.0),
                    'nocturna': float(config_utils.get_config_value(self.env, 'he_nocturna', cid) or 0.0),
                    'diurna_descanso': float(config_utils.get_config_value(self.env, 'he_diurna_dia_descanso', cid) or 0.0),
                    'nocturna_descanso': float(
                        config_utils.get_config_value(self.env, 'he_nocturna_dia_descanso', cid) or 0.0),
                    'diurna_asueto': float(config_utils.get_config_value(self.env, 'he_diurna_dia_festivo', cid) or 0.0),
                    'nocturna_asueto': float(
                        config_utils.get_config_value(self.env, 'he_nocturna_dia_festivo', cid) or 0.0),
                }

            total = 0.0
            total += horas_dict.get('horas_diurnas', 0) * salario_hora * recargos['diurna'] / 100.0
            total += horas_dict.get('horas_nocturnas', 0) * salario_hora * recargos['nocturna'] / 100.0
            total += horas_dict.get('horas_diurnas_descanso', 0) * salario_hora * recargos['diurna_descanso'] / 100.0
            total += horas_dict.get('horas_nocturnas_descanso', 0) * salario_hora * recargos['nocturna_descanso'] / 100.0
            total += horas_dict.get('horas_diurnas_asueto', 0) * salario_hora * recargos['diurna_asueto'] / 100.0
            total += horas_dict.get('horas_nocturnas_asueto', 0) * salario_hora * recargos['nocturna_asueto'] / 100.0
            return total
        except Exception as e:
            _logger.error("Error procesando descripción: %s", traceback.format_exc())
            raise

    @api.model
    def create_or_update_assignment(self, vals):
        """
        Crea o actualiza una asignación existente si ya hay una del mismo tipo, empleado y periodo.
        Si existen diferencias, consolida montos y descripciones.
        """
        try:
            # Convertir horas en vals a float decimal usando _parse_horas para compararlas bien
            horas_campos = [
                constants.HORAS_DIURNAS, constants.HORAS_NOCTURNAS,
                constants.HORAS_DIURNAS_DESCANSO, constants.HORAS_NOCTURNAS_DESCANSO,
                constants.HORAS_DIURNAS_ASUETO, constants.HORAS_NOCTURNAS_ASUETO,
            ]

            # Determinar si es un viático con horas extras
            es_viatico_con_horas_extras = vals.get('tipo') == constants.ASIGNACION_VIATICOS.upper() and any(vals.get(campo) for campo in horas_campos)

            # calcular comp_id una sola vez
            comp_id = vals.get('company_id') or (
                    vals.get('employee_id') and self.env['hr.employee'].browse(vals['employee_id']).company_id.id
            ) or self.env.company.id

            domain = [
                ('employee_id', '=', vals.get('employee_id')),
                ('tipo', '=', vals.get('tipo')),
                ('periodo', '=', vals.get('periodo')),
                ('company_id', '=', comp_id),
            ]

            existing = self.with_company(comp_id).search(domain, limit=1)

            # Solo agregar la condición de 'mostrar_horas_extras' si el tipo es VIATICO
            # y ese campo está presente en vals
            if vals.get('tipo') == constants.ASIGNACION_VIATICOS.upper():
                if 'mostrar_horas_extras' in vals:
                    domain.append(('mostrar_horas_extras', '=', vals['mostrar_horas_extras']))
                else:
                    domain.append(('mostrar_horas_extras', '=', es_viatico_con_horas_extras))

            existing = self.search(domain, limit=1)

            _logger.info("Tipo de asignación: %s, mostrar_horas_extras: %s", vals.get('tipo'), vals.get('mostrar_horas_extras'))
            # Asegurar valor por defecto si no se define mostrar_horas_extras
            if vals.get('tipo') == constants.ASIGNACION_VIATICOS.upper() and 'mostrar_horas_extras' not in vals:
                vals['mostrar_horas_extras'] = es_viatico_con_horas_extras

            # Convertir horas en vals a float decimal usando _parse_horas para compararlas bien
            for campo in horas_campos:
                if campo in vals:
                    try:
                        vals[campo] = self._parse_horas(vals[campo])
                    except Exception:
                        vals[campo] = 0.0  # En caso de error, poner 0.0

            # Si ya existe una asignación con los mismos datos
            if existing:
                _logger.info("Actualizando asignación consolidando diferencias en ID %s", existing.id)

                # Obtener las horas extra asociadas a esta asignación (usando el modelo hr.horas.extras)
                horas_existentes = self._sumar_horas_extras(existing)
                # Extraer y sumar horas nuevas desde horas_extras_ids en vals
                horas_nuevas = {campo: 0.0 for campo in horas_campos}
                if 'horas_extras_ids' in vals:
                    for cmd in vals['horas_extras_ids']:
                        # cmd es tipo (0, 0, {vals})
                        if cmd[0] == 0 and isinstance(cmd[2], dict):
                            for campo in horas_campos:
                                val = cmd[2].get(campo)
                                if val:
                                    try:
                                        horas_nuevas[campo] += self._parse_horas(val)
                                    except Exception:
                                        pass
                _logger.info(f"Comparando horas existentes: {horas_existentes} con nuevas: {horas_nuevas}")

                horas_directas = {campo: 0.0 for campo in horas_campos}
                for campo in horas_campos:
                    if campo in vals and vals[campo]:
                        try:
                            horas_directas[campo] += self._parse_horas(vals[campo])
                        except Exception:
                            pass

                horas_aportadas = {
                    campo: float(horas_nuevas.get(campo, 0.0)) + float(horas_directas.get(campo, 0.0))
                    for campo in horas_campos
                }
                hay_horas_aportadas = any(v > 0 for v in horas_aportadas.values())

                # Función auxiliar para comparar horas con tolerancia
                def horas_iguales(v1, v2):
                    try:
                        return abs(float(v1) - float(v2)) < 0.0001
                    except Exception:
                        return False

                # Determinar si se enviaron nuevas horas
                hay_horas_nuevas = 'horas_extras_ids' in vals and any(
                    cmd[0] == 0 and isinstance(cmd[2], dict) and any(cmd[2].get(c, 0.0) for c in horas_campos)
                    for cmd in vals['horas_extras_ids']
                )

                # Solo comparar si hay nuevas horas
                horas_diferentes = any(
                    not horas_iguales(horas_existentes.get(campo, 0.0), horas_nuevas.get(campo, 0.0))
                    for campo in horas_campos
                ) if hay_horas_nuevas else False

                monto_diferente = abs(self._as_float(existing.monto) - self._as_float(vals.get('monto', 0.0))) > 0.0001

                # Si las horas o el monto han cambiado, se actualiza el registro
                desc_actual = existing.description or ''
                desc_nueva = vals.get('description') or ''

                _logger.info("desc_actual tipo: %s, valor: %s", type(desc_actual), desc_actual)
                _logger.info("desc_nueva tipo: %s, valor: %s", type(desc_nueva), desc_nueva)

                if not isinstance(desc_actual, str):
                    desc_actual = str(desc_actual)
                if not isinstance(desc_nueva, str):
                    desc_nueva = str(desc_nueva)

                descripcion_final = desc_actual.strip()

                if desc_nueva.strip() and desc_nueva.strip() not in desc_actual:
                    descripcion_final = f"{desc_actual.strip()} | {desc_nueva.strip()}".strip(" | ")

                if not horas_diferentes and not monto_diferente and not hay_horas_aportadas:
                    #_logger.info("Asignación ya existe, solo se actualizó descripción: %s", existing)
                    existing.write({'description': descripcion_final})
                    omitidas = self.env.context.get('asignaciones_omitidas', [])
                    omitidas.append(
                        f"{existing.employee_id.name} ({existing.employee_id.barcode}) - {existing.tipo} - {existing.periodo.strftime('%d/%m/%Y')}"
                    )
                    self = self.with_context(asignaciones_omitidas=omitidas)
                    return existing
                _logger.info("DEBUG tipos: desc_actual=%s (%s), desc_nueva=%s (%s)", desc_actual, type(desc_actual),
                             desc_nueva, type(desc_nueva))

                if horas_diferentes:
                    # Consolidar horas sumando las existentes + nuevas
                    horas_dict = {
                        campo: horas_existentes.get(campo, 0.0) + horas_nuevas.get(campo, 0.0)
                        for campo in horas_campos
                    }
                    nuevo_monto = float_round(self._calcular_monto_horas_extras(existing.employee_id, horas_dict), 2)
                    existing.write({
                        'monto': nuevo_monto,
                        'description': descripcion_final,
                    })
                    _logger.info("Actualizando asignación consolidando diferencias en ID %s ", existing.id)

                    if existing.horas_extras_ids:
                        existing.horas_extras_ids.unlink()
                        self.env['hr.horas.extras'].create({
                            'salary_assignment_id': existing.id,
                            **horas_dict,
                            'descripcion': descripcion_final,
                        })

                elif hay_horas_aportadas:
                    horas_sumadas = {campo: horas_existentes.get(campo, 0.0) + horas_aportadas.get(campo, 0.0)
                                     for campo in horas_campos}
                    nuevo_monto = float_round(self._calcular_monto_horas_extras(existing.employee_id, horas_sumadas), 2)

                    existing.write({
                        'monto': nuevo_monto,
                        'description': descripcion_final,
                    })

                    if existing.horas_extras_ids:
                        existing.horas_extras_ids.unlink()
                    self.env['hr.horas.extras'].create({
                        'salary_assignment_id': existing.id,
                        **horas_sumadas,
                        'descripcion': descripcion_final,
                    })

                else:
                    # Solo consolidar monto y descripción
                    monto_total = float_round(self._as_float(existing.monto) + self._as_float(vals.get('monto', 0.0)), 2)
                    existing.write({
                        'monto': monto_total,
                        'description': descripcion_final,
                    })

                _logger.info("Asignación consolidada actualizada: ID %s", existing.id)
                return existing  # Retorna la asignación consolidada

            # Si no existe, creamos una nueva asignación
            _logger.info("Creando nueva asignación para empleado=%s, tipo=%s, periodo=%s", vals.get('employee_id'),
                         vals.get('tipo'), vals.get('periodo'))
            #return super(HrSalaryAssignment, self).create(vals)
            nuevo = super(HrSalaryAssignment, self).create(vals)
            _logger.info("Asignación nueva creada: ID %s", nuevo.id)
            return nuevo
        except Exception as e:
            # Si no existe, creamos una nueva asignación
            _logger.info("Creando nueva asignación para empleado=%s, tipo=%s, periodo=%s", vals.get('employee_id'), vals.get('tipo'), vals.get('periodo'))
            return super(HrSalaryAssignment, self).create(vals)

    def _sumar_horas_extras(self, asignacion):
        """
        Suma todas las horas desde las líneas hijas (hr.horas.extras) asociadas a una asignación salarial.
        Retorna un diccionario con las claves de horas.
        """
        try:
            total = {
                'horas_diurnas': 0.0,
                'horas_nocturnas': 0.0,
                'horas_diurnas_descanso': 0.0,
                'horas_nocturnas_descanso': 0.0,
                'horas_diurnas_asueto': 0.0,
                'horas_nocturnas_asueto': 0.0,
            }
            for he in asignacion.horas_extras_ids:  # Aquí nos referimos al modelo 'hr.horas.extras'
                total['horas_diurnas'] += self._parse_horas(he.horas_diurnas)
                total['horas_nocturnas'] += self._parse_horas(he.horas_nocturnas)
                total['horas_diurnas_descanso'] += self._parse_horas(he.horas_diurnas_descanso)
                total['horas_nocturnas_descanso'] += self._parse_horas(he.horas_nocturnas_descanso)
                total['horas_diurnas_asueto'] += self._parse_horas(he.horas_diurnas_asueto)
                total['horas_nocturnas_asueto'] += self._parse_horas(he.horas_nocturnas_asueto)
            return total
        except Exception as e:
            _logger.error("Error procesando descripción: %s", traceback.format_exc())
            raise

    @api.model_create_multi
    def create(self, vals_list):
        """
        Crea múltiples asignaciones salariales, validando cada una según reglas del tipo (horas extra, comisión, etc.).
        También calcula montos de horas extra si aplica.
        """
        try:
            records = []
            asignaciones_omitidas = []
                #horas_validas = False

            for vals in vals_list:
                #self._validar_asignacion(vals)
                empleado = None
                _logger.info("Creando asignación con datos: %s", vals)

                if vals.get("tipo") == constants.ASIGNACION_COMISIONES.upper():
                    for k, v in vals.items():
                        _logger.info("Campo: %s - Tipo: %s - Valor: %s", k, type(v), v)
                try:
                    # Normalizar tipo de asignación
                    tipo_raw = (vals.get("tipo") or "").strip()
                    tipo_map = {
                        "horas extras": constants.ASIGNACION_HORAS_EXTRA.upper(),
                        "hora extra": constants.ASIGNACION_HORAS_EXTRA.upper(),
                        "viáticos": constants.ASIGNACION_VIATICOS.upper(),
                        "viaticos": constants.ASIGNACION_VIATICOS.upper(),
                    }
                    tipo = tipo_map.get(tipo_raw, tipo_raw.upper())
                    vals["tipo"] = tipo
                    _logger.info("Procesando asignación tipo: %s", tipo)

                    # Buscar empleado por código o ID
                    codigo_empleado = vals.get('codigo_empleado')
                    _logger.info("Codigo del empleado: %s", codigo_empleado)

                    # Si viene de importación (usa código de empleado)
                    if codigo_empleado:
                        cod = codigo_empleado.strip() if isinstance(codigo_empleado, str) else codigo_empleado

                        # No filtres por company_id aquí si no viene en el archivo;
                        # busca por barcode y luego desambiguas tú.
                        emp_domain = [('barcode', '=', cod)]
                        if vals.get('company_id'):
                            emp_domain.append(('company_id', '=', vals['company_id']))
                        empleados = self.env['hr.employee'].search(emp_domain)

                        if not empleados:
                            raise UserError(f"No se encontró un empleado con código: {cod}")

                        if len(empleados) > 1 and not vals.get('company_id'):
                            empresas = ", ".join(sorted({e.company_id.display_name for e in empleados}))
                            raise UserError(
                                f"El código {cod} existe en múltiples empresas ({empresas}). "
                                f"Indique la empresa en el archivo (columna company_id) para desambiguar."
                            )

                        empleado = empleados[0]
                        vals['employee_id'] = empleado.id

                    # Si viene del formulario (usa employee_id directo)
                    elif vals.get('employee_id'):
                        empleado = self.env['hr.employee'].browse(vals['employee_id'])
                    else:
                        raise UserError("Debe seleccionar un empleado.")

                    # Convertir periodo si viene como string
                    if constants.PERIODO in vals and isinstance(vals[constants.PERIODO], str):
                        vals[constants.PERIODO] = self._parse_periodo(vals[constants.PERIODO])

                    # Detectar si hay horas extras en la relación One2many 'horas_extras_ids'
                    hay_horas = False
                    if 'horas_extras_ids' in vals:
                        for cmd in vals['horas_extras_ids']:
                            if cmd[0] == 0:  # comando para crear línea nueva
                                horas_linea = cmd[2]
                                if any(horas_linea.get(campo, 0) not in [None, '', 0, 0.0, '0'] for campo in [
                                    constants.HORAS_DIURNAS, constants.HORAS_NOCTURNAS,
                                    constants.HORAS_DIURNAS_DESCANSO, constants.HORAS_NOCTURNAS_DESCANSO,
                                    constants.HORAS_DIURNAS_ASUETO, constants.HORAS_NOCTURNAS_ASUETO
                                ]):
                                    hay_horas = True
                                    break
                    else:
                        # fallback, si los campos vienen planos en vals
                        hay_horas = any(vals.get(campo) not in [None, '', '0', 0, 0.0] for campo in [
                            constants.HORAS_DIURNAS, constants.HORAS_NOCTURNAS,
                            constants.HORAS_DIURNAS_DESCANSO, constants.HORAS_NOCTURNAS_DESCANSO,
                            constants.HORAS_DIURNAS_ASUETO, constants.HORAS_NOCTURNAS_ASUETO
                        ])
                    _logger.info("=== Hay horas extras: %s ===", hay_horas)

                    # Asignar mostrar_horas_extras según tipo y horas
                    if tipo == constants.ASIGNACION_VIATICOS.upper():
                        vals["mostrar_horas_extras"] = bool(hay_horas)
                    else:
                        vals.setdefault("mostrar_horas_extras", False)

                    if tipo == constants.ASIGNACION_HORAS_EXTRA.upper() or vals.get("mostrar_horas_extras") or hay_horas:
                        _logger.info("=== Entradas vals: %s ===", vals)

                        # Extraer horas desde horas_extras_ids si no están en vals
                        horas_dict = {}
                        if 'horas_extras_ids' in vals:
                            for cmd in vals['horas_extras_ids']:
                                if cmd[0] == 0:
                                    horas_dict = {
                                        campo: self._parse_horas(cmd[2].get(campo, 0))
                                        for campo in [
                                            constants.HORAS_DIURNAS, constants.HORAS_NOCTURNAS,
                                            constants.HORAS_DIURNAS_DESCANSO, constants.HORAS_NOCTURNAS_DESCANSO,
                                            constants.HORAS_DIURNAS_ASUETO, constants.HORAS_NOCTURNAS_ASUETO
                                        ]
                                    }
                                    break
                        else:
                            for campo in [
                                constants.HORAS_DIURNAS, constants.HORAS_NOCTURNAS,
                                constants.HORAS_DIURNAS_DESCANSO, constants.HORAS_NOCTURNAS_DESCANSO,
                                constants.HORAS_DIURNAS_ASUETO, constants.HORAS_NOCTURNAS_ASUETO
                            ]:
                                try:
                                    horas_dict[campo] = round(float(vals.get(campo, 0) or 0), 4)
                                except ValueError:
                                    horas_dict[campo] = 0.0

                        total_horas = sum(horas_dict.values())
                        if total_horas <= 0:
                            raise UserError("Debe ingresar al menos una hora extra.")

                        monto_total = self._calcular_monto_horas_extras(empleado, horas_dict)
                        vals['monto'] = float_round(monto_total, precision_digits=2)

                        # También guarda la descripción en las horas extras
                        if 'horas_extras_ids' in vals and horas_dict:
                            for cmd in vals['horas_extras_ids']:
                                if cmd[0] == 0:
                                    cmd[2]['descripcion'] = vals.get('description', '')

                    # Validar para tipo COMISION, VIATICO o BONO que monto sea positivo
                    if tipo in [constants.ASIGNACION_COMISIONES, constants.ASIGNACION_VIATICOS, constants.ASIGNACION_BONOS]:
                        if not vals.get('monto') or vals['monto'] <= 0:
                            raise UserError(f"Para asignación tipo {tipo} el monto debe ser mayor que cero.")

                    self = self.with_context(asignaciones_omitidas=asignaciones_omitidas)
                    record = self.create_or_update_assignment(vals)
                    records.append(record)
                except Exception as e:
                    _logger.error("Error al crear asignación con datos %s", vals)
                    _logger.error("Excepción completa:\n%s", traceback.format_exc())

            # Notificación si hay asignaciones omitidas por duplicado exacto
            if asignaciones_omitidas:
                mensaje = "Algunas asignaciones no se agregaron porque ya existían con los mismos datos:\n\n"
                mensaje += "\n".join(f"• {x}" for x in asignaciones_omitidas)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Asignaciones omitidas',
                        'message': mensaje,
                        'type': 'warning',
                        'sticky': False,
                    }
                }
            return self.browse([r.id for r in records])
        except Exception as e:
            _logger.error("Error procesando descripción: %s", traceback.format_exc())
            raise

    def action_descargar_plantilla(self):
        """
        Acción que permite descargar la plantilla de asignaciones salariales desde un archivo adjunto.
        Busca el adjunto por nombre definido en las constantes.
        Si no se encuentra, muestra una notificación de error al usuario.
        """
        # Busca el archivo adjunto con la plantilla
        attachment = self.env['ir.attachment'].search([
            ('name', '=', 'plantilla_asignaciones.xlsx'), #constants.NOMBRE_PLANTILLA_ASIGNACIONES
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        if not attachment:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'No se encontró la plantilla para descargar.',
                    'type': 'danger',
                    'sticky': False,
                }
            }
        # Retorna la acción para descargar el archivo
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def _parse_horas(self, valor):
        """
        Convierte un valor tipo '9:05' o '1.5' en un número decimal de horas.
        Soporta strings con formato 'HH:MM', decimales, enteros y valores vacíos.
        - Strings con formato HH:MM (ej. '9:05')
        - Decimales en string (ej. '1.25')
        - Valores numéricos (int o float)
        - Strings vacíos o None, retornando 0.0

        Lanza un UserError si el formato no es reconocido o inválido.
        """

        _logger.info("Intentando convertir valor de horas: %s", valor)

        if valor is None or (isinstance(valor, str) and not valor.strip()):
            _logger.info("Valor vacío o string en blanco recibido, se interpreta como 0.0 horas.")
            return 0.0

        # Si ya es float o int
        if isinstance(valor, (float, int)):
            _logger.info("Valor numérico directo detectado: %.4f", float(valor))
            return round(float(valor), 2)

        # Si es texto
        if isinstance(valor, str):
            valor = valor.strip()

            # Si viene en formato HH:MM
            if re.match(r'^\d{1,2}:\d{1,2}$', valor):
                partes = valor.split(':')
                try:
                    horas = int(partes[0])
                    minutos = int(partes[1])

                    if minutos >= 60:
                        _logger.warning("Minutos inválidos detectados en valor '%s' (>= 60)", valor)
                        raise UserError(_("Minutos no pueden ser iguales o mayores a 60: '%s'" % valor))

                    total = round(horas + (minutos / 60.0), 2)
                    _logger.info("Valor '%s' convertido a %.2f horas decimales", valor, total)
                    return total

                except Exception as e:
                    _logger.error("Error al convertir valor '%s' a horas decimales: %s", valor, str(e))
                    raise UserError(_("Error al interpretar el valor de horas: '%s'" % valor))

            # Si es un decimal en texto (ej. "1.25")
            try:
                valor_normalizado = str(valor).replace(',', '.')
                decimal = round(float(valor_normalizado), 2)
                _logger.info("Valor decimal string '%s' convertido a %.2f horas", valor, decimal)
                return decimal
            except ValueError:
                _logger.warning("Valor inválido para horas: '%s'", valor)
                raise UserError(_("Valor inválido para horas: '%s'" % valor))

        # Si llegó aquí es un tipo no soportado
        _logger.error("Tipo de dato no soportado para horas: %s (%s)", valor, type(valor))
        raise UserError(_("Formato de horas no reconocido: %s" % valor))

    def _parse_periodo(self, valor):
        """
        Convierte valor tipo '2 06 2025' o similar en un objeto date,
        o retorna None si no es válido.
        """
        if not valor or not isinstance(valor, str):
            return None
        formatos = ["%d %m %Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"]
        for fmt in formatos:
            try:
                return datetime.strptime(valor.strip(), fmt).date()
            except Exception:
                continue
        return None
