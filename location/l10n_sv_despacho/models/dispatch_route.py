from odoo import api, fields, models, _

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
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('confirmed', 'Confirmado'),
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

    @api.constrains('assistant_ids')
    def _check_max_three_assistants(self):
        for record in self:
            if len(record.assistant_ids) > 3:
                raise ValidationError('Solo se pueden seleccionar hasta 3 auxiliares.')
