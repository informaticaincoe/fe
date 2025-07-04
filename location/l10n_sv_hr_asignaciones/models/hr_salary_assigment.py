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
        ('OVERTIME', 'Hora extra'),
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

    @api.model_create_multi
    def create(self, vals_list):
        records = []
        empleado = None
        codigo_empleado = None
        contrato = None
        empresa = None
        dias_mes = 30
        horas_laboradas = 8
        recargo = constants.RECARGO_HE

        for vals in vals_list:
            try:
                _logger.info("=== Entradas vals: %s ===", vals)

                tipo = vals.get("tipo", "OVERTIME").upper()
                vals["tipo"] = tipo
                _logger.info("Procesando asignación tipo: %s", tipo)

                if tipo == constants.HORAS_EXTRAS.upper() or tipo == constants.ASIGNACION_VIATICOS.upper():
                    codigo_empleado = vals.get('codigo_empleado')
                    if not codigo_empleado:
                        raise UserError(
                            "Debe proporcionar el código de empleado (codigo_empleado) para importar la asignación.")

                    codigo_empleado = str(codigo_empleado).strip()
                    empleado = self.env['hr.employee'].search([('barcode', '=', codigo_empleado)], limit=1)
                    if not empleado:
                        raise UserError(f"No se encontró un empleado con código: {codigo_empleado}")

                    vals['employee_id'] = empleado.id

                    _logger.info("Procesando asignación de horas extra")

                    if not empleado.contract_id:
                        raise UserError("No se encontró contrato para calcular horas extra.")

                    contrato = empleado.contract_id

                    # Convertir el salario a mensual
                    # salario_base = empleado.contract_id.wage
                    salario_base = contrato.wage
                    if contrato.schedule_pay in ['bi-weekly', 'semi-monthly']:
                        salario_base *= 2
                    elif contrato.schedule_pay == 'weekly':
                        salario_base *= 4.33

                    salario_hora = round((salario_base / dias_mes / horas_laboradas), 4)  # Jornada de 240h/mes
                    _logger.info("Salario hora calculado: %s", salario_hora)

                    # Obtener horas desde vals
                    horas_diurnas = self._parse_horas(vals.get('horas_diurnas', 0.0))
                    horas_nocturnas = self._parse_horas(vals.get('horas_nocturnas', 0.0))
                    horas_diurnas_descanso = self._parse_horas(vals.get('horas_diurnas_descanso', 0.0))
                    horas_nocturnas_descanso = self._parse_horas(vals.get('horas_nocturnas_descanso', 0.0))
                    horas_diurnas_asueto = self._parse_horas(vals.get('horas_diurnas_asueto', 0.0))
                    horas_nocturnas_asueto = self._parse_horas(vals.get('horas_nocturnas_asueto', 0.0))
                    _logger.info("Horas diurnas: %s, horas nocturnas: %s", horas_diurnas, horas_nocturnas)

                    # Validar que al menos una hora haya sido ingresada
                    total_horas = (
                            horas_diurnas + horas_nocturnas +
                            horas_diurnas_descanso + horas_nocturnas_descanso +
                            horas_diurnas_asueto + horas_nocturnas_asueto
                    )
                    if total_horas <= 0:
                        raise UserError("Debe ingresar al menos una hora extra.")

                    # Obtener empresa del empleado
                    empresa = empleado.company_id
                    porcentaje_base = empresa.overtime_percentage or 1.0
                    porcentaje_nocturno = salario_hora * (porcentaje_base / 100)  # 25% recargo nocturno

                    valor_config = config_utils.get_config_value(self.env, 'porcentaje_horas_extras', empleado.company_id.id)
                    porcentaje_descanso = 0.0
                    try:
                        valor_config_float = float(valor_config)
                        porcentaje_descanso = (valor_config_float or 50) / 100.0
                    except (TypeError, ValueError):
                        porcentaje_descanso = 0.0
                    porcentaje_dia_descanso = salario_hora * porcentaje_descanso # Valor por defecto: 50%

                    # Cálculo monto según fórmulas
                    monto_total = 0.0

                    # Hora extra diurna 200%
                    monto_total += round(horas_diurnas * salario_hora * recargo, 4)

                    # Hora extra nocturna 250%
                    monto_total += round(horas_nocturnas * (salario_hora + porcentaje_nocturno) * recargo, 4)

                    # Hora extra diurna en día de descanso 400% (2 * salario + 50% salario)
                    monto_total += round(horas_diurnas_descanso * (salario_hora * recargo + porcentaje_dia_descanso), 4)

                    # Hora extra nocturna en día de descanso 475%
                    unidad_nocturna_descanso = (salario_hora + porcentaje_nocturno) * recargo + (
                                (salario_hora + porcentaje_nocturno) * porcentaje_dia_descanso)
                    monto_total += round(horas_nocturnas_descanso * unidad_nocturna_descanso, 4)

                    # Hora diurna en día de asueto/festivo 500%
                    monto_total += round(horas_diurnas_asueto * salario_hora * constants.RECARGO_HED_FEST, 4)

                    # Hora nocturna en día de asueto/festivo 600%
                    monto_total += round(horas_nocturnas_asueto * (salario_hora + porcentaje_nocturno) * constants.RECARGO_HEN_FEST,4)

                    # Asignar valores calculados
                    vals['monto'] = round(monto_total, 2)  # vals['monto'] = total_monto
                    vals['description'] = vals.get('description', '')
                    _logger.info("Vals actualizado con monto y description: %s", {
                        'monto': vals['monto'],
                        'description': vals['description'],
                    })
                else:
                    # Para otros tipos que no sean horas extra
                    if not vals.get("monto"):
                        _logger.error("No se proporcionó 'monto' para tipo distinto de horas extra")
                        raise UserError("Debe indicar el monto para este tipo de asignación.")

                record = super().create(vals)
                _logger.info("Registro creado (ID=%s) con vals finales: %s", record.id, record.read()[0])
                records.append(record)
            except Exception as e:
                _logger.error("Error al crear asignación con datos %s: %s", vals, str(e))
                raise UserError(_("Error al procesar asignación para el código '%s': %s") % (vals.get('codigo_empleado', 'N/D'), str(e)))
        return self.browse([r.id for r in records])

    def action_descargar_plantilla(self):
        # Busca el archivo adjunto con la plantilla
        attachment = self.env['ir.attachment'].search([('name', '=', 'Plantilla de Horas extras')], limit=1)
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

        if not valor:
            _logger.info("Valor vacío o nulo recibido, se interpreta como 0.0 horas.")
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
