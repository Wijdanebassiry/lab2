"""Transfert transparent d'une requete vers un microservice. A CODER PAR [Auth]."""


async def forward(request, service, address, client):
    """Transmet `request` a `address` avec `client` (httpx.AsyncClient) et renvoie une Response."""
    raise NotImplementedError("proxy.forward : a implementer (branche lab5/proxy)")