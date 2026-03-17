from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import datetime

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

    sale_order_ids = fields.Many2many(
        "sale.order",
        string="Órdenes de facturación",
        # compute="_compute_sale_orders",
        # inverse="_inverse_sale_orders",
        domain=[("dispatch_route_id", "=", False)],
        required=True,
    )

    invoice_ids = fields.Many2many(
        "account.move",
        string="Facturas relacionadas",
        compute="_compute_invoices_from_orders",
        readonly=True,
    )

    # Campo técnico para recolectar los IDs de municipios de la zona
    zone_municipality_ids = fields.Many2many(
        'res.municipality',
        compute="_compute_zone_municipality_ids",
        string="Municipios permitidos",
        store=False
    )

    @api.depends('zone_id', 'zone_id.zone_line_ids', 'zone_id.zone_line_ids.munic_ids')
    def _compute_zone_municipality_ids(self):
        for rec in self:
            municipios = self.env['res.municipality']
            if rec.zone_id and rec.zone_id.zone_line_ids:
                municipios = rec.zone_id.zone_line_ids.mapped('munic_ids')

            rec.zone_municipality_ids = municipios

            # ---- BLOQUE DE DEBUG PARA FILTRADO ----
            ids_zona = municipios.ids
            _logger.info("=== DEBUG FILTRADO DE ÓRDENES ===")
            _logger.info("IDs Municipios en Zona '%s': %s", rec.zone_id.name, ids_zona)

            # Buscamos órdenes borradores o confirmadas sin ruta para inspeccionar sus clientes
            ordenes_libres = self.env['sale.order'].search([
                ('dispatch_route_id', '=', False),
                ('state', 'not in', ['cancel'])
            ], limit=10)  # Limitamos a 10 para no saturar el log

            for so in ordenes_libres:
                m_id = so.partner_id.munic_id.id
                m_nombre = so.partner_id.munic_id.name

                esta_en_zona = m_id in ids_zona
                _logger.info(
                    "Orden: %s | Cliente: %s | Municipio Cliente ID: %s (%s) | ¿Pasaría el filtro?: %s",
                    so.name, so.partner_id.name, m_id, m_nombre, "SÍ" if esta_en_zona else "NO"
                )
            _logger.info("=================================")

    name = fields.Char(string='Referencia', readonly=True, copy=False, default='/')
    code_route = fields.Char(string='Codigo', readonly=True, copy=False, default='/', tracking=True)
    route_manager_id = fields.Many2one('res.users', string='Responsable de ruta', default=lambda self: self.env.user)
    route_supervisor_id = fields.Many2one(
        'res.users',
        string='Supervisor de ruta',
        help="Encargado de la supervisión y control de las rutas cuando el responsable principal no se encuentra disponible."
    )

    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo')
    zone_id = fields.Many2one('dispatch.zones', string='Zona de Destino', required=True, ondelete='restrict')
    route_date = fields.Date(string="Fecha de ruta", default=fields.Date.context_today)

    assistant_ids = fields.Many2many(
        'hr.employee',
        string='Auxiliares',
        domain="[('id', '!=', route_driver_id)]"
    )
    route_driver_id = fields.Many2one(
        'hr.employee',
        string='Conductor',
        required=True,
        domain="[('id', 'not in', assistant_ids)]"
    )
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
            ('loading', 'Cargando'),
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
        'dispatch_route_id',
        domain=[
            ('dispatch_route_id', '=', False),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            ('payment_state', 'not in', ('paid', 'in_payment')),
        ],
        compute='_compute_account_moves',
        inverse='_inverse_account_moves',
        string='Documentos electrónicos',
    )

    #AGREGADO POR FRAN
    # ---- DATOS DE RECEPCION (RESUMEN) ----
    received_by_id = fields.Many2one("res.users", string="Recibido por", readonly=True)
    received_date = fields.Datetime(string="Fecha de recepcion", readonly=True)
    cash_received = fields.Monetary(string="Efectivo Recibido", currency_field="currency_id", readonly=True)
    expected_cash_total = fields.Monetary(string="Esperado contado entregado", currency_field="currency_id", readonly=True)
    cash_difference = fields.Monetary(string="Diferencia", currency_field="currency_id", readonly=True)
    last_reception_id = fields.Many2one("dispatch.route.reception", string="Última recepción", readonly=True)
    invoice_names = fields.Text(string="Facturas", compute="_compute_invoice_names", store=False)

    def _compute_invoice_names(self):
        for r in self:
            r.invoice_names = "\n".join([f"• {x}" for x in r.sale_order_ids.mapped("name")])

    def _compute_sale_orders(self):
        for route in self:
            route.sale_order_ids = self.env["sale.order"].search([("dispatch_route_id", "=", route.id)])

    def _inverse_sale_orders(self):
        for route in self:
            current = self.env["sale.order"].search([("dispatch_route_id", "=", route.id)])
            selected = route.sale_order_ids

            (current - selected).write({"dispatch_route_id": False})
            (selected - current).write({"dispatch_route_id": route.id})

    def _compute_invoices_from_orders(self):
        for route in self:
            route.invoice_ids = route.sale_order_ids.mapped("invoice_ids").filtered(
                lambda m: m.move_type in ("out_invoice", "out_refund")
            )


    @api.constrains('assistant_ids')
    def _check_max_assistants(self):
        company = self.env.company

        if not config_utils:
            raise ValidationError(_("Falta el módulo/common_utils (config_utils). Verifica addons_path e instalación."))

        max_allowed_assistants = config_utils.get_config_value(self.env, 'cant_aux_ruta', company.id)
        if max_allowed_assistants is None:
            raise ValidationError(_('No se ha configurado la cantidad máxima de auxiliares para la empresa %s.') % company.name)

        for record in self:
            if len(record.assistant_ids) > int(max_allowed_assistants):
                raise ValidationError(
                    _('El número máximo permitido de auxiliares es %s.') % (int(max_allowed_assistants))
                )

    def _compute_account_moves(self):
        for route in self:
            route.account_move_ids = self.env['account.move'].search([
                ('dispatch_route_id', '=', route.id)
            ])

    def _inverse_account_moves(self):
        for route in self:
            # Facturas actualmente asignadas a esta ruta
            current_moves = self.env['account.move'].search([
                ('dispatch_route_id', '=', route.id)
            ])

            # Facturas seleccionadas en la UI
            selected_moves = route.account_move_ids

            # Quitar las que ya no están seleccionadas
            (current_moves - selected_moves).write({
                'dispatch_route_id': False
            })

            # Asignar las nuevas
            (selected_moves - current_moves).write({
                'dispatch_route_id': route.id
            })

    #####FRANCISCO FLORES

    def action_confirm(self):
        for r in self:
            if r.state != 'draft':
                continue

            if not r.sale_order_ids:
                raise UserError(_("No es posible confirmar la ruta sin seleccionar al menos una órden de factura."))
            r.state = 'confirmed'

    def action_load(self):
        for r in self:
            if r.state != 'confirmed':
                continue

            if not r.sale_order_ids:
                raise UserError(_("No es posible confirmar la ruta sin seleccionar al menos una órden de factura."))
            r.state = 'loading'

    def action_start_transit(self):
        for r in self:
            if r.state != "loading":
                raise UserError(_("La ruta debe estar en estado Cargando para pasar a En tránsito."))

            pickings = r.sale_order_ids.mapped("picking_ids")

            picking_recoleccion = pickings.filtered(
                lambda p: p.picking_type_id and 'recolectar' in (p.picking_type_id.name or '').lower()
            )

            pendientes = picking_recoleccion.filtered(
                lambda p: p.state not in ["done", "cancel"]
            )

            if pendientes:
                # Si 'pendientes' no está vacío, significa que hay al menos un picking
                # que requiere atención o está incompleto.
                raise UserError(
                    _("No se puede iniciar el tránsito: existen movimientos de recolección pendientes o en borrador.")
                )

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

        _logger.info("Iniciando action_create_reception | Ruta ID=%s | Estado=%s", self.id, self.state)

        if self.state != "in_transit":
            raise UserError(_("Solo se puede crear la recepción cuando la ruta está En tránsito."))
        if not self.departure_datetime:
            raise ValidationError(_('La hora de salida es requerida para enviar la ruta a Recepción (CxC).'))
        if not self.arrival_datetime:
            raise ValidationError(_('La hora de llegada es requerida para enviar la ruta a Recepción (CxC).'))

        Reception = self.env["dispatch.route.reception"]

        # 🔎 Buscar si ya existe recepción para esta ruta
        reception = Reception.search([
            ("route_id", "=", self.id),
        ], limit=1)

        # ➕ Si no existe, crearla
        if not reception:
            _logger.info("No existe recepción, creando nueva | Ruta ID=%s", self.id)

            # 1. Preparamos las líneas usando el método del modelo de recepción
            # Pasamos 'self' que es el registro de la ruta actual
            line_values = Reception._prepare_lines_from_route(self)

            # 2. Creamos la recepción con las líneas ya incluidas
            reception = Reception.create({
                "route_id": self.id,
                "company_id": self.company_id.id,
                "line_ids": line_values,  # <--- Esto inyecta las facturas
            })
        else:
            _logger.info("Recepción existente encontrada | Recepción ID=%s", reception.id)
            # Opcional: Si existe pero por algún error no tiene líneas, las cargamos
            if not reception.line_ids and reception.state == 'draft':
                line_values = reception._prepare_lines_from_route(self)
                reception.write({"line_ids": line_values})

        _logger.info("Abriendo formulario de recepción | Recepción ID=%s", reception.id)

        return {
            "type": "ir.actions.act_window",
            "name": _("Recepción de Ruta"),
            "res_model": "dispatch.route.reception",
            "res_id": reception.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.constrains('assistant_ids', 'route_driver_id')
    def _check_driver_not_in_assistants(self):
        for rec in self:
            if rec.route_driver_id and rec.route_driver_id in rec.assistant_ids:
                raise ValidationError(_("El conductor no puede estar incluido dentro de los auxiliares."))

    def action_set_draft(self):
        for record in self:
            if record.state not in('cancel'):
                raise ValidationError(_('Solo las rutas canceladas pueden regresar a estado Borrador.'))
            record.state = 'draft'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code_route', '/') == '/':
                vals['code_route'] = self.env['ir.sequence'].next_by_code('dispatch.route') or '/'
            if vals.get('zone_id'):
                zone = self.env['dispatch.zones'].browse(vals['zone_id'])
                vals['name'] = zone.name
        return super().create(vals_list)


    def action_download_report_reception(self):
        self.ensure_one()

        print(">>>>>>> SELF ", self )
        print(">>>>>>> SELF id", self.id )

        ruta = self.env["dispatch.route"].search([
            ("id", "=", self.id),
        ], limit=1)

        print(">>>>>>> RUTA ", ruta )
        print(">>>>>>> RUTA ID ", ruta.id )

        return self.env.ref('l10n_sv_despacho.action_report_recepcion_ruta').report_action(ruta)

    @api.onchange('zone_id')
    def _onchange_zone_id_set_name(self):
        for rec in self:
            if rec.zone_id:
                rec.name = rec.zone_id.name

    def action_download_report_cargar_ruta(self):
        self.ensure_one()

        print(">>>>>>> SELF ", self )
        print(">>>>>>> SELF id", self.id )

        ruta = self.env["dispatch.route"].search([
            ("id", "=", self.id),
        ], limit=1)

        print(">>>>>>> RUTA ", ruta )
        print(">>>>>>> RUTA ID ", ruta.id )

        return self.env.ref('l10n_sv_despacho.action_report_carga_ruta').report_action(ruta)

    # VEHICULOS
    vehicle_capacity = fields.Float(
        related='vehicle_id.car_value',  # O el campo de capacidad de tu modelo de flota
        string="Capacidad Vehículo (kg)",
        readonly=True
    )

    total_weight = fields.Float(
        string="Carga Total (kg)",
        compute="_compute_total_weight",
        store=True,
        help="Suma del peso de todos los productos en las órdenes seleccionadas"
    )

    capacity_list_view = fields.Char(
        string="Carga",
        compute="_compute_capacity_list_view",
        store=False,
        help="Capacidad utilizada del vehiculo"
    )

    @api.depends('sale_order_ids', 'sale_order_ids.order_line.product_id.weight')
    def _compute_total_weight(self):
        for route in self:
            weight = 0.0
            for order in route.sale_order_ids:
                # Sumamos el peso de cada línea (peso unitario * cantidad)
                for line in order.order_line:
                    weight += line.product_id.weight * line.product_uom_qty
            route.total_weight = weight

    @api.depends('sale_order_ids', 'sale_order_ids.order_line.product_id.weight', 'vehicle_id')
    def _compute_capacity_list_view(self):
        for route in self:
            # por si vienen nulos
            total = route.total_weight or 0.0
            cap = route.vehicle_capacity or 0.0
            route.capacity_list_view = f'{total} / {cap} kg'

    @api.model
    def action_download_loading_routes_report(self):
        routes = self.search([("state", "=", "loading")])

        if not routes:
            raise UserError(_("No hay rutas en estado 'Cargando' para imprimir."))

        return self.env.ref('l10n_sv_despacho.action_report_montacarguista').report_action(routes)