from odoo import fields, models, api, _
import logging

_logger = logging.getLogger(__name__)

import pytz
import datetime

def get_config_value(env, clave, company_id):
    """
    Buscar el valor de configuración según clave y company_id.
    """
    config = env['res.configuration'].search([
        ('clave', '=', clave),
        ('company_id', '=', company_id)
    ], limit=1)
    if config:
        return config.value_text
    return None

def compute_validation_type_2(env):
    """
    Busca el tipo de entorno (production o pruebas) dependiendo del valor en res.configuration.
    """
    _logger.info("SIT Entrando a compute_validation_type_2 desde res.configuration")

    config = env["res.configuration"].sudo().search([('clave', '=', 'ambiente')], limit=1)

    if not config or not config.value_text:
        _logger.warning("SIT No se encontró la clave 'ambiente' en res.configuration. Usando valor por defecto '00'")
        return "00"

    ambiente = config.value_text.strip()
    _logger.info("SIT Valor ambiente desde res.configuration: %s", ambiente)

    if ambiente in ["01"]:
        return ambiente
    else:
        _logger.warning("SIT Valor no reconocido en 'ambiente': %s. Usando '00'", ambiente)
        return "00"

def get_fecha_emi():
    # Establecer la zona horaria de El Salvador
    salvador_timezone = pytz.timezone('America/El_Salvador')
    fecha_emi = datetime.datetime.now(salvador_timezone)
    return fecha_emi.strftime('%Y-%m-%d')  # Formato: YYYY-MM-DD
