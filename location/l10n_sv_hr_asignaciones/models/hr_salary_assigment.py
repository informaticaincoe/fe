from odoo import models, fields, api, _
from datetime import datetime, timedelta
from odoo.exceptions import UserError
import logging
import unicodedata
import re

_logger = logging.getLogger(__name__)

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

    employee_id = fields.Many2one('hr.employee', string='Empleado')
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

    horas_diurnas = fields.Char("Horas extras diurnas", invisible=False)
    horas_nocturnas = fields.Char("Horas extras nocturnas", invisible=False)
    horas_diurnas_descanso = fields.Char("Horas extras diurnas dia descanso", invisible=False)
    horas_nocturnas_descanso = fields.Char("Horas extras nocturnas dia descanso", invisible=False)
    horas_diurnas_asueto = fields.Char("Horas diurnas dia de asueto", invisible=False)
    horas_nocturnas_asueto = fields.Char("Horas nocturnas dia de asueto", invisible=False)

    codigo_empleado = fields.Char(string="Código de empleado", store=False)

    def unlink(self):
        for asignacion in self:
            payslip = asignacion.payslip_id
            if payslip and payslip.state in ['done', 'paid']:
                raise UserError(_("No puede eliminar la asignación porque está vinculada a una boleta que ya fue procesada o pagada."))
        return super(HrSalaryAssignment, self).unlink()

    # @api.model
    # def create_or_update_assignment(self, vals):
    #     existing = self.search([
    #         ('employee_id', '=', vals.get('employee_id')),
    #         ('tipo', '=', vals.get('tipo')),
    #         ('periodo', '=', vals.get('periodo')),
    #     ], limit=1)
    #
    #     def _as_float(val):
    #         try:
    #             return round(float(val or 0.0), 4)
    #         except Exception:
    #             return 0.0
    #
    #     def _horas_iguales(v1, v2):
    #         return _as_float(v1) == _as_float(v2)
    #
    #     # Convertir horas a float para comparar correctamente
    #     for campo in [
    #         'horas_diurnas', 'horas_nocturnas',
    #         'horas_diurnas_descanso', 'horas_nocturnas_descanso',
    #         'horas_diurnas_asueto', 'horas_nocturnas_asueto'
    #     ]:
    #         if campo in vals:
    #             try:
    #                 vals[campo] = round(float(vals[campo]), 4)
    #             except Exception:
    #                 vals[campo] = 0.0
    #
    #     if existing:
    #         # Verificar si el registro existente es idéntico al nuevo
    #         iguales = (
    #                 _horas_iguales(existing.horas_diurnas, vals.get('horas_diurnas')) and
    #                 _horas_iguales(existing.horas_nocturnas, vals.get('horas_nocturnas')) and
    #                 _horas_iguales(existing.horas_diurnas_descanso, vals.get('horas_diurnas_descanso')) and
    #                 _horas_iguales(existing.horas_nocturnas_descanso, vals.get('horas_nocturnas_descanso')) and
    #                 _horas_iguales(existing.horas_diurnas_asueto, vals.get('horas_diurnas_asueto')) and
    #                 _horas_iguales(existing.horas_nocturnas_asueto, vals.get('horas_nocturnas_asueto')) and
    #                 _as_float(existing.monto) == _as_float(vals.get('monto'))
    #         )
    #         desc_actual = (existing.description or '').strip()
    #         desc_nueva = (vals.get('description') or '').strip()
    #         desc_contiene = desc_nueva in desc_actual or desc_actual in desc_nueva
    #
    #         if iguales and desc_contiene:
    #             _logger.info("Asignación idéntica ya existe (ignorada): %s", existing)
    #             return existing  # Ignorar duplicado idéntico
    #
    #         # Si no son idénticos, consolidar sumando montos y concatenando descripciones
    #         monto_total = _as_float(existing.monto) + _as_float(vals.get('monto'))
    #
    #         if desc_nueva and desc_nueva not in desc_actual:
    #             descripcion_final = f"{desc_actual} | {desc_nueva}".strip(" |")
    #         else:
    #             descripcion_final = desc_actual
    #
    #         update_vals = {
    #             'horas_diurnas': vals.get('horas_diurnas', existing.horas_diurnas),
    #             'horas_nocturnas': vals.get('horas_nocturnas', existing.horas_nocturnas),
    #             'horas_diurnas_descanso': vals.get('horas_diurnas_descanso', existing.horas_diurnas_descanso),
    #             'horas_nocturnas_descanso': vals.get('horas_nocturnas_descanso', existing.horas_nocturnas_descanso),
    #             'horas_diurnas_asueto': vals.get('horas_diurnas_asueto', existing.horas_diurnas_asueto),
    #             'horas_nocturnas_asueto': vals.get('horas_nocturnas_asueto', existing.horas_nocturnas_asueto),
    #             'monto': monto_total,
    #             'description': descripcion_final,
    #         }
    #
    #         _logger.info("Actualizando asignación consolidando diferencias en ID %s con valores: %s", existing.id, update_vals)
    #         existing.write(update_vals)
    #         return existing
    #     else:
    #         return super(HrSalaryAssignment, self).create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        records = []
        dias_mes = 30
        horas_laboradas = 8
        empleado = None

        valid_tipos = [x[0] for x in self._fields['tipo'].selection]

        for vals in vals_list:
            empleado = None
            try:
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

                if tipo == constants.ASIGNACION_HORAS_EXTRA.upper() or any(
                        vals.get(campo) not in [None, '', '0', 0] for campo in [
                            'horas_diurnas', 'horas_nocturnas',
                            'horas_diurnas_descanso', 'horas_nocturnas_descanso',
                            'horas_diurnas_asueto', 'horas_nocturnas_asueto'
                        ]):
                    _logger.info("=== Entradas vals: %s ===", vals)

                    contrato = empleado.contract_id
                    if not contrato:
                        raise UserError("No se encontró contrato para el empleado.")

                    salario_base = float(contrato.wage or 0.0)
                    if contrato.schedule_pay in ['bi-weekly', 'semi-monthly']:
                        salario_base *= 2
                    elif contrato.schedule_pay == 'weekly':
                        salario_base *= 4.33

                    salario_hora = round((salario_base / dias_mes) / horas_laboradas, 4)
                    _logger.info("Salario hora calculado: %.4f", salario_hora)

                    # Convertir y actualizar campos de horas como float
                    horas_diurnas = self._parse_horas(vals.get('horas_diurnas'))
                    horas_nocturnas = self._parse_horas(vals.get('horas_nocturnas'))
                    horas_diurnas_descanso = self._parse_horas(vals.get('horas_diurnas_descanso'))
                    horas_nocturnas_descanso = self._parse_horas(vals.get('horas_nocturnas_descanso'))
                    horas_diurnas_asueto = self._parse_horas(vals.get('horas_diurnas_asueto'))
                    horas_nocturnas_asueto = self._parse_horas(vals.get('horas_nocturnas_asueto'))

                    # Guardar los valores convertidos para evitar errores posteriores
                    vals['horas_diurnas'] = horas_diurnas
                    vals['horas_nocturnas'] = horas_nocturnas
                    vals['horas_diurnas_descanso'] = horas_diurnas_descanso
                    vals['horas_nocturnas_descanso'] = horas_nocturnas_descanso
                    vals['horas_diurnas_asueto'] = horas_diurnas_asueto
                    vals['horas_nocturnas_asueto'] = horas_nocturnas_asueto

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
                        recargo_he_diurna = float(
                            config_utils.get_config_value(self.env, 'he_diurna', empleado.company_id.id) or 0.0)
                        recargo_he_nocturna = float(
                            config_utils.get_config_value(self.env, 'he_nocturna', empleado.company_id.id) or 0.0)
                        recargo_he_diurna_dia_descanso = float(
                            config_utils.get_config_value(self.env, 'he_diurna_dia_descanso',
                                                          empleado.company_id.id) or 0.0)
                        recargo_he_nocturno_dia_descanso = float(
                            config_utils.get_config_value(self.env, 'he_nocturna_dia_descanso',
                                                          empleado.company_id.id) or 0.0)
                        recargo_he_diurna_dia_festivo = float(
                            config_utils.get_config_value(self.env, 'he_diurna_dia_festivo',
                                                          empleado.company_id.id) or 0.0)
                        recargo_he_nocturna_dia_festivo = float(
                            config_utils.get_config_value(self.env, 'he_nocturna_dia_festivo',
                                                          empleado.company_id.id) or 0.0)

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
                    raise UserError(
                        "Debe seleccionar un tipo de asignación (Ej: Horas extra, Viáticos, Comisión, etc.).")

                # Validación: periodo obligatorio
                if not vals.get('periodo'):
                    raise UserError("Debe seleccionar el periodo para la asignación.")

                # Validación: monto no puede ser cero
                if vals.get('monto', 0.0) <= 0:
                    raise UserError("El monto no puede ser cero. Verifique los datos ingresados.")

                record = super().create(vals)

                _logger.info("Registro creado o actualizado (ID=%s) con vals finales: %s", record.id, record.read()[0])
                records.append(record)

            except Exception as e:
                _logger.error("Error al crear asignación con datos %s: %s", vals, str(e))
                raise UserError(
                    _("Error al procesar asignación para el empleado '%s' (código: %s): %s") % (
                        empleado.name, empleado.barcode, str(e))
                )

        return self.browse([r.id for r in records])

    def action_descargar_plantilla(self):
        # Busca el archivo adjunto con la plantilla
        attachment = self.env['ir.attachment'].search([('name', '=', 'Plantilla de Asignaciones')], limit=1)
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
