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
        string='Dias laborados',
        compute='_compute_worked_days_total',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    total_worked_hours = fields.Float(
        string='Horas laboradas',
        compute='_compute_worked_hours_total',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    basic_wage = fields.Float(
        string="Salario a pagar"
    )

    employee_name = fields.Char(
        string="Empleado"
    )

    department_name = fields.Char(
        string="Departamento"
    )

    salario_pagar = fields.Char(
        string='Salario a pagar',
        compute='_compute_salario_pagar',
        store=False,
        readonly=True
    )

    comisiones = fields.Float(
        string='Comisiones',
        compute='_compute_comisiones',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    total_overtime = fields.Float(
        string='Horas extras',
        compute='_compute_overtime_total',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    viaticos = fields.Float(
        string='Viaticos ordinarios',
        compute='_compute_viaticos',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    bonos = fields.Float(
        string='Bonos',
        compute='_compute_bonos',
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
        string='AFP crecer',
        compute='_compute_afp',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    afp_confia = fields.Float(
        string='AFP Confia',
        compute='_compute_afp_confia',
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

    sueldo_liquido = fields.Float(
        string='Liquido a recibir',
        compute='_compute_sueldo_liquidido',
        readonly=True,
        store=False  # No se almacena en la base de datos
    )

    quin1cena = fields.Selection(
        [('1', '1° Quincena'), ('2', '2° Quincena')],
        string='Quincena',
        compute='_compute_quincena',
        store=True
    )

    vacaciones = fields.Float(
        string="Vacaciones",
        compute="_compute_vacaciones",
        readonly=True,
        store=False
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
            asistencia_lines = record.worked_days_line_ids.filtered(lambda l: l.name == 'Asistencia' or l.name == 'Vacaciones')
            insasistencia_injustificada_line = record.line_ids.filtered(lambda l: l.code == 'DESC_FALTA_SEPTIMO')
            inansistencia_injustificada_cantidad = sum(insasistencia_injustificada_line.mapped('quantity'))

            total_days = sum(asistencia_lines.mapped('number_of_days'))
            record.total_worked_days = total_days - inansistencia_injustificada_cantidad

    @api.depends('worked_days_line_ids.number_of_hours')
    def _compute_worked_hours_total(self):
        for record in self:
            asistencia_lines = record.worked_days_line_ids.filtered(lambda l: l.name == 'Asistencia' or l.name == 'Vacaciones')
            inasistencia_injustificada_lines = record.worked_days_line_ids.filtered(lambda l: l.name == 'Falta Injustificada')

            inansistencia_injustificada_horas = sum(inasistencia_injustificada_lines.mapped('number_of_hours'))

            total_hours = sum(asistencia_lines.mapped('number_of_hours'))
            record.total_worked_hours = total_hours - inansistencia_injustificada_horas

    @api.depends('line_ids.amount', 'basic_wage')
    def _compute_salario_pagar(self):
        for record in self:
            descuento_falta = sum(record.line_ids.filtered(lambda l: l.code == 'DESC_FALTA_SEPTIMO').mapped('amount'))
            salario_base = record.basic_wage or 0.0
            record.salario_pagar = round(salario_base - abs(descuento_falta), 2)

    @api.depends('line_ids.amount')
    def _compute_comisiones(self):
        for record in self:
            comisiones_lines = record.line_ids.filtered(lambda l: l.code == 'COMISION')
            record.comisiones = sum(comisiones_lines.mapped('amount'))

    @api.depends('line_ids.amount')
    def _compute_overtime_total(self):
        for record in self:
            overtime_lines = record.line_ids.filtered(lambda l: l.code == 'OVERTIME')
            record.total_overtime = sum(overtime_lines.mapped('amount'))

    @api.depends('line_ids.amount')
    def _compute_bonos(self):
        for record in self:
            bonos_lines = record.line_ids.filtered(lambda l: l.code == 'BONO')
            record.bonos = sum(bonos_lines.mapped('amount'))

    @api.depends('line_ids.amount')
    def _compute_viaticos(self):
        for record in self:
            viaticos_lines = record.line_ids.filtered(lambda l: l.code == 'VIATICO')
            record.viaticos = sum(viaticos_lines.mapped('amount')) + record.bonos

    @api.depends('viaticos', 'total_overtime')
    def _compute_total_viaticos_a_pagar(self):
        for record in self:
            record.total_viaticos_a_pagar = record.viaticos + record.total_overtime

    @api.depends('viaticos', 'total_viaticos_a_pagar', 'salario_pagar')
    def _compute_total_devengado(self):
        for record in self:
            record.total_devengado = record.total_viaticos_a_pagar + float(record.salario_pagar) + record.comisiones

    @api.depends('line_ids.amount')
    def _compute_isr(self):
        for record in self:
            overtime_lines = record.line_ids.filtered(lambda l: l.code == 'RENTA')
            record.isr = abs(sum(overtime_lines.mapped('amount')))

    @api.depends('line_ids.amount')
    def _compute_afp(self):
        for record in self:
            afp_lines = record.line_ids.filtered(lambda l: l.code == 'AFP')
            record.afp = abs(sum(afp_lines.mapped('amount')))

    @api.depends('line_ids.amount')
    def _compute_afp_confia(self):
        for record in self:
            afp_confia_lines = record.line_ids.filtered(lambda l: l.code == 'AFP_CONF')
            record.afp_confia = abs(sum(afp_confia_lines.mapped('amount')))

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
            record.total_descuentos = record.isss + record.isr + record.afp + record.otros + record.bancos + record.fsv + record.prestamos_incoe + record.venta_empleados

    @api.depends('total_devengado', 'total_descuentos')
    def _compute_sueldo_liquidido(self):
        for record in self:
            record.sueldo_liquido = record.total_devengado - record.total_descuentos

    @api.depends('line_ids.amount')
    def _compute_vacaciones(self):
        for record in self:
            vacaciones_lines = record.line_ids.filtered(lambda l: l.code == 'VACACIONES')
            record.vacaciones = abs(sum(vacaciones_lines.mapped('amount')))

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

        report = self.env.ref('rrhh_base.report_payslip')

        _logger.warning("RESOLVED REPORT: %s | TYPE: %s", report, type(report))
        # Renderizar PDF
        report_name = 'rrhh_base.report_boleta_pago_template'
        pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(report.report_name, [self.id])

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

