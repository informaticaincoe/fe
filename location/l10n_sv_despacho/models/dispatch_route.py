from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    _logger.info("SIT Modulo config_utils [Despacho - dispatch_route]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils' en modelo dispatch_route: {e}")
    config_utils = None

class DispatchRoute(models.Model):
    _name = "dispatch.route"
    _description = 'Ruta de Despacho'
    _inherit = ['mail.thread', 'mail.activity.mixin'] # chatter + actividades

    route_manager_id = fields.Many2one('res.users', string='Responsable de ruta', default=lambda self: self.env.user)
    route_supervisor_id = fields.Many2one('res.users', string='Supervisor de ruta')

    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo')
    zone = fields.Text(string='Zona de Destino', required=True)
    route_date = fields.Date(string="Fecha de ruta", default=fields.Date.context_today)

    assistant_ids = fields.Many2many('hr.employee', string='Auxiliares')
    route_driver_id = fields.Many2one('hr.employee', string='Conductor', required=True)
    departure_datetime = fields.Datetime(string="Hora de salida")
    arrival_datetime = fields.Datetime(string="Hora de llegada")

    ####FRANCISCO FLORES
    company_id = fields.Many2one(
        'res.company', string="Compañia", required=True
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
        copy=False,
        string="Estado"
    )

    account_move_ids = fields.Many2many(
        'account.move',
        domain=[
            ('dispatch_route_id', '=', False),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            ('payment_state', 'not in', ('paid', 'in_payment')),
        ],
        string='Documentos electrónicos',
        required=True
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
    def _check_max_assistants(self):
        company = self.env.company

        max_allowed_assistants = config_utils.get_config_value(self.env, 'cant_aux_ruta', company.id)
        if max_allowed_assistants is None:
            raise ValidationError(_('No se ha configurado la cantidad máxima de auxiliares para la empresa %s.') % company.name)

        for record in self:
            if len(record.assistant_ids) > int(max_allowed_assistants):
                raise ValidationError(
                    _('El número máximo permitido de auxiliares es %s.') % (int(max_allowed_assistants))
                )

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

    def action_open_reception(self):
        self.ensure_one()
        if self.state != "in_transit":
            raise UserError(_("Solo se puede recibir una ruta cuando está En tránsito."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Recepción de Ruta (CxC)"),
            "res_model": "dispatch.route.reception",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_route_id": self.id,
            },
        }

    def action_create_reception(self):
        self.ensure_one()

        if self.state != "in_transit":
            raise UserError(_("Solo se puede crear la recepción cuando la ruta está En tránsito."))

        Reception = self.env["dispatch.route.reception"]

        # 🔎 Buscar si ya existe recepción para esta ruta
        reception = Reception.search([
            ("route_id", "=", self.id),
            # ("state", "!=", "cancel"),
        ], limit=1)

        # ➕ Si no existe, crearla
        if not reception:
            reception = Reception.create({
                "route_id": self.id,
                "company_id": self.company_id.id,
            })

        # 🔁 Abrir la recepción (existente o recién creada)
        return {
            "type": "ir.actions.act_window",
            "name": _("Recepción de Ruta"),
            "res_model": "dispatch.route.reception",
            "res_id": reception.id,
            "view_mode": "form",
            "target": "current",
        }

    #########

















