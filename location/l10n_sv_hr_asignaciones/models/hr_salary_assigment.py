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

    mostrar_horas_extras = fields.Boolean(string="Mostrar Horas Extras", store=True)

    codigo_empleado = fields.Char(string="Código de empleado", store=False)

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
        return self._as_float(v1) == self._as_float(v2)

    def _calcular_monto_horas_extras(self, empleado, horas_dict):
        dias_mes = 30
        horas_laboradas = 8

        contrato = empleado.contract_id
        if not contrato:
            raise UserError("No se encontró contrato para el empleado.")

        conversion = {
            'monthly': 1, 'semi-monthly': 2, 'bi-weekly': 52 / 12 / 2,
            'weekly': 52 / 12, 'daily': 30, 'bimonthly': 0.5,
            'quarterly': 1 / 3, 'semi-annually': 1 / 6, 'annually': 1 / 12,
        }
        factor = conversion.get(contrato.schedule_pay)
        if factor is None:
            raise UserError(f"Frecuencia de pago no soportada: {contrato.schedule_pay}")

        salario_base = float(contrato.wage or 0.0) * factor
        salario_hora = round((salario_base / dias_mes) / horas_laboradas, 4)

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
        return round(total, 2)

    @api.model
    def create_or_update_assignment(self, vals):
        """
        Crea o actualiza una asignación existente si ya hay una del mismo tipo, empleado y periodo.
        Si existen diferencias, consolida montos y descripciones.
        """
        # Buscar si existe una asignación con el mismo empleado, tipo y periodo
        existing = self.search([
            ('employee_id', '=', vals.get('employee_id')),
            ('tipo', '=', vals.get('tipo')),
            ('periodo', '=', vals.get('periodo')),
        ], limit=1)

        # Convertir horas a float para comparar correctamente, si es necesario
        for campo in [
            constants.HORAS_DIURNAS, constants.HORAS_NOCTURNAS,
            constants.HORAS_DIURNAS_DESCANSO, constants.HORAS_NOCTURNAS_DESCANSO,
            constants.HORAS_DIURNAS_ASUETO, constants.HORAS_NOCTURNAS_ASUETO]:
            if campo in vals:
                try:
                    vals[campo] = round(float(vals[campo]), 4)
                except ValueError:
                    vals[campo] = 0.0  # Si hay un error, se asegura que sea 0.0

        if existing:
            # Obtener las horas extra asociadas a esta asignación (usando el modelo hr.horas.extras)
            horas_existentes = self._sumar_horas_extras(existing)

            iguales = all([
                self._horas_iguales(horas_existentes['horas_diurnas'], vals.get(constants.HORAS_DIURNAS)),
                self._horas_iguales(horas_existentes['horas_nocturnas'], vals.get(constants.HORAS_NOCTURNAS)),
                self._horas_iguales(horas_existentes['horas_diurnas_descanso'], vals.get(constants.HORAS_DIURNAS_DESCANSO)),
                self._horas_iguales(horas_existentes['horas_nocturnas_descanso'], vals.get(constants.HORAS_NOCTURNAS_DESCANSO)),
                self._horas_iguales(horas_existentes['horas_diurnas_asueto'], vals.get(constants.HORAS_DIURNAS_ASUETO)),
                self._horas_iguales(horas_existentes['horas_nocturnas_asueto'], vals.get(constants.HORAS_NOCTURNAS_ASUETO)),
                self._as_float(existing.monto) == self._as_float(vals.get('monto'))
            ])

            if iguales:
                _logger.info("Asignación idéntica ya existe (ignorada): %s", existing)
                return existing  # Ignorar duplicado idéntico

            # Consolidar sumando horas existentes con las nuevas horas que se pasaron en vals
            horas_dict = {
                constants.HORAS_DIURNAS: horas_existentes['horas_diurnas'] + vals.get(constants.HORAS_DIURNAS, 0.0),
                constants.HORAS_NOCTURNAS: horas_existentes['horas_nocturnas'] + vals.get(constants.HORAS_NOCTURNAS, 0.0),
                constants.HORAS_DIURNAS_DESCANSO: horas_existentes['horas_diurnas_descanso'] + vals.get(constants.HORAS_DIURNAS_DESCANSO, 0.0),
                constants.HORAS_NOCTURNAS_DESCANSO: horas_existentes['horas_nocturnas_descanso'] + vals.get(constants.HORAS_NOCTURNAS_DESCANSO, 0.0),
                constants.HORAS_DIURNAS_ASUETO: horas_existentes['horas_diurnas_asueto'] + vals.get(constants.HORAS_DIURNAS_ASUETO, 0.0),
                constants.HORAS_NOCTURNAS_ASUETO: horas_existentes['horas_nocturnas_asueto'] + vals.get(constants.HORAS_NOCTURNAS_ASUETO, 0.0),
            }

            # Consolidar monto
            monto_total = self._as_float(existing.monto) + self._as_float(vals.get('monto'))

            # Consolidar descripción
            desc_actual = (existing.description or '').strip()
            desc_nueva = (vals.get('description') or '').strip()
            descripcion_final = f"{desc_actual} | {desc_nueva}".strip(
                " |") if desc_nueva and desc_nueva not in desc_actual else desc_actual

            # Actualizamos la asignación existente
            update_vals = {
                # constants.HORAS_DIURNAS: horas_dict[constants.HORAS_DIURNAS],
                # constants.HORAS_NOCTURNAS: horas_dict[constants.HORAS_NOCTURNAS],
                # constants.HORAS_DIURNAS_DESCANSO: horas_dict[constants.HORAS_DIURNAS_DESCANSO],
                # constants.HORAS_NOCTURNAS_DESCANSO: horas_dict[constants.HORAS_NOCTURNAS_DESCANSO],
                # constants.HORAS_DIURNAS_ASUETO: horas_dict[constants.HORAS_DIURNAS_ASUETO],
                # constants.HORAS_NOCTURNAS_ASUETO: horas_dict[constants.HORAS_NOCTURNAS_ASUETO],
                'monto': monto_total,
                'description': descripcion_final,
            }

            _logger.info("Actualizando asignación consolidando diferencias en ID %s con valores: %s", existing.id, update_vals)
            existing.write(update_vals)
            return existing  # Retorna la asignación consolidada

        # Si no existe, creamos una nueva asignación
        _logger.info("Creando nueva asignación para empleado=%s, tipo=%s, periodo=%s", vals.get('employee_id'), vals.get('tipo'), vals.get('periodo'))
        return super(HrSalaryAssignment, self).create(vals)

    def _sumar_horas_extras(self, asignacion):
        """
        Suma todas las horas desde las líneas hijas (hr.horas.extras) asociadas a una asignación salarial.
        Retorna un diccionario con las claves de horas.
        """
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

    @api.model_create_multi
    def create(self, vals_list):
        """
        Crea múltiples asignaciones salariales, validando cada una según reglas del tipo (horas extra, comisión, etc.).
        También calcula montos de horas extra si aplica.
        """
        records = []
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

                # Horas
                horas_diurnas = horas_nocturnas = 0.0
                horas_diurnas_descanso = horas_nocturnas_descanso = 0.0
                horas_diurnas_asueto = horas_nocturnas_asueto = 0.0

                if (tipo == constants.ASIGNACION_HORAS_EXTRA.upper()
                        or (tipo == constants.ASIGNACION_VIATICOS.upper() and vals.get("mostrar_horas_extras"))
                        or any(vals.get(campo) not in [None, '', '0', 0] for campo in [
                            constants.HORAS_DIURNAS, constants.HORAS_NOCTURNAS,
                            constants.HORAS_DIURNAS_DESCANSO, constants.HORAS_NOCTURNAS_DESCANSO,
                            constants.HORAS_DIURNAS_ASUETO, constants.HORAS_NOCTURNAS_ASUETO
                        ])):
                    _logger.info("=== Entradas vals: %s ===", vals)

                    # Extraer horas desde horas_extras_ids si no están en vals
                    horas_dict = {}
                    descripciones = []
                    if vals.get('horas_extras_ids'):
                        for comando in vals['horas_extras_ids']:
                            if isinstance(comando, (list, tuple)) and len(comando) == 3:
                                horas_dict = comando[2]
                                horas_diurnas += self._parse_horas(horas_dict.get("horas_diurnas"))
                                horas_nocturnas += self._parse_horas(horas_dict.get("horas_nocturnas"))
                                horas_diurnas_descanso += self._parse_horas(horas_dict.get("horas_diurnas_descanso"))
                                horas_nocturnas_descanso += self._parse_horas(horas_dict.get("horas_nocturnas_descanso"))
                                horas_diurnas_asueto += self._parse_horas(horas_dict.get("horas_diurnas_asueto"))
                                horas_nocturnas_asueto += self._parse_horas(horas_dict.get("horas_nocturnas_asueto"))
                                if horas_dict.get("descripcion"): descripciones.append(
                                    str(horas_dict["descripcion"]).strip())

                    total_horas = sum([
                        horas_diurnas, horas_nocturnas,
                        horas_diurnas_descanso, horas_nocturnas_descanso,
                        horas_diurnas_asueto, horas_nocturnas_asueto
                    ])
                    if total_horas <= 0:
                        raise UserError("Debe ingresar al menos una hora extra.")

                    horas_dict = {
                        'horas_diurnas': horas_diurnas,
                        'horas_nocturnas': horas_nocturnas,
                        'horas_diurnas_descanso': horas_diurnas_descanso,
                        'horas_nocturnas_descanso': horas_nocturnas_descanso,
                        'horas_diurnas_asueto': horas_diurnas_asueto,
                        'horas_nocturnas_asueto': horas_nocturnas_asueto,
                        'descripcion': vals.get('description', ''),
                    }
                    monto_total = self._calcular_monto_horas_extras(empleado, horas_dict)
                    vals['monto'] = monto_total
                    # Guardar horas calculadas en vals para luego crear o actualizar
                    #vals.update(horas_dict)

                    # Validar para tipo COMISION, VIATICO o BONO que monto sea positivo
                    if tipo in [constants.ASIGNACION_COMISIONES, constants.ASIGNACION_VIATICOS,
                                constants.ASIGNACION_BONOS]:
                        monto = vals.get('monto', 0)
                        if monto is None or monto <= 0:
                            raise UserError(f"Para asignación tipo {tipo} el monto debe ser mayor que cero.")

                record = self.create_or_update_assignment(vals)
                records.append(record)
                _logger.info("Registro creado o actualizado (ID=%s) con vals finales: %s", record.id, record.read()[0])
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
