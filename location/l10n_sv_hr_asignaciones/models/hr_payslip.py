from odoo import models, api, fields
import logging
from odoo.tools import float_round
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Intentamos importar constantes definidas en un módulo utilitario común.
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
        """
        Sobrescribimos el método create para agregar asignaciones salariales
        automáticamente justo después de crear el recibo de nómina.
        """
        _logger.info(f"Create de Asignaciones")
        # Guardar el ID del payslip en el contexto para usarlo en la asignación
        res = super().create(vals)
        res._agregar_asignaciones_salario()
        return res

    def compute_sheet(self):
        """
        Sobrescribe el cálculo de nómina (`Compute Sheet`) para incluir
        las asignaciones antes del cálculo final.
        """
        _logger.info(f"compute_sheet() de Asignaciones")
        for slip in self:
            slip._agregar_asignaciones_salario()
        return super().compute_sheet()

    def _agregar_asignaciones_salario(self):
        """
        Método principal que integra asignaciones salariales al recibo de nómina,
        como comisiones, viáticos, bonos y horas extra. También elimina entradas
        anteriores incluso si la asignación fue eliminada.
        """
        tipos_asignacion = [
            constants.ASIGNACION_COMISIONES.upper(),
            constants.ASIGNACION_VIATICOS.upper(),
            constants.ASIGNACION_BONOS.upper(),
            constants.ASIGNACION_HORAS_EXTRA.upper(),
            constants.DEVOLUCION_RENTA_CODE.upper(),
        ]

        _logger.info("ASIGNACIONES %s", tipos_asignacion)

        for slip in self:
            # Buscar los tipos de entrada hr.payslip.input.type según los códigos en la lista
            tipos_inputs = self.env['hr.payslip.input.type'].search([
                ('code', 'in', tipos_asignacion)
            ])

            _logger.info("tipos_inputs %s", tipos_inputs)

            # Eliminar entradas anteriores que sean de los tipos definidos
            entradas_a_borrar = slip.input_line_ids.filtered(lambda l: l.input_type_id in tipos_inputs)
            if entradas_a_borrar:
                _logger.info("Eliminando %s líneas de input antiguas", len(entradas_a_borrar))
                entradas_a_borrar.unlink()

            contract = slip.contract_id
            is_professional = contract.wage_type == constants.SERVICIOS_PROFESIONALES
            _logger.info("Contrato tipo '%s'. ¿Es servicios profesionales? %s", contract.wage_type, is_professional)

            # Si el contrato es de servicios profesionales, excluimos comisiones
            tipos_asignacion_final = tipos_asignacion.copy()
            if is_professional and constants.ASIGNACION_COMISIONES.upper() in tipos_asignacion_final:
                tipos_asignacion_final.remove(constants.ASIGNACION_COMISIONES.upper())
                _logger.info("Contrato de servicios profesionales: se omite asignación de COMISIONES")

            #Ahora procesamos cada tipo normalmente
            for tipo in tipos_asignacion_final:
                # Buscar el tipo de entrada usando el campo técnico 'code', evitando dependencia de XML ID
                # input_type = self.env.ref(f'l10n_sv_hr_asignaciones.{xml_id}', raise_if_not_found=False)
                input_type = self.env['hr.payslip.input.type'].search([('code', '=', tipo)], limit=1)
                if not input_type:
                    _logger.warning(f"[{tipo}] Tipo de entrada '{tipo}' no encontrado, se omite.")
                    continue

                company_id = self.env.company.id or slip.company_id.id

                # 1. Liberar asignaciones previas
                asignaciones_previas = self.env['hr.salary.assignment'].search([
                    ('payslip_id', '=', slip.id),
                    ('tipo', '=', tipo),
                    ('company_id', '=', company_id),
                ])
                asignaciones_previas.write({'payslip_id': False})
                _logger.info(f"[{tipo}] Asignaciones previas liberadas: {len(asignaciones_previas)}")

                # 2. Buscar asignaciones actuales dentro del período de pago
                asignaciones = self.env['hr.salary.assignment'].search([
                    ('employee_id', '=', slip.employee_id.id),
                    ('tipo', '=', tipo),
                    ('payslip_id', '=', False),
                    ('periodo', '>=', slip.date_from),
                    ('periodo', '<=', slip.date_to),
                    ('company_id', '=', company_id),
                ])
                _logger.info(f"[{tipo}] Asignaciones encontradas: {len(asignaciones)}")

                # 3. Crear líneas input y marcar como procesadas
                for asignacion in asignaciones:
                    slip.input_line_ids.create({
                        'payslip_id': slip.id,
                        'input_type_id': input_type.id,
                        'amount': float_round(asignacion.monto, precision_digits=2),
                        'name': asignacion.description or tipo.title(),
                        # 'company_id': company_id,
                    })
                    asignacion.payslip_id = slip.id  # Marcamos como ya utilizada en este recibo
                    _logger.info(f"[{tipo}] Asignación {asignacion.id} aplicada con monto: {asignacion.monto}")

    def action_descargar_plantilla(self):
        attachment = self.env['ir.attachment'].search([
            ('name', '=', 'plantilla_asignaciones.xlsx'),
            ('mimetype', '=', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        ], limit=1)

        if not attachment:
            raise UserError("No se encontró la plantilla de asistencia.")

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

