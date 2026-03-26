from aiohttp import web
import logging
import os

logger = logging.getLogger(__name__)

async def handle_health(request):
    return web.Response(text="OK", status=200)

async def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    app = web.Application()
    app.router.add_get('/health', handle_health)
    app.router.add_get('/', handle_health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    logger.info(f"✅ Health server started on port {port}")
    await site.start()
