from odoo import fields, models, api
import logging

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils [hacienda ws-account_move]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None
    constants = None

class ResPartner(models.Model):
    _inherit = 'res.partner'

    tipo_ingreso_id_partner = fields.Many2one(
        comodel_name="account.tipo.ingreso",
        string="Tipo de Ingreso"
    )

    tipo_costo_gasto_id_partner = fields.Many2one(
        comodel_name="account.tipo.costo.gasto",
        string="Tipo de Costo/Gasto"
    )

    tipo_operacion_partner = fields.Many2one(
        comodel_name="account.tipo.operacion",
        string="Tipo Operacion"
    )

    clasificacion_facturacion_partner = fields.Many2one(
        comodel_name="account.clasificacion.facturacion",
        string="Clasificacion"
    )

    sector_partner = fields.Many2one(
        comodel_name="account.sector",
        string="Sector"
    )

    clasificacion_partner_domain = fields.Char(
        compute='_compute_partner_clasificacion_domain',
        readonly=True
    )

    sector_partner_domain = fields.Char(
        compute='_compute_partner_sector_domain',
        readonly=True
    )

    tipo_costo_gasto_partner_domain = fields.Char(
        compute='_compute_partner_costo_gasto_domain',
        readonly=True
    )

    @api.depends('tipo_operacion_partner')
    def _compute_partner_clasificacion_domain(self):
        for partner in self:
            domain = []

            tipo_operacion = partner.tipo_operacion_partner
            codigo_operacion = (tipo_operacion.codigo if tipo_operacion and tipo_operacion.codigo is not None else None)

            if codigo_operacion in (constants.TO_GRAVADO, constants.TO_NO_GRAV_EX, constants.TO_EXCLUIDO, constants.TO_MIXTA):
                domain = [
                    ('codigo', 'in', [constants.C_COSTO, constants.C_GASTO])
                ]

            partner.clasificacion_partner_domain = str(domain)

    @api.depends('clasificacion_facturacion_partner', 'tipo_operacion_partner')
    def _compute_partner_sector_domain(self):
        for partner in self:
            domain = []

            clasificacion = partner.clasificacion_facturacion_partner
            tipo_operacion = partner.tipo_operacion_partner

            codigo_clasificacion = (clasificacion.codigo if clasificacion and clasificacion.codigo is not None else None)

            codigo_operacion = (tipo_operacion.codigo if tipo_operacion and tipo_operacion.codigo is not None else None)

            if (codigo_clasificacion in (constants.C_COSTO, constants.C_GASTO)
                and codigo_operacion in (constants.TO_GRAVADO, constants.TO_NO_GRAV_EX, constants.TO_EXCLUIDO, constants.TO_MIXTA)):
                domain = [
                    ('codigo', 'in', [
                        constants.S_INDUSTRIA,
                        constants.S_COMERCIO,
                        constants.S_AGROP,
                        constants.S_SERVICIOS,
                    ])
                ]

            partner.sector_partner_domain = str(domain)

    @api.depends('sector_partner', 'clasificacion_facturacion_partner', 'tipo_operacion_partner')
    def _compute_partner_costo_gasto_domain(self):
        for partner in self:
            domain = []

            sector = partner.sector_partner
            clasificacion = partner.clasificacion_facturacion_partner
            tipo_operacion = partner.tipo_operacion_partner

            codigo_sector = (sector.codigo if sector and sector.codigo is not None else None)
            codigo_clasificacion = (clasificacion.codigo if clasificacion and clasificacion.codigo is not None else None)
            codigo_operacion = (tipo_operacion.codigo if tipo_operacion and tipo_operacion.codigo is not None else None)

            # Si la operación no es válida fiscalmente, no hay dominio
            if codigo_operacion not in (constants.TO_GRAVADO, constants.TO_NO_GRAV_EX, constants.TO_EXCLUIDO, constants.TO_MIXTA):
                partner.tipo_costo_gasto_partner_domain = str(domain)
                continue

            # INDUSTRIA | COSTOS
            if (codigo_sector == constants.S_INDUSTRIA
                    and codigo_clasificacion == constants.C_COSTO):
                domain = [
                    ('codigo', 'in', [
                        constants.TCG_IMPORTACIONES,
                        constants.TCG_COSTO_INTERNO,
                        constants.TCG_COSTOS_FAB,
                        constants.TCG_MANO_OBRA,
                    ])
                ]

            # COMERCIO / AGROP / SERVICIOS | COSTOS
            elif (codigo_sector in (constants.S_COMERCIO, constants.S_AGROP, constants.S_SERVICIOS)
                  and codigo_clasificacion == constants.C_COSTO):
                domain = [
                    ('codigo', 'in', [
                        constants.TCG_IMPORTACIONES,
                        constants.TCG_COSTO_INTERNO,
                    ])
                ]

            # TODOS LOS SECTORES | GASTOS
            elif (codigo_sector in (constants.S_INDUSTRIA, constants.S_COMERCIO, constants.S_AGROP, constants.S_SERVICIOS)
                  and codigo_clasificacion == constants.C_GASTO):
                domain = [
                    ('codigo', 'in', [
                        constants.TCG_VENTA_SIN_DONACION,
                        constants.TCG_GASTOS_ADMIN,
                        constants.TCG_GASTOS_FIN,
                    ])
                ]

            partner.tipo_costo_gasto_partner_domain = str(domain)
