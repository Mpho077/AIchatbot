# -*- coding: utf-8 -*-
import logging

from odoo import api, Command, fields, models

_logger = logging.getLogger(__name__)


class ImLivechatChannel(models.Model):
    """Extend im_livechat.channel with Grok AI configuration"""

    _inherit = 'im_livechat.channel'

    # Grok AI Integration
    grok_ai_enabled = fields.Boolean(
        'Enable Grok AI',
        default=False,
        help="Enable Grok AI for this livechat channel"
    )
    grok_ai_config_id = fields.Many2one(
        'grok.ai.config',
        string='Grok AI Configuration',
        help="Grok AI configuration to use for this channel"
    )

    # Round-robin operator assignment
    last_assigned_operator_id = fields.Many2one(
        'res.users',
        string='Last Assigned Operator',
        help="Last human operator assigned from AI handoff (for round-robin distribution)"
    )

    def write(self, vals):
        """Override to add/remove AI user from channel operators when Grok AI is enabled/disabled"""
        result = super().write(vals)

        # If Grok AI settings changed, update user_ids
        if 'grok_ai_enabled' in vals or 'grok_ai_config_id' in vals:
            for record in self:
                if record.grok_ai_enabled and record.grok_ai_config_id:
                    # Ensure AI operator exists
                    if not record.grok_ai_config_id.ai_operator_user_id:
                        record.grok_ai_config_id._create_ai_operator_user()

                    # Add AI user to channel operators if not already there
                    ai_user = record.grok_ai_config_id.ai_operator_user_id
                    if ai_user not in record.user_ids:
                        record.user_ids = [Command.link(ai_user.id)]

                    # Ensure AI user has online presence status
                    self._ensure_ai_user_online(ai_user)

                elif 'grok_ai_enabled' in vals and not vals.get('grok_ai_enabled'):
                    # Remove AI user when Grok AI is disabled
                    if record.grok_ai_config_id and record.grok_ai_config_id.ai_operator_user_id:
                        ai_user = record.grok_ai_config_id.ai_operator_user_id
                        if ai_user in record.user_ids:
                            record.user_ids = [Command.unlink(ai_user.id)]

        return result

    def _ensure_ai_user_online(self, ai_user):
        """Ensure AI user is marked as online in the presence system"""
        # In Odoo 19, presence is managed via res.users.presence_ids
        # sudo: res.users - need to access presence system for AI user
        presence = self.env['bus.presence'].sudo().search([
            ('user_id', '=', ai_user.id)
        ], limit=1)

        if presence:
            presence.write({'status': 'online'})
        else:
            self.env['bus.presence'].sudo().create({
                'user_id': ai_user.id,
                'status': 'online',
            })

    def _get_operator_info(self, /, *, lang, country_id, previous_operator_id=None, chatbot_script_id=None, **kwargs):
        """Override to use AI operator when Grok AI is enabled.

        In Odoo 19, the livechat channel uses _get_operator_info to determine which
        operator (agent, chatbot, or AI) should handle a new conversation.
        """
        # If Grok AI is enabled, bypass normal operator/chatbot logic
        if self.grok_ai_enabled and self.grok_ai_config_id:
            # Ensure AI operator user exists
            if not self.grok_ai_config_id.ai_operator_user_id:
                self.grok_ai_config_id._create_ai_operator_user()

            ai_user = self.grok_ai_config_id.ai_operator_user_id
            return {
                'agent': ai_user,
                'chatbot_script': self.env['chatbot.script'],
                'operator_partner': ai_user.partner_id,
                'operator_model': 'res.users',
            }

        # Normal flow when Grok AI is not enabled
        return super()._get_operator_info(
            lang=lang,
            country_id=country_id,
            previous_operator_id=previous_operator_id,
            chatbot_script_id=chatbot_script_id,
            **kwargs,
        )

    def _get_livechat_discuss_channel_vals(self, /, *, chatbot_script=None, agent=None,
                                            operator_partner, operator_model, **kwargs):
        """Override to add Grok AI configuration when creating new sessions.

        In Odoo 19, this method replaces the old _get_livechat_mail_channel_vals.
        """
        vals = super()._get_livechat_discuss_channel_vals(
            chatbot_script=chatbot_script,
            agent=agent,
            operator_partner=operator_partner,
            operator_model=operator_model,
            **kwargs,
        )

        # Add Grok AI configuration if enabled
        if self.grok_ai_enabled and self.grok_ai_config_id:
            vals.update({
                'grok_ai_active': True,
                'grok_ai_config_id': self.grok_ai_config_id.id,
            })

        return vals
