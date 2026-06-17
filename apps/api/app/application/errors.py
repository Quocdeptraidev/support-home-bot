class ApplicationError(Exception):
    code = "APPLICATION_ERROR"


class AIProviderError(ApplicationError):
    code = "AI_PROVIDER_ERROR"


class MessageGatewayError(ApplicationError):
    code = "MESSAGE_GATEWAY_ERROR"
