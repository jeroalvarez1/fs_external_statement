from email.policy import default

from odoo import api, fields, models


class SettlementHeaderFieldConfig(models.Model):
    _name = "settlement.header.field.config"

    name = fields.Char(compute='_compute_name', string='Nombre')
    settlement_header_config_id = fields.Many2one(
        'settlement.header.config',
        string='Configuración de Cabecera de Liquidación',
    )
    destination_field_id = fields.Many2one(
        'ir.model.fields',
        domain=[('model_id.model', '=', 'settlement.header')],
        string='Campo de destino',
        required=True
    )

    search_type = fields.Selection(
        related='settlement_header_config_id.search_type', string='Tipo de búsqueda', store=True
    )

    # Sirve para excel y txt
    start_with = fields.Char(
        string='Caracter de comienzo de linea'
    )
    line_number = fields.Integer(
        string='Numero de linea (.txt)'
    )
    starting_position = fields.Integer(string='Posición inicial en extracto (.txt)')
    end_position = fields.Integer(string='Posición final en el extracto (.txt)')

    # Campos para .csv, xsl y xlsx
    row = fields.Integer(string='Fila')
    col = fields.Integer(string='Columna')

    # TODO HACER UNICO CON COSTRAINT
    is_liquidation_number = fields.Boolean(string='Es el numero de liquidación', default=False)
    group_by = fields.Boolean(string='Agrupar por este campo', default=False)

    origin_date_format = fields.Char(string='Formato de Origen')
    dest_date_format = fields.Char(string='Formato de Destino')



    @api.depends('destination_field_id')
    def _compute_name(self):
        for record in self:
            record.name = record.destination_field_id.name

    @api.onchange('search_type')
    def _onchange_search_type(self):
        for record in self:
            if record.search_type:
                record.write({
                    'start_with': False,
                    'starting_position': False,
                    'end_position': False,
                    'col': False,
                    'is_liquidation_number': False,
                    'group_by': False,
                    'origin_date_format': False,
                    'dest_date_format': False
                })
            if record.search_type == 'excel_init_with_date':
                record.write({
                    'origin_date_format': '%Y-%m-%dT%H:%M:%S.%f%z',
                    'dest_date_format': '%Y-%m-%d',
                })
            else:
                record.write({
                    'origin_date_format': False,
                    'dest_date_format': False,
                })