from odoo import fields, models, api, _
import logging

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils sv despacho - res_company")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils' [despacho]: {e}")
    constants = None

class ResCompany(models.Model):
    _inherit = "res.company"

    # -------------------------------------------------------------------------
    # Configuración de despacho
    # -------------------------------------------------------------------------
    # Campo utilizado para definir un contacto restringido que no debe
    # aparecer en las órdenes de venta utilizadas para la asignación de rutas
    # de despacho.

    dispatch_contact_id = fields.Many2one(
        "res.partner",
        string="Contacto",
        help="Contacto restringido para órdenes de factura"
    )

    def get_values(self):
        # -------------------------------------------------------------------------
        # Lectura de configuración
        # -------------------------------------------------------------------------
        # Recupera el contacto restringido desde la tabla `res.configuration`
        # para mostrarlo en la configuración de la empresa.
        # -------------------------------------------------------------------------
        res = super().get_values()

        config = self.env["res.configuration"].search(
            [("clave", "=", constants.config_contacto_ruta),
             ("company_id", "=", self.env.company.id)],
            limit=1
        )

        res.update(dispatch_contact_id=int(config.value_text) if config.value_text else False)
        return res

    def set_values(self):
        # -------------------------------------------------------------------------
        # Escritura de configuración
        # -------------------------------------------------------------------------
        # Guarda el contacto seleccionado en la tabla `res.configuration`
        # como texto en el campo `value_text`.
        # -------------------------------------------------------------------------
        super().set_values()

        config = self.env["res.configuration"].search(
            [("clave", "=", constants.config_contacto_ruta),
             ("company_id", "=", self.env.company.id)],
            limit=1
        )

        if config:
            config.value_text = str(self.dispatch_contact_id.id or "")
