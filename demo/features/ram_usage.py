#<imports>
import psutil
#</imports>

#<handlers>
def _bytes_to_gib(value):
    return round(value / (1024 ** 3), 2)


async def handle_ram(context, args):
    memory = psutil.virtual_memory()
    used_gib = _bytes_to_gib(memory.used)
    total_gib = _bytes_to_gib(memory.total)
    return {
        "title": "RAM",
        "summary": f"RAM usage: {used_gib} GiB / {total_gib} GiB ({memory.percent:.1f}%)",
        "data": {
            "used_gib": used_gib,
            "total_gib": total_gib,
            "percent": memory.percent,
        },
    }
#</handlers>

COMMAND_REGISTRY_SNIPPET = {
#<registry>
    "ram": handle_ram,
#</registry>
}
