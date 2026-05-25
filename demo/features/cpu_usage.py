#<imports>
import psutil
#</imports>

#<handlers>
async def handle_cpu(context, args):
    cpu_percent = psutil.cpu_percent(interval=1.0)
    return {
        "title": "CPU",
        "summary": f"CPU usage: {cpu_percent:.1f}%",
        "data": {
            "cpu_percent": cpu_percent,
        },
    }
#</handlers>

COMMAND_REGISTRY_SNIPPET = {
#<registry>
    "cpu": handle_cpu,
#</registry>
}
