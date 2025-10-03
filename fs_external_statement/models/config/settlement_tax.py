from odoo import api, fields, models


class SettlementTax(models.Model):
    _name = "settlement.tax"

    name = fields.Char(string='Nombre', required=True)

    settlement_tax_config_id = fields.Many2one(
        'settlement.tax.config',
        string='Configuración del Impuesto'
    )
    active = fields.Boolean(string='Activo', default=True)
    type = fields.Selection([
        ('net', 'Neto'),
        ('tax', 'Impuesto')
    ], string='Tipo', required=True)
    parent_id = fields.Many2one('settlement.tax', string='Impuesto padre', ondelete='cascade')
    tax_id = fields.Many2one('account.tax', string='Impuesto Relacionado', domain=[('type_tax_use', '=', 'purchase')])
    product_id = fields.Many2one(
        'product.template',
        string='Producto del impuesto',
        help='Producto utilizado para facturar el impuesto del extracto'
    )
    settlement_tax_line_ids = fields.One2many(
        'settlement.tax.line',
        'settlement_tax_id',
        string='Líneas de configuración',
        required=True
    )
    journal_ids = fields.Many2many(
        'account.journal',
        'journal_settlement_tax_rel',
        'settlement_tax_id',
        'journal_id',
        domain=[('type', '=', 'bank')],
        string="Diarios de Tarjeta"
    )


    # NUEVOS
    destination_field_id = fields.Many2one(
        'ir.model.fields',
        domain=[('model_id.model', '=', 'settlement.trailer.tax')],
        string='Campo de destino',
    )
    start_with = fields.Char(string='Caracter de comienzo de linea')
    starting_position = fields.Integer(string='Posición inicial en extracto (.txt)')
    end_position = fields.Integer(string='Posición final en el extracto (.txt)')
    field_type = fields.Selection([('base', 'Base'), ('tax', 'Impuesto')], string='Tipo de registro') # todo cambiar nombre
    row = fields.Integer(string='Fila')
    col = fields.Integer(string='Columna')
    origin_date_format = fields.Char(string='Formato de Origen')
    dest_date_format = fields.Char(string='Formato de Destino')


    @api.onchange('type')
    def _onchange_type(self):
        if self.type == 'net':
            self.write({
                'parent_id': False,
            })
        elif self.type == 'tax':
            self.write({
                'product_id': False
            })