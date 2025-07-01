from odoo import models, api, fields
import logging
from odoo.tools import float_round
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo common_utils [Asignaciones -payslip]")
except ImportError as e:
    _logger.error(f"Error al importar 'common_utils': {e}")
    constants = None

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    @api.model
    def create(self, vals):
        _logger.info(f"Create de Asignaciones")
        # Guardar el ID del payslip en el contexto para usarlo en la asignación
        res = super().create(vals)
        res._agregar_asignaciones_salario()
        return res

    def compute_sheet(self):
        _logger.info(f"compute_sheet() de Asignaciones")
        for slip in self:
            slip._agregar_asignaciones_salario()
        return super().compute_sheet()

    def _agregar_asignaciones_salario(self):
        tipos_asignacion = {
            constants.ASIGNACION_COMISIONES.upper(): 'input_type_comision',
            constants.ASIGNACION_VIATICOS.upper(): 'input_type_viaticos',
            constants.ASIGNACION_BONOS.upper(): 'input_type_bonus',
        }

        for tipo, xml_id in tipos_asignacion.items():
            input_type = self.env.ref(f'l10n_sv_hr_asignaciones.{xml_id}', raise_if_not_found=False)
            if not input_type:
                _logger.warning(f"[{tipo}] Tipo de entrada '{xml_id}' no encontrado, se omite.")
                continue

            for slip in self:
                # 1. Eliminar líneas anteriores
                entradas_previas = slip.input_line_ids.filtered(lambda i: i.input_type_id == input_type)
                entradas_previas.unlink()
                _logger.info(f"[{tipo}] Entradas previas eliminadas: {len(entradas_previas)}")

                # 2. Liberar asignaciones previas
                asignaciones_previas = self.env['hr.salary.assignment'].search([
                    ('payslip_id', '=', slip.id),
                    ('tipo', '=', tipo),
                ])
                asignaciones_previas.write({'payslip_id': False})
                _logger.info(f"[{tipo}] Asignaciones previas liberadas: {len(asignaciones_previas)}")

                # 3. Buscar asignaciones actuales dentro del período
                asignaciones = self.env['hr.salary.assignment'].search([
                    ('employee_id', '=', slip.employee_id.id),
                    ('tipo', '=', tipo),
                    ('payslip_id', '=', False),
                    ('periodo', '>=', slip.date_from),
                    ('periodo', '<=', slip.date_to),
                ])
                _logger.info(f"[{tipo}] Asignaciones encontradas: {len(asignaciones)}")

                # 4. Crear líneas input y marcar como procesadas
                for asignacion in asignaciones:
                    slip.input_line_ids.create({
                        'payslip_id': slip.id,
                        'input_type_id': input_type.id,
                        'amount': asignacion.monto,
                        'name': asignacion.description or tipo.title(),
                    })
                    asignacion.payslip_id = slip.id
                    _logger.info(f"[{tipo}] Asignación {asignacion.id} aplicada con monto: {asignacion.monto}")

    # def compute_sheet(self):
    #     _logger.info(">>> Inicio compute_sheet personalizado para horas extra")
    #     res = super().compute_sheet()
    #
    #     overtime_input_type = self.env.ref('l10n_sv_hr_asignaciones.input_type_overtime', raise_if_not_found=False)
    #     if not overtime_input_type:
    #         _logger.warning("Tipo de entrada 'Horas Extra' (OVERTIME) no encontrado. Se omite procesamiento.")
    #         return res
    #
    #     for slip in self:
    #         _logger.info(f"Procesando nómina para: {slip.employee_id.name} (ID: {slip.id})")
    #         # Eliminar entradas anteriores con código OVERTIME
    #         entradas_anteriores = slip.input_line_ids.filtered(lambda l: l.input_type_id == overtime_input_type)
    #         cantidad_entradas = len(entradas_anteriores)
    #         if cantidad_entradas > 0:
    #             _logger.info(f"Eliminando {cantidad_entradas} entradas anteriores de horas extra")
    #             entradas_anteriores.unlink()
    #         else:
    #             _logger.info("No se encontraron entradas anteriores de horas extra para eliminar")
    #
    #         # Obtener línea OVERTIME desde worked_days
    #         overtime_line = slip.worked_days_line_ids.filtered(lambda l: l.code == 'OVERTIME')
    #         if not overtime_line:
    #             _logger.info("No se encontraron horas extra (worked_days_line_ids) para este slip")
    #             continue
    #
    #         horas = overtime_line.number_of_hours
    #         tarifa_hora = slip.contract_id.wage / 220 if slip.contract_id and slip.contract_id.wage else 0.0
    #         total = horas * tarifa_hora * 2.0  # factor de recargo 2x
    #
    #         _logger.info(
    #             f"Total horas extra detectadas: {horas:.2f} horas, tarifa hora: {tarifa_hora:.4f}, total calculado: ${total:.2f}")
    #
    #         # Crear entrada con descripción clara y monto redondeado
    #         slip.input_line_ids.create({
    #             'payslip_id': slip.id,
    #             'input_type_id': overtime_input_type.id,
    #             'name': f'Horas Extra - {horas:.2f} horas',
    #             'amount': float_round(total, precision_digits=2),
    #         })
    #         _logger.info(
    #             f"Entrada de horas extra creada para {slip.employee_id.name}: {float_round(total, 2):.2f} ({horas:.2f} horas)")
    #
    #     _logger.info("<<< Fin compute_sheet personalizado para horas extra")
    #     return res
