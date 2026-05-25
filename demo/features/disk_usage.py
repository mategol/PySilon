#<imports>
import psutil
#</imports>

#<handlers>
def _bytes_to_gib(value):
    return round(value / (1024 ** 3), 2)


async def handle_disk(context, args):
    disks = []
    for partition in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except OSError:
            continue

        disks.append(
            {
                "device": partition.device,
                "mountpoint": partition.mountpoint,
                "fstype": partition.fstype,
                "used_gib": _bytes_to_gib(usage.used),
                "total_gib": _bytes_to_gib(usage.total),
                "percent": usage.percent,
            }
        )

    if not disks:
        summary = "No readable disks found."
    else:
        summary = "\n".join(
            f"{disk['mountpoint']}: {disk['used_gib']} GiB / {disk['total_gib']} GiB ({disk['percent']:.1f}%)"
            for disk in disks
        )

    return {
        "title": "Disk",
        "summary": summary,
        "data": {
            "disks": disks,
        },
    }
#</handlers>

COMMAND_REGISTRY_SNIPPET = {
#<registry>
    "disk": handle_disk,
#</registry>
}
