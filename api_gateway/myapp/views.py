import logging
import time
from itertools import cycle
from aiohttp import ClientSession, ClientTimeout
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from django.http import HttpResponse
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)

MICRO_SERVICES = {
    "book-api": cycle(["http://book-api:5000", "http://book-api_2:5000"]),
    "user-management-api": cycle(["http://user-management-api:5001", "http://user-management-api_2:5001"])
}

async def proxy_to_microservice(request, service_group, path):
    microservices = list(MICRO_SERVICES[service_group])
    selected_service = microservices[request.session.get(f'{service_group}_counter', 0) % len(microservices)]
    request.session[f'{service_group}_counter'] = request.session.get(f'{service_group}_counter', 0) + 1

    logger.info(f"Forwarding request to {selected_service}/{path}")
    start_time = time.time()  # Начало отсчёта времени

    timeout = ClientTimeout(total=20, connect=5)
    async with ClientSession(timeout=timeout) as session:
        try:
            method = request.method.lower()
            url = f"{selected_service}/{path}"
            data = request.body if request.body else None
            headers = {
                'Content-Type': request.content_type or 'application/json',
                'Authorization': request.headers.get('Authorization', '')
            }
            async with session.request(method, url, data=data, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    elapsed_time = time.time() - start_time  # Время выполнения
                    logger.info(f"Request to {selected_service}/{path} took {elapsed_time:.2f} seconds")
                    return JsonResponse({
                        'microservice': selected_service,
                        'response': result
                    }, status=response.status)
                else:
                    elapsed_time = time.time() - start_time
                    logger.warning(f"Request to {selected_service}/{path} failed with status {response.status}, took {elapsed_time:.2f} seconds")
                    return JsonResponse({'error': f'Remote server error: {response.status}'}, status=response.status)
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Error connecting to {selected_service}: {e}, took {elapsed_time:.2f} seconds")
            return JsonResponse({'error': f'Failed to connect to {selected_service}: {str(e)}'}, status=503)

@method_decorator(csrf_exempt, name='dispatch')
class UserManagementProxyView(APIView):
    @async_to_sync
    async def get(self, request, path):
        return await proxy_to_microservice(request, "user-management-api", path)

    @async_to_sync
    async def post(self, request, path):
        return await proxy_to_microservice(request, "user-management-api", path)

    @async_to_sync
    async def put(self, request, path):
        return await proxy_to_microservice(request, "user-management-api", path)

    @async_to_sync
    async def delete(self, request, path):
        return await proxy_to_microservice(request, "user-management-api", path)

@method_decorator(csrf_exempt, name='dispatch')
class BookApiProxyView(APIView):
    @async_to_sync
    async def get(self, request, path):
        return await proxy_to_microservice(request, "book-api", path)

    @async_to_sync
    async def post(self, request, path):
        return await proxy_to_microservice(request, "book-api", path)

    @async_to_sync
    async def put(self, request, path):
        return await proxy_to_microservice(request, "book-api", path)

    @async_to_sync
    async def delete(self, request, path):
        return await proxy_to_microservice(request, "book-api", path)

def health_check(request):
    return HttpResponse("OK", status=200)