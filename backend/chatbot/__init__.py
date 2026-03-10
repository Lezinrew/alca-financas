"""
Pacote de roteamento do chatbot: intent, FAQ, cache, finance handler.
Reduz uso de LLM encaminhando mensagens para respostas locais quando possível.
"""
from chatbot.router import route_message

__all__ = ["route_message"]
