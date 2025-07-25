from odoo import models, api, _, fields
from odoo.exceptions import UserError
import logging
import base64

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    employee_name = fields.Char(
        string='Employee Name',
        related='employee_id.name',
        store=True,
        readonly=True
    )

    department_name = fields.Char(
        string='Department Name',
        related='employee_id.department_id.complete_name',
        store=True,
        readonly=True
    )

    total_overtime = fields.Float(
        string='Total Overtime',
        compute='_compute_overtime_total',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    total_viaticos = fields.Float(
        string='Total Viaticos',
        compute='_compute_viaticos_total',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    total_worked_days = fields.Float(
        string='Total Worked Days',
        compute='_compute_worked_days_total',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    total_worked_hours = fields.Float(
        string='Total Worked Hours',
        compute='_compute_worked_hours_total',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    total_viaticos_a_pagar = fields.Float(
        string='Total viaticos',
        compute='_compute_total_viaticos_a_pagar',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    @api.depends('worked_days_line_ids.number_of_days')
    def _compute_worked_days_total(self):
        for record in self:
            # Sumar los días trabajados de la tabla 'hr.payslip.worked_days'
            total_days = sum(record.worked_days_line_ids.mapped('number_of_days'))
            record.total_worked_days = total_days

    @api.depends('worked_days_line_ids.number_of_hours')
    def _compute_worked_hours_total(self):
        for record in self:
            total_hours = sum(record.worked_days_line_ids.mapped('number_of_hours'))
            record.total_worked_hours = total_hours

    @api.depends('line_ids.amount')
    def _compute_overtime_total(self):
        for record in self:
            overtime_lines = record.line_ids.filtered(lambda l: l.code == 'OVERTIME')
            record.total_overtime = sum(overtime_lines.mapped('amount'))

    @api.depends('line_ids.amount')
    def _compute_viaticos_total(self):
        for record in self:
            viaticos_lines = record.line_ids.filtered(lambda l: l.code == 'VIATICOS')
            record.total_viaticos = sum(viaticos_lines.mapped('amount'))

    @api.depends('total_viaticos', 'total_overtime')
    def _compute_total_viaticos_a_pagar(self):
        for record in self:
            # Calcular el total de viáticos a pagar (solo viáticos)
            record.total_viaticos_a_pagar = record.total_viaticos  # Se puede agregar lógica adicional si es necesario

    def action_send_payslip_email(self):
        self.ensure_one()

        # Obtener plantilla
        template = self.env.ref('rrhh_base.rrhh_email_template_payslip', raise_if_not_found=False)
        rendered_body = template._render_field('body_html', [self.id])[self.id]
        _logger.warning("CUERPO RENDERIZADO:\n%s", rendered_body)


        if not template:
            raise UserError("No se encontró la plantilla de correo para la boleta de pago.")
        if not self.employee_id.work_email:
            raise UserError("El empleado no tiene un correo configurado.")

        _logger.warning("TYPE CHECK >> about to resolve report: %s", type('rrhh_base.hr_payslip_report'))

        report = self.env.ref('rrhh_base.hr_payslip_report')  #

        _logger.warning("RESOLVED REPORT: %s | TYPE: %s", report, type(report))
        # Renderizar PDF
        report_name = 'rrhh_base.report_boleta_pago_template'
        pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(report_name, [self.id])

        filename = f"Boleta_{self.employee_id.name.replace(' ', '_')}_{self.date_to}.pdf"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'hr.payslip',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        # Enviar correo
        try:
            template.send_mail(self.id, force_send=True, email_values={
                'attachment_ids': [(6, 0, [attachment.id])]
            })
            _logger.info("Correo enviado a %s con archivo %s", self.employee_id.work_email, filename)
        except Exception as e:
            raise UserError(_("Error al enviar el correo: %s") % str(e))
