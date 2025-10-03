odoo.define('fs_external_statement.import_settlements',function(require){
    "use strict";
    
var ListController = require('web.ListController');
var ajax = require('web.ajax');

ListController.include({
   renderButtons: function($node) {
	   this._super.apply(this, arguments);
       if (this.$buttons) {
           this.$buttons.find('.o_list_import_settlements').click(this.proxy('action_import_settlements')) ;
       }
	},
    action_import_settlements: function(){
	    var self=this;
	    ajax.jsonRpc('/get_action_import_settlements','call',{
		}).then(function(data){
        	return self.do_action(data);
        });
       }
   });
});