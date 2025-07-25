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

    comisiones = fields.Float(
        string='Total comisiones',
        compute='_compute_comisiones',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    total_overtime = fields.Float(
        string='Total Overtime',
        compute='_compute_overtime_total',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    viaticos = fields.Float(
        string='Viaticos',
        compute='_compute_viaticos',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    total_viaticos_a_pagar = fields.Float(
        string='Total viaticos',
        compute='_compute_total_viaticos_a_pagar',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    total_devengado = fields.Float(
        string='Total devengado',
        compute='_compute_total_devengado',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    isss = fields.Float(
        string='ISSS',
        compute='_compute_isss',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    isr = fields.Float(
        string='ISR',
        compute='_compute_isr',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    afp = fields.Float(
        string='AFP',
        compute='_compute_afp',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    otros = fields.Float(
        string='Otros',
        compute='_compute_otros_ded',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )
    bancos = fields.Float(
        string='Bancos',
        compute='_compute_bancos_ded',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )
    venta_empleados = fields.Float(
        string='Venta a empleados',
        compute='_compute_venta_empleados',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )
    prestamos_incoe = fields.Float(
        string='Prestamos INCOE',
        compute='_compute_prestamos_incoe',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )
    fsv = fields.Float(
        string='Fondo social de la vivienda',
        compute='_compute_fsv',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    total_descuentos = fields.Float(
        string='Total descuentos',
        compute='_compute_total_descuentos',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    quin1cena = fields.Selection(
        [('1', '1° Quincena'), ('2', '2° Quincena')],
        string='Quincena',
        compute='_compute_quincena',
        store=True
    )

    @api.depends('date_from')
    def _compute_quincena(self):
        for record in self:
            if record.date_from:
                record.quin1cena = '1' if record.date_from.day <= 15 else '2'
            else:
                record.quin1cena = False

    @api.depends('worked_days_line_ids.number_of_days')
    def _compute_worked_days_total(self):
        for record in self:
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
    def _compute_viaticos(self):
        for record in self:
            viaticos_lines = record.line_ids.filtered(lambda l: l.code == 'VIATICOS')
            record.viaticos = sum(viaticos_lines.mapped('amount'))

    @api.depends('viaticos', 'total_overtime')
    def _compute_total_viaticos_a_pagar(self):
        for record in self:
            record.total_viaticos_a_pagar = record.viaticos + record.total_overtime

    @api.depends('line_ids.amount')
    def _compute_comisiones(self):
        for record in self:
            comisiones_lines = record.line_ids.filtered(lambda l: l.code == 'COMISION')
            record.comisiones = sum(comisiones_lines.mapped('amount'))

    @api.depends('viaticos', 'total_viaticos_a_pagar')
    def _compute_total_devengado(self):
        for record in self:
            record.total_devengado = record.comisiones + record.total_viaticos_a_pagar

    @api.depends('line_ids.amount')
    def _compute_isr(self):
        for record in self:
            overtime_lines = record.line_ids.filtered(lambda l: l.code == 'ISR')
            record.isr = abs(sum(overtime_lines.mapped('amount')))

    @api.depends('line_ids.amount')
    def _compute_afp(self):
        for record in self:
            overtime_lines = record.line_ids.filtered(lambda l: l.code == 'AFP')
            record.afp = abs(sum(overtime_lines.mapped('amount')))

    @api.depends('line_ids.amount')
    def _compute_isss(self):
        for record in self:
            overtime_lines = record.line_ids.filtered(lambda l: l.code == 'ISSS')
            record.isss = abs(sum(overtime_lines.mapped('amount')))

    @api.depends('line_ids.amount')
    def _compute_otros_ded(self):
        for record in self:
            otros_lines = record.line_ids.filtered(lambda l: l.code == 'OTROS')
            record.otros = abs(sum(otros_lines.mapped('amount')))

    @api.depends('line_ids.amount')
    def _compute_bancos_ded(self):
        for record in self:
            bancos_lines = record.line_ids.filtered(lambda l: l.code == 'BANCO')
            record.bancos = abs(sum(bancos_lines.mapped('amount')))

    @api.depends('line_ids.amount')
    def _compute_venta_empleados(self):
        for record in self:
            venta_empleados_lines = record.line_ids.filtered(lambda l: l.code == 'VENTA_EMPLEADOS')
            record.venta_empleados = abs(sum(venta_empleados_lines.mapped('amount')))

    @api.depends('line_ids.amount')
    def _compute_prestamos_incoe(self):
        for record in self:
            prestamos_lines = record.line_ids.filtered(lambda l: l.code == 'PRESTAMOS')
            record.prestamos_incoe = abs(sum(prestamos_lines.mapped('amount')))

    @api.depends('line_ids.amount')
    def _compute_fsv(self):
        for record in self:
            fsv_lines = record.line_ids.filtered(lambda l: l.code == 'FSV')
            record.fsv = abs(sum(fsv_lines.mapped('amount')))

    @api.depends('isss', 'isr', 'afp', 'otros', 'bancos', 'fsv', 'prestamos_incoe', 'venta_empleados', 'total_viaticos_a_pagar')
    def _compute_total_descuentos(self):
        for record in self:
            record.total_descuentos = record.isss + record.isr + record.afp + record.otros + record.bancos + record.fsv + record.prestamos_incoe + record.venta_empleados + record.total_viaticos_a_pagar

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
