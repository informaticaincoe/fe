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

    @api.model_create_multi
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
            constants.ASIGNACION_HORAS_EXTRA.upper(): 'input_type_overtime',
        }

        for tipo, xml_id in tipos_asignacion.items():
            input_type = self.env.ref(f'l10n_sv_hr_asignaciones.{xml_id}', raise_if_not_found=False)
            if not input_type:
                _logger.warning(f"[{tipo}] Tipo des entrada '{xml_id}' no encontrado, se omite.")
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
                        'amount': float_round(asignacion.monto, precision_digits=2),
                        'name': asignacion.description or tipo.title(),
                    })
                    asignacion.payslip_id = slip.id
                    _logger.info(f"[{tipo}] Asignación {asignacion.id} aplicada con monto: {asignacion.monto}")
