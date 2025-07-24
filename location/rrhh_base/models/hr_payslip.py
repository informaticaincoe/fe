from odoo import models, api, _
from odoo.exceptions import UserError
import logging
import base64

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

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
