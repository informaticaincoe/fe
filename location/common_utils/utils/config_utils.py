def get_config_value(env, clave, company_id):
    config = env['res.configuration'].search([
        ('clave', '=', clave),
        ('company_id', '=', company_id)
    ], limit=1)
    if config:
        if config.value_type == 'int':
            return int(config.value_text)
    return None
