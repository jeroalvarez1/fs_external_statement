from odoo import api, fields, models


class SettlementHeaderConfig(models.Model):
    _name = "settlement.header.config"

    name = fields.Char(compute='_compute_name', string='Nombre')
    external_bank_config_id = fields.Many2one(
        'external.bank.config',
        string='Configuración del Banco Externo'
    )
    field_type = fields.Selection([
        ('txt', '.txt'), ('csv', '.csv'), ('xls', '.xls'), ('xlsx', '.xlsx')
    ], string='Tipo de Archivo')

    # TODO, Poner dominio correspondiente
    search_type = fields.Selection([
        ('txt_sw', '.txt Caracter de comienzo de linea'), ('txt_ln', '.txt Numero de linea'),
        ('excel_rc', 'Excel, coincidencia exacta (fila, columna)'), ('excel_init_with', 'Excel, comienza con'),
        ('excel_init_with_date', 'Excel, comienza con fecha')
    ], string='Tipo de búsqueda')

    field_config_ids = fields.One2many(
        'settlement.header.field.config',
        'settlement_header_config_id',
        string='Campos de Configuración',
    )

    @api.depends('external_bank_config_id', 'field_type')
    def _compute_name(self):
        for record in self:
            record.name = f'{record.external_bank_config_id.name}-{record.field_type}'

