import asyncio
import aiohttp
from rest_framework.views import APIView
from rest_framework.response import Response
import os
import socket
import logging
from itertools import cycle

logger = logging.getLogger(__name__)

class LoadBalancedGatewayView(APIView):
    # Список микросервисов (имена из docker-compose.yml)
    MICRO_SERVICES = {
        "book-api": cycle(["http://book-api:5000"]),
        "book-api_2": cycle(["http://book-api:5000"]),
        "user-management-api": cycle(["http://user-management-api:5001"]),
        "user-management-api_2": cycle(["http://user-management-api:5001"])
    }
    EXTERNAL_APIS = [
        "https://api.example.com",
        "https://api2.example.com"
    ]

    async def get(self, request, path):
        logger.info(f"Processing request for path: {path}")
        # Выбираем микросервис для перенаправления с Round Robin
        service_name = next(iter(self.MICRO_SERVICES.keys()))  # Берем первый сервис (можно улучшить)
        service_urls = self.MICRO_SERVICES[service_name]
        service_url = next(service_urls)
        external_api = next(cycle(self.EXTERNAL_APIS))

        hostname = socket.gethostname() + ":" + os.getenv("SERVER_PORT", "unknown")
        try:
            async with aiohttp.ClientSession() as session:
                # Перенаправляем к микросервису
                async with session.get(f"{service_url}/{service_name}/{path}") as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Success from {service_url}")
                        return Response({"message": f"From {hostname} via {service_url}", "data": data})
                    logger.warning(f"Failed to connect to {service_url}, status: {response.status}")
                # Если микросервис недоступен, пробуем внешний API
                async with session.get(f"{external_api}/{path}") as external_response:
                    if external_response.status == 200:
                        data = await external_response.json()
                        logger.info(f"Success from {external_api}")
                        return Response({"message": f"From {hostname} via {external_api}", "data": data})
                    logger.error(f"External API failed, status: {external_response.status}")
                    return Response({"error": "External API failed"}, status=502)
        except Exception as e:
            logger.error(f"Load balancer error: {str(e)}")
            return Response({"error": f"Load balancer error: {str(e)}"}, status=500)

    def get(self, request, *args, **kwargs):
        # Асинхронный вызов для совместимости с DRF
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.async_get(request, *args, **kwargs))

    async def async_get(self, request, *args, **kwargs):
        return await self.get(request, *args, **kwargs)