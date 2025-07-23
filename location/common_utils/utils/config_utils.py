from odoo import fields, models, api, _
import logging

_logger = logging.getLogger(__name__)

import pytz
import datetime

from odoo.exceptions import UserError
from .constants import SCHEDULE_PAY_CONVERSION

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

        regla = env['hr.salary.rule'].search([('code', '=', codigo_regla)], limit=1)
        if not regla:
            _logger.warning("[COMMON_UTILS] Regla con código %s no encontrada. Se omite.", codigo_regla)
            continue

        _logger.debug("[COMMON_UTILS] Regla encontrada: %s (ID: %s)", regla.name, regla.id)

        cuenta_credito = obtener_cuenta_desde_codigo_config(env, claves_config['cuenta_salarial_deducciones_credito'])
        cuenta_debito = obtener_cuenta_desde_codigo_config(env, claves_config['cuenta_salarial_deducciones_debito'])

        _logger.debug(
            "[COMMON_UTILS] Cuenta crédito obtenida: %s, cuenta débito obtenida: %s",
            cuenta_credito and cuenta_credito.display_name or "N/A",
            cuenta_debito and cuenta_debito.display_name or "N/A"
        )

        valores = {}
        if cuenta_credito and regla.account_credit != cuenta_credito:
            valores['account_credit'] = cuenta_credito.id
        if cuenta_debito and regla.account_debit != cuenta_debito:
            valores['account_debit'] = cuenta_debito.id

        if valores:
            regla.write(valores)
            _logger.info(
                "[COMMON_UTILS] Regla %s (ID: %s) actualizada con valores: %s",
                codigo_regla,
                regla.id,
                valores
            )
        else:
            _logger.info(
                "[COMMON_UTILS] Regla %s (ID: %s) ya tenía las cuentas correctas configuradas, no se actualiza.",
                codigo_regla,
                regla.id
            )

    _logger.info("[COMMON_UTILS] Finalizó actualización de cuentas de reglas salariales.")

def get_monthly_wage_from_contract(contract):
    """
    Convierte el salario base del contrato a salario mensual
    según su schedule_pay.
    """
    schedule_pay = contract.schedule_pay or "monthly"
    factor = SCHEDULE_PAY_CONVERSION.get(schedule_pay, 1.0)
    _logger.info("Salario mensual=%.2f ", contract.wage * factor)
    _logger.info(
        "Contrato %s | wage=%.2f | schedule_pay=%s | factor=%.4f", contract.name, contract.wage, contract.schedule_pay, SCHEDULE_PAY_CONVERSION.get(contract.schedule_pay or 'monthly', 1.0))
    return contract.wage * factor

def get_hourly_rate_from_contract(contract):
    """
    Devuelve el valor por hora del contrato.
    - Si wage_type=hourly → usa contract.hourly_wage (lanza error si falta)
    - Si wage_type=monthly o professional_services → calcula desde salario mensual
    """
    tipo_salario = contract.wage_type or "monthly"

    # Servicios profesionales se tratan como mensual
    if tipo_salario == "professional_services":
        tipo_salario = "monthly"

    if tipo_salario == "hourly":
        if not contract.hourly_wage:
            raise UserError(
                f"El contrato '{contract.name}' es por hora pero no tiene definido "
                f"el salario por hora (campo Hourly Wage)."
            )
        return contract.hourly_wage

    # mensual fijo → promedio 30 días, 8 horas/día
    salario_mensual = get_monthly_wage_from_contract(contract)
    return salario_mensual / 30.0 / 8.0