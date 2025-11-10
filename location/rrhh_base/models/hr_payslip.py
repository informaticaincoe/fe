from odoo import _, api, fields, models
import logging
from lxml import etree
from datetime import date
from email.utils import parseaddr, formataddr
import base64, re
try:
    import unicodedata
except Exception:
    unicodedata = None

_logger = logging.getLogger(__name__)
try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo constants [rrhh_base-hr_payslip]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # Catálogo de meses para filtros
    PERIOD_MONTHS = [
        ('01', 'enero'), ('02', 'febrero'), ('03', 'marzo'),
        ('04', 'abril'), ('05', 'mayo'), ('06', 'junio'),
        ('07', 'julio'), ('08', 'agosto'), ('09', 'septiembre'),
        ('10', 'octubre'), ('11', 'noviembre'), ('12', 'diciembre'),
    ]

    name = fields.Char(
        string='Employee Name',
        related='employee_id.name',
        store=False,
        readonly=True
    )

    complete_name = fields.Char(
        string='Department Name',
        related='employee_id.department_id.complete_name',
        store=False,
        readonly=True
    )

    total_worked_days = fields.Float(
        string='Dias laborados',
        compute='_compute_worked_days_total',
        readonly=True,
        store=False
    )

    total_worked_hours = fields.Float(
        string='Horas laboradas',
        compute='_compute_worked_hours_total',
        readonly=True,
        store=False
    )

    basic_wage = fields.Float(
        string="Salario a pagar"
    )

    employee_name = fields.Char(
        string="Empleado"
    )

    salario_pagar = fields.Float(
        string="Salario a pagar"
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
        store=False
    )

    total_overtime = fields.Float(
        string='Horas extras',
        compute='_compute_overtime_total',
        readonly=True,
        store=False
    )

    viaticos = fields.Float(
        string='Viaticos ordinarios',
        compute='_compute_viaticos',
        readonly=True,
        store=False
    )

    bonos = fields.Float(
        string='Bonos',
        compute='_compute_bonos',
        readonly=True,
        store=False
    )

    total_viaticos_a_pagar = fields.Float(
        string='Total viaticos',
        compute='_compute_total_viaticos_a_pagar',
        readonly=True,
        store=False
    )

    total_devengado = fields.Float(
        string='Total devengado',
        compute='_compute_total_devengado',
        readonly=True,
        store=False
    )

    isss = fields.Float(
        string='ISSS',
        compute='_compute_isss',
        readonly=True,
        store=False
    )

    isr = fields.Float(
        string='ISR',
        compute='_compute_isr',
        readonly=True,
        store=False
    )

    afp = fields.Float(
        string='AFP crecer',
        compute='_compute_afp',
        readonly=True,
        store=False
    )

    afp_confia = fields.Float(
        string='AFP Confia',
        compute='_compute_afp_confia',
        readonly=True,
        store=False
    )

    afp_IPSFA = fields.Float(
        string='INCAF',
        compute='_compute_afp_IPSFA',
        readonly=True,
        store=False
    )

    otros = fields.Float(
        string='Otros',
        compute='_compute_otros_ded',
        readonly=True,
        store=False
    )

    bancos = fields.Float(
        string='Bancos',
        compute='_compute_bancos_ded',
        readonly=True,
        store=False
    )

    venta_empleados = fields.Float(
        string='Venta a empleados',
        compute='_compute_venta_empleados',
        readonly=True,
        store=False
    )

    prestamos_incoe = fields.Float(
        string='Prestamos INCOE',
        compute='_compute_prestamos_incoe',
        readonly=True,
        store=False
    )

    fsv = fields.Float(
        string='Fondo social de la vivienda',
        compute='_compute_fsv',
        readonly=True,
        store=False
    )

    total_descuentos = fields.Float(
        string='Total descuentos',
        compute='_compute_total_descuentos',
        readonly=True,
        store=False
    )

    sueldo_liquido = fields.Float(
        string='Liquido a recibir',
        compute='_compute_sueldo_liquidido',
        readonly=True,
        store=False
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

    @api.depends('line_ids.amount')
    def _compute_vacaciones(self):
        """Suma de importes de líneas con code='VACACIONES'"""
        for record in self:
            vacaciones_lines = record.line_ids.filtered(lambda l: l.code == constants.SUM_VACACIONES.upper())
            record.vacaciones = abs(sum(vacaciones_lines.mapped('amount')))

    @api.depends('date_from')
    def _compute_quincena(self):
        """Determina si es la 1a o 2a quincena en base al día de date_from."""
        for record in self:
            if record.date_from:
                record.quin1cena = '1' if record.date_from.day <= 15 else '2'
            else:
                record.quin1cena = False

    @api.depends('worked_days_line_ids.number_of_days')
    def _compute_worked_days_total(self):
        """Suma número de días trabajados o si es vacaciones el numero de dias de vacacion"""
        for record in self:
            asistencia_lines = record.worked_days_line_ids.filtered(
                lambda l: l.name in (constants.SUM_ASISTENCIA, constants.SUM_VACACIONES)
            )

            total_days = sum(asistencia_lines.mapped('number_of_days'))
            record.total_worked_days = total_days

    @api.depends('worked_days_line_ids.number_of_hours')
    def _compute_worked_hours_total(self):
        """Suma horas de líneas 'Asistencia' o 'Vacaciones'."""
        for record in self:
            asistencia_lines = record.worked_days_line_ids.filtered(
                lambda l: l.name == constants.SUM_ASISTENCIA or l.name == constants.SUM_VACACIONES)

            total_hours = sum(asistencia_lines.mapped('number_of_hours'))
            record.total_worked_hours = total_hours

    @api.depends('line_ids.amount', 'basic_wage')
    def _compute_salario_pagar(self):
        """ Calcula salario a pagar: salario base - descuento por faltas/septimo """
        for record in self:
            descuento_falta = sum(record.line_ids.filtered(lambda l: l.code == constants.REGLASAL_DESC_SEPTIMO).mapped('amount'))
            salario_base = record.basic_wage or 0.0
            record.salario_pagar = round(salario_base - abs(descuento_falta), 2)

    @api.depends('line_ids.amount')
    def _compute_comisiones(self):
        """ Suma importes de líneas con codigo 'COMISION' """
        for record in self:
            comisiones_lines = record.line_ids.filtered(lambda l: l.code == constants.ASIGNACION_COMISIONES.upper())
            record.comisiones = sum(comisiones_lines.mapped('amount'))

    @api.depends('line_ids.amount')
    def _compute_overtime_total(self):
        """Suma importes de líneas con codigo 'OVERTIME' (horas extra)."""
        for record in self:
            overtime_lines = record.line_ids.filtered(lambda l: l.code == constants.ASIGNACION_HORAS_EXTRA.upper())
            record.total_overtime = sum(overtime_lines.mapped('amount'))

    @api.depends('line_ids.amount')
    def _compute_bonos(self):
        """Suma importes de líneas con codigo 'BONO'."""
        for record in self:
            bonos_lines = record.line_ids.filtered(lambda l: l.code == constants.ASIGNACION_BONOS.upper())
            record.bonos = sum(bonos_lines.mapped('amount'))

    @api.depends('line_ids.amount')
    def _compute_viaticos(self):
        """Viáticos = VIATICO + BONO (acumulados)."""
        for record in self:
            viaticos_lines = record.line_ids.filtered(lambda l: l.code == constants.ASIGNACION_VIATICOS.upper())
            record.viaticos = sum(viaticos_lines.mapped('amount')) + record.bonos

    @api.depends('viaticos', 'total_overtime')
    def _compute_total_viaticos_a_pagar(self):
        """Total de viaticos -> Suma viáticos y horas extra."""
        for record in self:
            record.total_viaticos_a_pagar = record.viaticos + record.total_overtime

    @api.depends('viaticos', 'total_viaticos_a_pagar', 'salario_pagar', 'vacaciones')
    def _compute_total_devengado(self):
        """Devengado total = viáticos + salario + comisiones + vacaciones."""
        for record in self:
            record.total_devengado = record.total_viaticos_a_pagar + float(record.salario_pagar) + record.comisiones + record.vacaciones

    @api.depends('line_ids.amount')
    def _compute_isr(self):
        """
           Calcula ISR con base en líneas:
           - 'RENTA'  (descuento normal) -> valor positivo
           - 'DEV_RENTA' (devolución)    -> valor negativo
        """
        for record in self:
            lineas_renta = record.line_ids.filtered(lambda l: l.code == constants.RENTA)
            lineas_dev_renta = record.line_ids.filtered(lambda l: l.code == constants.DEVOLUCION_RENTA_CODE)

            total_renta = record.isr = abs(sum(lineas_renta.mapped('amount')))
            total_dev_renta =  record.isr = abs(sum(lineas_dev_renta.mapped('amount')))
            if total_renta > 0:
                record.isr = total_renta
            else:
                record.isr = - total_dev_renta

    @api.depends('line_ids.amount')
    def _compute_afp(self):
        """Suma importes de líneas con code='AFP' (empleado)."""
        for record in self:
            afp_lines = record.line_ids.filtered(lambda l: l.code == constants.TIPO_DED_AFP.upper())
            record.afp = abs(sum(afp_lines.mapped('amount')))

    @api.depends('line_ids.amount')
    def _compute_afp_confia(self):
        """Suma importes de líneas con code='AFP_CONF' (Confía)."""
        for record in self:
            afp_confia_lines = record.line_ids.filtered(lambda l: l.code == constants.SUM_AFP.upper())
            record.afp_confia = abs(sum(afp_confia_lines.mapped('amount')))

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """Oculta la columna afp_incaf en lista si no hay ningún INCAF > 0 en las líneas de recibo."""
        res = super().fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)

        if view_type in ('tree', 'list'):
            # Consulta rápida para saber si hay INCAF en alguna boleta
            hay_incaf = bool(
                self.env['hr.payslip.line'].sudo().search([
                    ('code', '=', constants.DEDUCCION_INCAF.upper()),
                    ('amount', '>', 0),
                ], limit=1)
            )

            if not hay_incaf and res.get('arch'):
                try:
                    doc = etree.XML(res['arch'])
                    # Ocultar la columna si existe en la vista
                    for node in doc.xpath("//field[@name='afp_incaf']"):
                        node.set('invisible', '1')
                        # Para que no lo pueda reactivar por dominio, añade attrs también:
                        node.set('attrs', "{'invisible': True}")
                    res['arch'] = etree.tostring(doc, encoding='unicode')
                except Exception as e:
                    # Evita romper la carga de la vista si algo sale mal
                    self.env['ir.logging'].sudo().create({
                        'name': 'fields_view_get afp_incaf',
                        'type': 'server',
                        'dbname': self._cr.dbname,
                        'level': 'WARNING',
                        'message': f'No se pudo alterar la vista para ocultar afp_incaf: {e}',
                        'path': __name__,
                        'line': '0',
                        'func': 'fields_view_get',
                    })

        return res

    @api.depends('line_ids.amount')
    def _compute_afp_IPSFA(self):
        """Suma importes de líneas con code='IPSFA' (INCAF)."""
        for record in self:
            afp_ipsfa_lines = record.line_ids.filtered(lambda l: l.code == constants.AFP_IPSFA.upper())
            record.afp_IPSFA = abs(sum(afp_ipsfa_lines.mapped('amount')))

    @api.depends('line_ids.amount')
    def _compute_isss(self):
        """Suma importes de líneas con code='ISSS'."""
        for record in self:
            overtime_lines = record.line_ids.filtered(lambda l: l.code == constants.TIPO_DED_ISSS.upper())
            record.isss = abs(sum(overtime_lines.mapped('amount')))

    @api.depends('line_ids.amount')
    def _compute_otros_ded(self):
        """Suma importes de líneas con code='OTROS' (otras deducciones)."""
        for record in self:
            otros_lines = record.line_ids.filtered(lambda l: l.code == constants.SUM_OTRAS_DED.upper())
            record.otros = abs(sum(otros_lines.mapped('amount')))

    @api.depends('line_ids.amount')
    def _compute_bancos_ded(self):
        """Suma importes de líneas con code='BANCO' (descuentos bancarios)."""
        for record in self:
            bancos_lines = record.line_ids.filtered(lambda l: l.code == constants.SUM_BANCOS.upper())
            record.bancos = abs(sum(bancos_lines.mapped('amount')))

    @api.depends('line_ids.amount')
    def _compute_venta_empleados(self):
        """Suma importes de líneas con code='VENTA_EMPLEADOS'."""
        for record in self:
            venta_empleados_lines = record.line_ids.filtered(lambda l: l.code == constants.SUM_VENTA_EMPLEADOS)
            record.venta_empleados = abs(sum(venta_empleados_lines.mapped('amount')))

    @api.depends('line_ids.amount')
    def _compute_prestamos_incoe(self):
        """Suma importes de líneas con code='PRESTAMOS'."""
        for record in self:
            prestamos_lines = record.line_ids.filtered(lambda l: l.code == constants.SUM_PRESTAMOS.upper())
            record.prestamos_incoe = abs(sum(prestamos_lines.mapped('amount')))

    @api.depends('line_ids.amount')
    def _compute_fsv(self):
        """Suma importes de líneas con code='FSV'. (Fondo Social de la Vivienda)"""
        for record in self:
            fsv_lines = record.line_ids.filtered(lambda l: l.code == constants.SUM_FSV.upper())
            record.fsv = abs(sum(fsv_lines.mapped('amount')))

    @api.depends('isss', 'isr', 'afp', 'otros', 'bancos', 'fsv', 'prestamos_incoe', 'venta_empleados',
                 'total_viaticos_a_pagar')
    def _compute_total_descuentos(self):
        """Suma total de deducciones principales (sin viáticos)."""
        for record in self:
            record.total_descuentos = record.isss + record.isr + record.afp + record.otros + record.bancos + record.fsv + record.prestamos_incoe + record.venta_empleados

    @api.depends('total_devengado', 'total_descuentos')
    def _compute_sueldo_liquidido(self):
        """ Sueldo liquido = devengado - deducciones."""
        for record in self:
            record.sueldo_liquido = record.total_devengado - record.total_descuentos

    def action_send_lote_payslip(self):
        for record in self:
            _logger.info("RECORD : %s", record)

    def action_send_payslip_email(self):
        """
        Genera PDF y envía correo con la boleta al email laboral del empleado.
        Valida remitente, adjunta el reporte.
        """
        self.ensure_one()

        def _notify(msg, level='success', title='Boleta de pago', sticky=False):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {'title': title, 'message': msg, 'type': level, 'sticky': sticky},
            }

        # Plantilla de correo (debes tenerla definida en datos XML)
        template = self.env.ref('rrhh_base.rrhh_email_template_payslip', raise_if_not_found=False)
        if not template:
            return _notify("No se encontró la plantilla de correo para la boleta de pago.", 'warning', sticky=True)
        if not self.employee_id.work_email:
            return _notify("El empleado no tiene un correo configurado.", 'warning', sticky=True)

        # ===== VALIDAR REMITENTE DE BOLETAS =====
        # Se exige que la compañía tenga 'email_from_payslip' configurado.
        cfg_from = (self.company_id.email_from_payslip or '').strip()
        if not cfg_from:
            return _notify(
                "Configura el campo 'Remitente Boletas (From)' en Ajustes → Compañías → Correos de envío.",
                'warning', sticky=True
            )

        raw_from = cfg_from.replace('\r', ' ').replace('\n', ' ')
        name, addr = parseaddr(raw_from)
        if not addr or '@' not in addr:
            return _notify(
                "Remitente de boletas inválido. Usa 'correo@dominio' o 'Nombre <correo@dominio>'.",
                'danger', sticky=True
            )
        # Validación: dirección ASCII pura (evitar tildes en el correo)
        try:
            addr.encode('ascii')
        except UnicodeEncodeError:
            return _notify(f"El correo remitente debe ser ASCII simple (sin tildes): {addr}", 'danger', sticky=True)

        # Normaliza el "Nombre" para evitar caracteres raros en cabeceras
        def _sanitize(n):
            n = (n or '').replace('\r', ' ').replace('\n', ' ').strip()
            n = re.sub(r'\s+', ' ', n)
            if unicodedata:
                try:
                    n = unicodedata.normalize('NFKD', n).encode('ascii', 'ignore').decode('ascii')
                except Exception:
                    pass
            return n

        email_from_norm = formataddr((_sanitize(name), addr)) if name else addr

        # ===== Render PDF =====
        # Busca la acción de reporte de boleta
        report_action = (self.env.ref('rrhh_base.hr_payslip_report', raise_if_not_found=False)
                         or self.env.ref('rrhh_base.report_payslip', raise_if_not_found=False))
        if not report_action:
            return _notify("No se encontró la acción de reporte de la boleta de pago.", 'warning', sticky=True)

        # Renderiza QWeb a PDF para el registro actual
        pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
            report_action.report_name, [self.id]
        )
        filename = f"Boleta_{self.employee_id.name.replace(' ', '_')}_{self.date_to}.pdf"
        # Crea adjunto en el sistema (ir.attachment)
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'hr.payslip',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        # ===== Enviar =====
        # Prepara valores para el envío, incluyendo el adjunto y un remitente normalizado
        email_values = {
            'attachment_ids': [(6, 0, [attachment.id])],
            'email_from': email_from_norm,
        }
        # Usar el servidor SMTP de la compañía dedicado para boletas
        if self.company_id.smtp_payslip_id:
            email_values['mail_server_id'] = self.company_id.smtp_payslip_id.id

        try:
            template.send_mail(self.id, force_send=True, email_values=email_values)
        except Exception as e:
            # En caso de fallo de envío, intenta limpiar el adjunto
            try:
                attachment.unlink()
            except Exception:
                pass
            return _notify(f"No se pudo enviar el correo: {str(e)}", 'danger', sticky=True)

        self.message_post(body=f"Correo enviado a {self.employee_id.work_email} con el archivo {filename}.")
        return _notify(f"Correo enviado con éxito a {self.employee_id.work_email}", 'success')

    def year_selection(self):
        """Rango de años que se mostrarán en el panel."""
        current_year = date.today().year
        years = list(range(current_year - 3, current_year + 2))
        return [(str(y), str(y)) for y in years]

    period_year = fields.Selection(
        selection=year_selection, string='Año',
        compute='_compute_period_fields', store=True, index=True
    )
    period_month = fields.Selection(
        selection=PERIOD_MONTHS, string='Mes',
        compute='_compute_period_fields', store=True, index=True
    )
    period_quincena = fields.Selection(
        selection=[('1', '1ª quincena'), ('2', '2ª quincena')],
        string='Quincena',
        compute='_compute_period_fields', store=True, index=True
    )

    @api.depends('date_from', 'date_to')
    def _compute_period_fields(self):
        """
        Deriva año, mes (01..12) y quincena desde date_from.
        Si no hay fecha, limpia los campos.
        """
        for rec in self:
            if rec.date_from:
                # Tomamos date_from como referencia de periodo
                d = fields.Date.from_string(rec.date_from)
                rec.period_year = str(d.year)
                rec.period_month = f"{d.month:02d}"
                rec.period_quincena = '1' if d.day <= 15 else '2'
            else:
                rec.period_year = False
                rec.period_month = False
                rec.period_quincena = False