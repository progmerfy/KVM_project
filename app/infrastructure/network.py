import random


def generate_mac() -> str:
    # locally administered MAC, QEMU/virtio style
    mac = [
        0x52,
        0x54,
        0x00,
        random.randrange(0x00, 0xFF),
        random.randrange(0x00, 0xFF),
        random.randrange(0x00, 0xFF),
    ]
    return ":".join(map(lambda x: "%02x" % x, mac))
