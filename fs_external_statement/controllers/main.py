from odoo import http
from odoo.http import request

class ImportSettlements(http.Controller):
    
    @http.route('/get_action_import_settlements', auth="user", type='json')
    def get_action_import_settlements(self, **kw):
        action = request.env.ref('fs_external_statement.action_import_external_statement_wizard').read()[0]
        return action

