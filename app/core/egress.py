"""Política local para chamadas aos serviços remotos controlados pelo app."""


class EgressDenied(RuntimeError):
    pass


def offline() -> bool:
    from core.config import get_config

    return get_config().get("privacy.offline", False) is True


def require_online(service: str) -> None:
    if offline():
        raise EgressDenied(f"Modo offline: {service} indisponível.")
