# -*- coding: utf-8 -*-
{
    'name': 'Live Chat AI Assistant',
    'version': '19.0.1.0.0',
    'category': 'Website/Live Chat',
    'summary': 'AI-powered Live Chat Assistant with Grok AI',
    'assets': {
        'web.assets_frontend': [
            'im_livechat_grok_ai/static/src/css/chatbot.css',
        ]
    },
    'description': """
Live Chat AI Assistant powered by Grok AI
===========================================

This module extends Odoo Live Chat with an intelligent AI Assistant powered by Grok AI:

**Core Features:**
* AI-powered customer support and recommendations
* Dynamic custom API endpoints - Add unlimited APIs from the frontend
* Intelligent buying intent detection
* Automatic handoff to specialists for bookings
* Configurable AI behavior through system prompts
* Conversation history management
* Typing indicators for better user experience

The AI Assistant handles initial inquiries, automatically fetching real-time data
from your configured APIs. When customers are ready to proceed, it seamlessly
transfers them to human agents!
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['im_livechat'],
    'data': [
        'security/ir.model.access.csv',
        'views/grok_ai_config_views.xml',
        'views/grok_api_endpoint_views.xml',
        'views/im_livechat_channel_views.xml',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
