from odoo import fields, models, api, _
import logging

_logger = logging.getLogger(__name__)

import pytz
from datetime import datetime
import pytz

from odoo.exceptions import UserError
from .constants import SCHEDULE_PAY_CONVERSION

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils contingencia")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils' en modulo de contingencia: {e}")
    config_utils = None
    constants = None

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
    Busca el tipo de entorno (producción o pruebas) dependiendo del valor en res.configuration.
    """
    _logger.info("SIT Entrando a compute_validation_type_2 desde res.configuration")

    config = env["res.configuration"].sudo().search([('clave', '=', 'ambiente')], limit=1)

    if not config or not config.value_text:
        _logger.warning("SIT No se encontró la clave 'ambiente' en res.configuration. Usando valor por defecto '00'")
        raise UserError("No se encontró la configuración del ambiente en la configuracion de empresa. Por favor verifique que exista la clave 'ambiente'.")

    ambiente = config.value_text.strip()
    _logger.info("SIT Valor ambiente desde res.configuration: %s", ambiente)

    if ambiente in ["01"]:
        return ambiente
    else:
        _logger.warning("SIT Valor no reconocido en 'ambiente': %s. Usando '00'", ambiente)
        return "00"

def _compute_validation_type_2(env, company):
    """
    Busca el tipo de entorno (production o pruebas) dependiendo del valor en res.company.
    """
    _logger.info("SIT Entrando a compute_validation_type_2 desde res.company: company: %s", company)
    entorno_pruebas = False

    #config_settings = env["res.config.settings"].sudo().search([('company_id', '=', company.id)], order='id desc', limit=1)
    config_settings_entorno = env["res.company"].sudo().search([('id', '=', company.id)], order='id desc', limit=1)
    _logger.info("SIT Empresa: %s, entorno: %s", config_settings_entorno.id, config_settings_entorno.sit_entorno_test)
    if config_settings_entorno:
        parameter_env_type = config_settings_entorno.sit_entorno_test

        _logger.info("SIT Valor ambiente desde res.config.settings: %s", parameter_env_type)
        if not parameter_env_type:
            entorno_pruebas = False
        else:
            entorno_pruebas = True
    if not config_settings_entorno:
        _logger.info("SIT No se encontro el tipo de entorno configurado: %s", config_settings_entorno)
        raise UserError(_("No se encontró configuración de ambiente para la compañía %s. Por favor configure el tipo de entorno.") % company.name)
    return entorno_pruebas

def get_fecha_emi():
    # Establecer la zona horaria de El Salvador
    salvador_timezone = pytz.timezone('America/El_Salvador')
    fecha_emi = datetime.datetime.now(salvador_timezone)
    return fecha_emi.strftime('%Y-%m-%d')  # Formato: YYYY-MM-DD

def obtener_cuenta_desde_codigo_config(env, clave_config):
    """
    Busca una configuración específica mediante la clave proporcionada
    y obtiene la cuenta contable asociada.
    """
    _logger.info("Buscando cuenta contable a partir de la configuración con clave: %s", clave_config)

    config = env['res.configuration'].search([('clave', '=', clave_config)], limit=1)
    if config:
        if config.value_text:
            cuenta = env['account.account'].search([('code', '=', config.value_text)], limit=1)
            if cuenta:
                _logger.info("Cuenta contable encontrada para clave %s: %s", clave_config, cuenta.display_name)
                return cuenta
            else:
                _logger.warning("No se encontró cuenta contable con código: %s", config.value_text)
        else:
            _logger.warning("La configuración no tiene valor_text definido.")
    else:
        _logger.warning("No se encontró configuración con clave: %s", clave_config)

    return False

def actualizar_cuentas_reglas_generico(env, reglas):
    """
    Actualiza las cuentas contables (crédito y débito) para las reglas salariales indicadas.

    :param env: entorno de ejecución Odoo
    :param reglas: diccionario {codigo_regla: {clave_credito, clave_debito}}
    """
    _logger.info("[COMMON_UTILS] Iniciando actualización de cuentas para %d reglas salariales.", len(reglas))

    for codigo_regla, claves_config in reglas.items():
        _logger.debug("[COMMON_UTILS] Procesando regla con código: %s", codigo_regla)

        # Buscar TODAS las reglas con este código (pueden estar en varias estructuras)
        reglas_encontradas = env['hr.salary.rule'].search([('code', '=', codigo_regla)])
        if not reglas_encontradas:
            _logger.warning("[COMMON_UTILS] Regla con código %s no encontrada. Se omite.", codigo_regla)
            continue

        # Obtener las cuentas configuradas desde la utilidad
        cuenta_credito = obtener_cuenta_desde_codigo_config(env, claves_config['cuenta_salarial_deducciones_credito'])
        cuenta_debito = obtener_cuenta_desde_codigo_config(env, claves_config['cuenta_salarial_deducciones_debito'])

        _logger.debug(
            "[COMMON_UTILS] Cuenta crédito obtenida: %s, cuenta débito obtenida: %s",
            cuenta_credito.display_name if cuenta_credito else "N/A",
            cuenta_debito.display_name if cuenta_debito else "N/A"
        )

        # Actualizar cada regla encontrada
        for regla in reglas_encontradas:
            valores = {}
            if cuenta_credito and regla.account_credit != cuenta_credito:
                valores['account_credit'] = cuenta_credito.id
            if cuenta_debito and regla.account_debit != cuenta_debito:
                valores['account_debit'] = cuenta_debito.id

            if valores:
                regla.write(valores)
                _logger.info(
                    "[COMMON_UTILS] Regla %s (ID: %s, estructura: %s) actualizada con %s",
                    codigo_regla,
                    regla.id,
                    regla.struct_id.display_name if regla.struct_id else "Sin estructura",
                    valores
                )
            else:
                _logger.info(
                    "[COMMON_UTILS] Regla %s (ID: %s, estructura: %s) ya estaba correcta, no se modifica",
                    codigo_regla,
                    regla.id,
                    regla.struct_id.display_name if regla.struct_id else "Sin estructura"
                )

    _logger.info("[COMMON_UTILS] Finalizó actualización de cuentas en todas las estructuras.")

def get_monthly_wage_from_contract(contract):
    """
    Convierte el salario base del contrato a salario mensual
    según su schedule_pay.
    """
    schedule_pay = contract.schedule_pay or "monthly"
    factor = SCHEDULE_PAY_CONVERSION.get(schedule_pay, 1.0)
    _logger.info("Salario mensual=%.2f ", contract.wage * factor)
    _logger.info("Contrato %s | wage=%.2f | schedule_pay=%s | factor=%.4f", contract.name, contract.wage, contract.schedule_pay, SCHEDULE_PAY_CONVERSION.get(contract.schedule_pay or 'monthly', 1.0))
    return contract.wage * factor

def get_hourly_rate_from_contract(contract):#Se utilizaba para vacaciones parciales
    """
    Devuelve el valor por hora del contrato.
    - Si wage_type=hourly → usa contract.hourly_wage (lanza error si falta)
    - Si wage_type=monthly o professional_services → calcula desde salario mensual
    """
    tipo_salario = contract.wage_type or "semi-monthly"

    # Servicios profesionales se tratan como mensual
    if tipo_salario == constants.SERVICIOS_PROFESIONALES:
        tipo_salario = constants.SALARIO_MENSUAL

    if tipo_salario == constants.SALARIO_POR_HORA:
        if not contract.hourly_wage:
            raise UserError(
                f"El contrato '{contract.name}' es por hora pero no tiene definido "
                f"el salario por hora (campo Hourly Wage)."
            )
        return contract.hourly_wage

    # mensual fijo → promedio 30 días, 8 horas/día
    salario_mensual = get_monthly_wage_from_contract(contract)
    dias_promedio = to_int(get_dias_promedio_salario(contract.env, contract.company_id.id), 0)
    horas_diarias = to_int(get_config_value(contract.env, CANT_HORAS_DIARIAS, contract.company_id.id), 0)

    if dias_promedio <= 0 or horas_diarias <= 0:
        raise UserError("No se puede calcular la tarifa por hora debido a configuración inválida.")

    return salario_mensual / dias_promedio / horas_diarias

def get_dias_promedio_salario(env, company_id):
    """
    Obtiene el número de días promedio para cálculo diario del salario
    desde res.configuration. Si no existe, devuelve 30 por defecto.
    """
    dias_cfg = get_config_value(env, constants.DIAS_PROMEDIO_TRABAJADOS, company_id)
    try:
        return int(dias_cfg) if dias_cfg else 30
    except ValueError:
        _logger.warning("Valor inválido para dias_promedio_salario: %s, usando 30 por defecto", dias_cfg)
        return 30

def to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _get_fecha_procesamiento(self, fh_str=None, fmt='%d/%m/%Y %H:%M:%S'):
    """
    Devuelve un datetime válido para 'fecha de procesamiento'.
    - Si fh_str está definido e interpretable, se convierte a datetime.
    - Si fh_str no existe o es inválido, retorna la hora actual de El Salvador.
    - Si tampoco se puede, usa create_date ajustado a la zona horaria de El Salvador.
    """
    salvador_tz = pytz.timezone('America/El_Salvador')

    # 1) Si hay fecha de Hacienda, intentar parsear
    if fh_str:
        try:
            fecha = datetime.strptime(fh_str, fmt)
            _logger.info("Fecha de procesamiento válida recibida: %s", fecha)
            return fecha
        except Exception as e:
            _logger.warning("No se pudo parsear fecha '%s': %s", fh_str, e)

    # 2) Si no hay fh_str o falló, usar hora actual de El Salvador
    try:
        now_salvador = datetime.now(salvador_tz)
        _logger.info("Usando hora actual de El Salvador como fecha de procesamiento: %s", now_salvador)
        return now_salvador
    except Exception as e:
        _logger.warning("Error al obtener hora de El Salvador: %s", e)

    # 3) Último fallback: usar create_date convertido a El Salvador
    if hasattr(self, "create_date") and self.create_date:
        create_date_salvador = self.create_date.astimezone(salvador_tz)
        _logger.info("Usando create_date ajustado a El Salvador: %s", create_date_salvador)
        return create_date_salvador

    _logger.warning("No se pudo obtener ninguna fecha de procesamiento, devolviendo None")
    return None
