from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class DispatchRoute(models.Model):
    _name = "dispatch.route"
    _description = 'Ruta de Despacho'
    _inherit = ['mail.thread', 'mail.activity.mixin'] # chatter + actividades

    route_manager_id = fields.Many2one('res.users', string='Responsable de ruta', default=lambda self: self.env.user)

    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo')
    zone = fields.Text(string='Zona de Destino')
    route_date = fields.Date(string="Fecha de ruta", default=fields.Date.context_today)
    assistant_ids = fields.Many2many('hr.employee', string='Auxiliares')
    departure_time = fields.Float(string='Hora de salida', help='Hora de salida')
    arrival_time = fields.Float(string='Hora de llegada', help='Hora de llegada')

    ####FRANCISCO FLORES
    company_id = fields.Many2one(
        'res.company', string="Compañia", default=lambda self: self.env.company, required=True
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", string="Moneda", readonly=True
    )
    ######

    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('confirmed', 'Confirmado'),
            ("in_transit", 'En transito'),
            ("received", "Recibido (CxC)"),
            ('cancel', 'Cancelado'),
        ],
        default='draft',
        tracking=True,
        copy=False
    )

    account_move_ids = fields.One2many(
        'account.move',
        'dispatch_route_id',
        string='Documentos electrónicos'
    )

    #AGREGADO POR FRAN
    # ---- DATOS DE RECEPCION (RESUMEN) ----
    received_by_id = fields.Many2one("res.users", string="Recebido por", readonly=True)
    received_date = fields.Datetime(string="Fecha de recepcion", readonly=True)
    cash_received = fields.Monetary(string="Efectivo Recebido", currency_field="currency_id", readonly=True)
    expected_cash_total = fields.Monetary(string="Esperado contado entregado", currency_field="currency_id", readonly=True)
    cash_difference = fields.Monetary(string="Diferencia", currency_field="currency_id", readonly=True)
    last_reception_id = fields.Many2one("dispatch.route.reception", string="Última recepción", readonly=True)

    @api.constrains('assistant_ids')
    def _check_max_three_assistants(self):
        for record in self:
            if len(record.assistant_ids) > 3:
                raise ValidationError('Solo se pueden seleccionar hasta 3 auxiliares.')

    #####FRANCISCO FLORES

    def action_confirm(self):
        for r in self:
            if r.state != 'draft':
                continue
            r.state = 'confirmed'

    def action_start_transit(self):
        for r in self:
            if r.state != "confirmed":
                raise UserError(_("La ruta debe estar en estado Confirmado para pasar a En tránsito."))
            r.state = "in_transit"

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_open_reception_wizard(self):
        self.ensure_one()
        if self.state != "in_transit":
            raise UserError(_("Solo se puede recibir una ruta cuando esta en transito"))

        return{
            "type": "ir.actions.act_window",
            "name": _("Recepción de Ruta (CxC)"),
            "res_model": "dispatch.route.reception.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_route_id": self.id,
            },
        }

    #########

















