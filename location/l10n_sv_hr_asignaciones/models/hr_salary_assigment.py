from odoo import models, fields, api, _
from datetime import datetime, timedelta
from odoo.exceptions import UserError
import logging
import unicodedata
import re

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

    # Campos principales de la asignación
    employee_id = fields.Many2one('hr.employee', string='Empleado')
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
    ], string='Tipo')
    monto = fields.Float("Monto", required=False)
    periodo = fields.Date("Periodo", required=True)
    description = fields.Text(string="Descripción", help="Descripción")
    payslip_id = fields.Many2one('hr.payslip', string='Histórico (Boleta)', help="Si se desea vincular con un recibo de pago.")


    # horas_diurnas = fields.Char("Horas extras diurnas", invisible=False)
    # horas_nocturnas = fields.Char("Horas extras nocturnas", invisible=False)
    # horas_diurnas_descanso = fields.Char("Horas extras diurnas dia descanso", invisible=False)
    # horas_nocturnas_descanso = fields.Char("Horas extras nocturnas dia descanso", invisible=False)
    # horas_diurnas_asueto = fields.Char("Horas diurnas dia de asueto", invisible=False)
    # horas_nocturnas_asueto = fields.Char("Horas nocturnas dia de asueto", invisible=False)

    mostrar_horas_extras = fields.Boolean(string="Mostrar Horas Extras", store=False)
    codigo_empleado = fields.Char(string="Código de empleado", store=False)

    def unlink(self):
        for asignacion in self:
            payslip = asignacion.payslip_id
            if payslip and payslip.state in ['done', 'paid']:
                raise UserError(_("No puede eliminar la asignación porque está vinculada a una boleta que ya fue procesada o pagada."))
        return super(HrSalaryAssignment, self).unlink()

    @api.model
    def create_or_update_assignment(self, vals):
        """
        Crea o actualiza una asignación existente si ya hay una del mismo tipo, empleado y periodo.
        Si existen diferencias, consolida montos y descripciones.
        """
        existing = self.search([
            ('employee_id', '=', vals.get('employee_id')),
            ('tipo', '=', vals.get('tipo')),
            ('periodo', '=', vals.get('periodo')),
        ], limit=1)

        def _as_float(val):
            try:
                return round(float(val or 0.0), 4)
            except Exception:
                return 0.0

        def _horas_iguales(v1, v2):
            return _as_float(v1) == _as_float(v2)

        # Convertir horas a float para comparar correctamente
        for campo in [
            constants.HORAS_DIURNAS, constants.HORAS_NOCTURNAS,
            constants.HORAS_DIURNAS_DESCANSO, constants.HORAS_NOCTURNAS_DESCANSO,
            constants.HORAS_DIURNAS_ASUETO, constants.HORAS_NOCTURNAS_ASUETO]:
            if campo in vals:
                try:
                    vals[campo] = round(float(vals[campo]), 4)
                except Exception:
                    vals[campo] = 0.0

        if existing:
            iguales = (
                _horas_iguales(existing.horas_diurnas, vals.get(constants.HORAS_DIURNAS)) and
                _horas_iguales(existing.horas_nocturnas, vals.get(constants.HORAS_NOCTURNAS)) and
                _horas_iguales(existing.horas_diurnas_descanso, vals.get(constants.HORAS_DIURNAS_DESCANSO)) and
                _horas_iguales(existing.horas_nocturnas_descanso, vals.get(constants.HORAS_NOCTURNAS_DESCANSO)) and
                _horas_iguales(existing.horas_diurnas_asueto, vals.get(constants.HORAS_DIURNAS_ASUETO)) and
                _horas_iguales(existing.horas_nocturnas_asueto, vals.get(constants.HORAS_NOCTURNAS_ASUETO)) and
                _as_float(existing.monto) == _as_float(vals.get('monto'))
            )
            desc_actual = (existing.description or '').strip()
            desc_nueva = (vals.get('description') or '').strip()
            #desc_contiene = desc_nueva in desc_actual or desc_actual in desc_nueva

            if iguales:
                _logger.info("Asignación idéntica ya existe (ignorada): %s", existing)
                return existing  # Ignorar duplicado idéntico

            monto_total = _as_float(existing.monto) + _as_float(vals.get('monto'))
            descripcion_final = f"{desc_actual} | {desc_nueva}".strip(" |") if desc_nueva and desc_nueva not in desc_actual else desc_actual

            update_vals = {
                constants.HORAS_DIURNAS: vals.get(constants.HORAS_DIURNAS, existing.horas_diurnas),
                constants.HORAS_NOCTURNAS: vals.get(constants.HORAS_NOCTURNAS, existing.horas_nocturnas),
                constants.HORAS_DIURNAS_DESCANSO: vals.get(constants.HORAS_DIURNAS_DESCANSO, existing.horas_diurnas_descanso),
                constants.HORAS_NOCTURNAS_DESCANSO: vals.get(constants.HORAS_NOCTURNAS_DESCANSO, existing.horas_nocturnas_descanso),
                constants.HORAS_DIURNAS_ASUETO: vals.get(constants.HORAS_DIURNAS_ASUETO, existing.horas_diurnas_asueto),
                constants.HORAS_NOCTURNAS_ASUETO: vals.get(constants.HORAS_NOCTURNAS_ASUETO, existing.horas_nocturnas_asueto),
                'monto': monto_total,
                'description': descripcion_final,
            }
            _logger.info("Actualizando asignación consolidando diferencias en ID %s con valores: %s", existing.id, update_vals)
            existing.write(update_vals)
            return existing
        return super(HrSalaryAssignment, self).create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        """
        Crea múltiples asignaciones salariales, validando cada una según reglas del tipo (horas extra, comisión, etc.).
        También calcula montos de horas extra si aplica.
        """
        records = []
        dias_mes = 30
        horas_laboradas = 8
        empleado = None

        for vals in vals_list:
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
                    if isinstance(codigo_empleado, str):
                        codigo_empleado = codigo_empleado.strip()

                    if not codigo_empleado:
                        raise UserError("Debe proporcionar el código de empleado (codigo_empleado).")

                    empleado = self.env['hr.employee'].search([('barcode', '=', codigo_empleado)], limit=1)
                    if not empleado:
                        raise UserError(f"No se encontró un empleado con código: {codigo_empleado}")
                    vals['employee_id'] = empleado.id

                # Si viene del formulario (usa employee_id directo)
                elif vals.get('employee_id'):
                    empleado = self.env['hr.employee'].browse(vals['employee_id'])
                else:
                    raise UserError("Debe seleccionar un empleado.")

                # Convertir periodo si viene como string
                if constants.PERIODO in vals and isinstance(vals[constants.PERIODO], str):
                    vals[constants.PERIODO] = self._parse_periodo(vals[constants.PERIODO])

                if tipo == constants.ASIGNACION_HORAS_EXTRA.upper() or any(
                        vals.get(campo) not in [None, '', '0', 0] for campo in [
                            constants.HORAS_DIURNAS, constants.HORAS_NOCTURNAS,
                            constants.HORAS_DIURNAS_DESCANSO, constants.HORAS_NOCTURNAS_DESCANSO,
                            constants.HORAS_DIURNAS_ASUETO, constants.HORAS_NOCTURNAS_ASUETO
                        ]):
                    _logger.info("=== Entradas vals: %s ===", vals)

                    contrato = empleado.contract_id
                    if not contrato:
                        raise UserError("No se encontró contrato para el empleado.")

                    # Tabla de conversión según frecuencia de pago(campo contrato.schedule_pay)
                    conversion = {
                        'monthly': 1, #Mensual
                        'semi-monthly': 2, #Quincenal (2 veces al mes)
                        'bi-weekly': 52 / 12 / 2, #Cada 2 semanas
                        'weekly': 52 / 12, #Semanal
                        'daily': 30, #Diario
                        'bimonthly': 0.5, #Bimestral (cada 2 meses)
                        'quarterly': 1 / 3, #Trimestral
                        'semi-annually': 1 / 6, #Semestral
                        'annually': 1 / 12, #Anual
                    }

                    factor = conversion.get(contrato.schedule_pay)
                    if factor is None:
                        raise UserError(f"Frecuencia de pago no soportada: {contrato.schedule_pay}")

                    salario_base = float(contrato.wage or 0.0) * factor
                    salario_hora = round((salario_base / dias_mes) / horas_laboradas, 4)
                    _logger.info("Salario hora calculado: %.4f", salario_hora)

                    # Convertir y actualizar campos de horas como float
                    # horas_diurnas = self._parse_horas(vals.get(constants.HORAS_DIURNAS))
                    # horas_nocturnas = self._parse_horas(vals.get(constants.HORAS_NOCTURNAS))
                    # horas_diurnas_descanso = self._parse_horas(vals.get(constants.HORAS_DIURNAS_DESCANSO))
                    # horas_nocturnas_descanso = self._parse_horas(vals.get(constants.HORAS_NOCTURNAS_DESCANSO))
                    # horas_diurnas_asueto = self._parse_horas(vals.get(constants.HORAS_DIURNAS_ASUETO))
                    # horas_nocturnas_asueto = self._parse_horas(vals.get(constants.HORAS_NOCTURNAS_ASUETO))

                    # Guardar los valores convertidos para evitar errores posteriores
                    # vals[constants.HORAS_DIURNAS] = horas_diurnas
                    # vals[constants.HORAS_NOCTURNAS] = horas_nocturnas
                    # vals[constants.HORAS_DIURNAS_DESCANSO] = horas_diurnas_descanso
                    # vals[constants.HORAS_NOCTURNAS_DESCANSO] = horas_nocturnas_descanso
                    # vals[constants.HORAS_DIURNAS_ASUETO] = horas_diurnas_asueto
                    # vals[constants.HORAS_NOCTURNAS_ASUETO] = horas_nocturnas_asueto

                    # Extraer horas desde horas_extras_ids si no están en vals
                    horas_dict = {}
                    if vals.get('horas_extras_ids'):
                        comando = vals['horas_extras_ids'][0]
                        if isinstance(comando, (list, tuple)) and len(comando) == 3:
                            horas_dict = comando[2]

                    # Parsear valores usando horas_dict
                    horas_diurnas = self._parse_horas(horas_dict.get("horas_diurnas"))
                    horas_nocturnas = self._parse_horas(horas_dict.get("horas_nocturnas"))
                    horas_diurnas_descanso = self._parse_horas(horas_dict.get("horas_diurnas_descanso"))
                    horas_nocturnas_descanso = self._parse_horas(horas_dict.get("horas_nocturnas_descanso"))
                    horas_diurnas_asueto = self._parse_horas(horas_dict.get("horas_diurnas_asueto"))
                    horas_nocturnas_asueto = self._parse_horas(horas_dict.get("horas_nocturnas_asueto"))


                    total_horas = sum([
                        horas_diurnas, horas_nocturnas,
                        horas_diurnas_descanso, horas_nocturnas_descanso,
                        horas_diurnas_asueto, horas_nocturnas_asueto
                    ])
                    if total_horas <= 0:
                        raise UserError("Debe ingresar al menos una hora extra.")

                    # Recargos
                    recargo_he_diurna = 0.0
                    recargo_he_nocturna = 0.0
                    recargo_he_diurna_dia_descanso = 0.0
                    recargo_he_nocturno_dia_descanso = 0.0
                    recargo_he_diurna_dia_festivo = 0.0
                    recargo_he_nocturna_dia_festivo = 0.0

                    if config_utils:
                        recargo_he_diurna = float(config_utils.get_config_value(self.env, 'he_diurna', empleado.company_id.id) or 0.0)
                        recargo_he_nocturna = float(config_utils.get_config_value(self.env, 'he_nocturna', empleado.company_id.id) or 0.0)
                        recargo_he_diurna_dia_descanso = float(config_utils.get_config_value(self.env, 'he_diurna_dia_descanso', empleado.company_id.id) or 0.0)
                        recargo_he_nocturno_dia_descanso = float(config_utils.get_config_value(self.env, 'he_nocturna_dia_descanso', empleado.company_id.id) or 0.0)
                        recargo_he_diurna_dia_festivo = float(config_utils.get_config_value(self.env, 'he_diurna_dia_festivo', empleado.company_id.id) or 0.0)
                        recargo_he_nocturna_dia_festivo = float(config_utils.get_config_value(self.env, 'he_nocturna_dia_festivo', empleado.company_id.id) or 0.0)

                    monto_total = 0.0
                    monto_total += horas_diurnas * salario_hora * (recargo_he_diurna / 100.0)
                    monto_total += horas_nocturnas * salario_hora * (recargo_he_nocturna / 100.0)
                    monto_total += horas_diurnas_descanso * salario_hora * (recargo_he_diurna_dia_descanso / 100.0)
                    monto_total += horas_nocturnas_descanso * salario_hora * (recargo_he_nocturno_dia_descanso / 100.0)
                    monto_total += horas_diurnas_asueto * salario_hora * (recargo_he_diurna_dia_festivo / 100.0)
                    monto_total += horas_nocturnas_asueto * salario_hora * (recargo_he_nocturna_dia_festivo / 100.0)

                    vals['monto'] = round(monto_total, 2)
                    _logger.info("Monto total calculado: %s", monto_total)
                else:
                    # Para otros tipos, asegurarse que haya monto
                    vals['monto'] = float(vals.get('monto', 0.0))

                vals['employee_id'] = vals.get('employee_id') or False
                vals['description'] = vals.get('description', '')

                # Validación: tipo obligatorio
                if not vals.get("tipo"):
                    raise UserError("Debe seleccionar un tipo de asignación (Ej: Horas extra, Viáticos, Comisión, etc.).")

                # Validación: periodo obligatorio
                if not vals.get('periodo'):
                    raise UserError("Debe seleccionar el periodo para la asignación.")

                # Validación: monto no puede ser cero
                if vals.get('monto', 0.0) <= 0:
                    raise UserError("El monto no puede ser cero. Verifique los datos ingresados.")

                # record = self.create_or_update_assignment(vals)  # record = super().create(vals)
                record = self.create_or_update_assignment(vals)

                # Crear el registro en hr.horas.extras si el tipo es OVERTIME
                if tipo == constants.ASIGNACION_HORAS_EXTRA.upper() and record:
                    self.env['hr.horas.extras'].create({
                        'salary_assignment_id': record.id,
                        'horas_diurnas': horas_diurnas,
                        'horas_nocturnas': horas_nocturnas,
                        'horas_diurnas_descanso': horas_diurnas_descanso,
                        'horas_nocturnas_descanso': horas_nocturnas_descanso,
                        'horas_diurnas_asueto': horas_diurnas_asueto,
                        'horas_nocturnas_asueto': horas_nocturnas_asueto,
                        'descripcion': vals.get('description', ''),
                    })

                _logger.info("Registro creado o actualizado (ID=%s) con vals finales: %s", record.id, record.read()[0])
                records.append(record)
            except Exception as e:
                _logger.error("Error al crear asignación con datos %s: %s", vals, str(e))
                raise UserError(_("Error al procesar asignación para el empleado '%s' (código: %s): %s") % (empleado.name, empleado.barcode, str(e)))


        return self.browse([r.id for r in records])

    def action_descargar_plantilla(self):
        """
        Acción que permite descargar la plantilla de asignaciones salariales desde un archivo adjunto.
        Busca el adjunto por nombre definido en las constantes.
        Si no se encuentra, muestra una notificación de error al usuario.
        """
        # Busca el archivo adjunto con la plantilla
        attachment = self.env['ir.attachment'].search([('name', '=', constants.NOMBRE_PLANTILLA_ASIGNACIONES)], limit=1)
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
            return round(float(valor), 4)

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

                    total = round(horas + (minutos / 60.0), 4)
                    _logger.info("Valor '%s' convertido a %.4f horas decimales", valor, total)
                    return total

                except Exception as e:
                    _logger.error("Error al convertir valor '%s' a horas decimales: %s", valor, str(e))
                    raise UserError(_("Error al interpretar el valor de horas: '%s'" % valor))

            # Si es un decimal en texto (ej. "1.25")
            try:
                decimal = round(float(valor), 4)
                _logger.info("Valor decimal string '%s' convertido a %.4f horas", valor, decimal)
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
